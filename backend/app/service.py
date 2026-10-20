import asyncio
import json
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .coingecko import CoinGeckoClient
from .config import Settings
from .filters import ACTIVITY_MINIMUM, number, passes_market_filters, project_from_detail
from .models import ProjectsResponse, ScanMeta


class ProjectService:
    def __init__(self, client: CoinGeckoClient, settings: Settings):
        self.client = client
        self.settings = settings
        self._lock = asyncio.Lock()
        self._cache: ProjectsResponse | None = None
        self._expires_at = 0.0

    async def get_projects(self) -> ProjectsResponse:
        # A lock + second cache check collapse concurrent browser requests to one scan.
        async with self._lock:
            if self._cache is not None and time.monotonic() < self._expires_at:
                result = self._cache.model_copy(deep=True)
                result.meta.cached = True
                return result
            result = self._demo() if self.settings.data_mode == "demo" else await self._scan()
            self._cache = result.model_copy(deep=True)
            self._expires_at = time.monotonic() + self.settings.cache_ttl_seconds
            return result

    def _demo(self) -> ProjectsResponse:
        path = Path(__file__).resolve().parents[1] / "data" / "demo.json"
        details = json.loads(path.read_text(), parse_float=Decimal)
        projects = [project for detail in details if (project := project_from_detail(detail))]
        return ProjectsResponse(projects=projects, meta=ScanMeta(
            mode="demo", fetched_at=datetime.now(timezone.utc).isoformat(),
            market_coins_scanned=len(details), candidates=len(details), details_checked=len(details),
            warnings=["Synthetic demo projects for testing. These are not live CoinGecko listings."],
        ))

    async def _scan(self) -> ProjectsResponse:
        candidates = []
        scanned = 0
        seen = set()
        exhausted = False
        for page in range(1, self.settings.market_pages + 1):
            coins = await self.client.markets(page)
            scanned += len(coins)
            for coin in coins:
                coin_id = coin.get("id")
                if isinstance(coin_id, str) and coin_id and coin_id not in seen:
                    seen.add(coin_id)
                    if passes_market_filters(coin):
                        candidates.append(coin_id)
            # volume_desc means later pages cannot pass the volume threshold.
            last_volume = number(coins[-1].get("total_volume")) if coins else None
            if len(coins) < 250 or (last_volume is not None and last_volume <= ACTIVITY_MINIMUM):
                exhausted = True
                break

        projects = []
        checked = 0
        for coin_id in candidates[:self.settings.max_detail_requests]:
            detail = await self.client.detail(coin_id)
            checked += 1
            project = project_from_detail(detail)
            if project is not None:
                projects.append(project)

        warnings = []
        if not exhausted:
            warnings.append(
                f"Scan limited to {self.settings.market_pages} market pages ordered by 24h volume. "
                "Lower-volume projects may not have been scanned."
            )
        detail_truncated = len(candidates) > checked
        if detail_truncated:
            warnings.append(
                f"Checked {checked} of {len(candidates)} candidates to limit API usage. "
                "Increase MAX_DETAIL_REQUESTS for wider coverage."
            )
        return ProjectsResponse(
            projects=sorted(projects, key=lambda p: p.market_cap, reverse=True),
            meta=ScanMeta(
                mode="live", fetched_at=datetime.now(timezone.utc).isoformat(),
                market_coins_scanned=scanned, candidates=len(candidates), details_checked=checked,
                market_scan_truncated=not exhausted, detail_scan_truncated=detail_truncated,
                warnings=warnings,
            ),
        )
