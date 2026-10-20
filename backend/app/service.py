import asyncio
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field

from .coingecko import CoinGeckoClient, UpstreamError
from .config import Settings
from .filters import ACTIVITY_MINIMUM, inspect_detail, number, passes_market_filters, project_from_detail
from .models import ProjectsResponse, ScanMeta


class Checkpoint(BaseModel):
    """Only normalized results and cursors; never API keys or raw responses."""

    version: int = 1
    next_page: int = Field(default=1, ge=1)
    seen_ids: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    completed_at: float | None = None
    response: ProjectsResponse


class ProjectService:
    def __init__(self, client: CoinGeckoClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._state = self._new_state()
        if settings.data_mode == "live":
            self._load()

    @staticmethod
    def _new_state() -> Checkpoint:
        return Checkpoint(response=ProjectsResponse(projects=[], meta=ScanMeta(
            mode="live", fetched_at=datetime.now(timezone.utc).isoformat(),
            status="scanning", phase="markets", market_coins_scanned=0,
            candidates=0, details_checked=0,
        )))

    async def get_projects(self, retry: bool = False) -> ProjectsResponse:
        # Return immediately. Concurrent browsers share one background task.
        async with self._lock:
            if self.settings.data_mode == "demo":
                return self._demo()
            meta = self._state.response.meta
            if meta.status == "complete":
                completed = self._state.completed_at or 0
                if time.time() - completed < self.settings.cache_ttl_seconds:
                    result = self._state.response.model_copy(deep=True)
                    result.meta.cached = True
                    return result
                self._state = self._new_state()
                meta = self._state.response.meta
            if meta.status == "error" and retry:
                meta.status, meta.error = "scanning", None
            if meta.status == "scanning" and (self._task is None or self._task.done()):
                self._task = asyncio.create_task(self._scan(), name="coingecko-live-scan")
            return self._state.response.model_copy(deep=True)

    async def close(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _demo(self) -> ProjectsResponse:
        path = Path(__file__).resolve().parents[1] / "data" / "demo.json"
        details = json.loads(path.read_text(), parse_float=Decimal)
        projects = [project for detail in details if (project := project_from_detail(detail))]
        return ProjectsResponse(projects=projects, meta=ScanMeta(
            mode="demo", fetched_at=datetime.now(timezone.utc).isoformat(),
            market_coins_scanned=len(details), candidates=len(details), details_checked=len(details),
            warnings=["Synthetic demo projects for testing. These are not live CoinGecko listings."],
        ))

    async def _scan(self) -> None:
        state = self._state
        meta = state.response.meta
        seen = set(state.seen_ids)
        try:
            while meta.phase == "markets":
                coins = await self.client.markets(state.next_page)
                meta.market_coins_scanned += len(coins)
                for coin in coins:
                    coin_id = coin.get("id")
                    if isinstance(coin_id, str) and coin_id and coin_id not in seen:
                        seen.add(coin_id)
                        state.seen_ids.append(coin_id)
                        if passes_market_filters(coin):
                            state.candidate_ids.append(coin_id)
                meta.candidates = len(state.candidate_ids)
                state.next_page += 1
                # Results are ordered by volume descending. Once the final
                # volume is <= $50k, later pages cannot meet the volume rule.
                last_volume = number(coins[-1].get("total_volume")) if coins else None
                if len(coins) < 250 or (last_volume is not None and last_volume <= ACTIVITY_MINIMUM):
                    meta.phase = "details"
                self._save()

            for coin_id in state.candidate_ids[meta.details_checked:]:
                detail = await self.client.detail(coin_id)
                inspected = inspect_detail(detail)
                project = project_from_detail(detail)
                if project is not None:
                    state.response.projects.append(project)
                    state.response.projects.sort(key=lambda p: p.market_cap, reverse=True)
                else:
                    for reason in inspected.rejection_reasons:
                        meta.rejection_counts[reason] = meta.rejection_counts.get(reason, 0) + 1
                    if len(state.response.inspected_projects) < 10:
                        state.response.inspected_projects.append(inspected)
                meta.details_checked += 1
                self._save()

            # Completion requires exhausting market pages and inspecting every
            # numeric candidate. An interrupted scan does not get a cache TTL.
            meta.status, meta.phase = "complete", "complete"
            meta.fetched_at = datetime.now(timezone.utc).isoformat()
            state.completed_at = time.time()
            self._save()
        except asyncio.CancelledError:
            # Each completed page/detail was checkpointed. The interrupted
            # request will be repeated safely after restart.
            raise
        except Exception as exc:
            meta.status = "error"
            meta.error = str(exc) if isinstance(exc, UpstreamError) else (
                "The scan stopped unexpectedly. Check backend logs and resume the scan."
            )
            try:
                self._save()
            except UpstreamError:
                pass

    def _save(self) -> None:
        path = self.settings.scan_cache_path
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(self._state.model_dump_json(), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            raise UpstreamError("Unable to save scan progress. Check the backend cache directory permissions.") from exc

    def _load(self) -> None:
        path = self.settings.scan_cache_path
        if path is None or not path.is_file():
            return
        try:
            state = Checkpoint.model_validate_json(path.read_text(encoding="utf-8"))
            meta = state.response.meta
            if (state.version != 1 or meta.mode != "live"
                    or meta.candidates != len(state.candidate_ids)
                    or not 0 <= meta.details_checked <= len(state.candidate_ids)
                    or (meta.status == "complete" and (
                        meta.phase != "complete" or meta.details_checked != meta.candidates
                        or state.completed_at is None
                    ))):
                raise ValueError("Invalid checkpoint")
            self._state = state
        except (OSError, ValueError):
            self._state.response.meta.warnings.append(
                "The saved checkpoint could not be read; a fresh scan will start."
            )
