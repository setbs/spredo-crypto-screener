import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings


class UpstreamError(Exception):
    """An actionable public message without exposing URLs, keys or responses."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class CoinGeckoClient:
    def __init__(self, http: httpx.AsyncClient, settings: Settings):
        self.http = http
        self.settings = settings
        self._last_request = 0.0

    async def _get(self, path: str, params: dict[str, Any]) -> Any:
        headers = {}
        key = self.settings.coingecko_api_key.get_secret_value()
        if key:
            headers[f"x-cg-{self.settings.coingecko_api_tier}-api-key"] = key
        interval = self.settings.request_interval_seconds
        if not key:
            interval = max(interval, 2.1)
        # Retry only transient failures. A failed scan retains its cursor, so
        # explicit retry resumes from the failed request rather than starting over.
        try:
            for attempt in range(3):
                delay = interval - (time.monotonic() - self._last_request)
                if delay > 0:
                    await asyncio.sleep(delay)
                self._last_request = time.monotonic()
                response = await self.http.get(path, params=params, headers=headers)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt < 2:
                        await asyncio.sleep(self._retry_delay(response.headers.get("Retry-After"), attempt))
                        continue
                    if response.status_code == 429:
                        raise UpstreamError(
                            "CoinGecko rate limit reached after retries. Wait a minute, then resume the scan.", 503
                        )
                    raise UpstreamError("Unable to read CoinGecko data after retries. Resume the scan later.")
                if response.status_code in (401, 403):
                    raise UpstreamError(
                        "CoinGecko denied access. Check the backend API key and its Demo/Pro tier.", 503
                    )
                response.raise_for_status()
                return response.json(parse_float=Decimal)
        except httpx.TimeoutException as exc:
            raise UpstreamError("CoinGecko timed out. Please try again.", 504) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise UpstreamError("Unable to read CoinGecko data. Please try again.") from exc

    @staticmethod
    def _retry_delay(value: str | None, attempt: int) -> float:
        delay = float(2 ** attempt)
        if value:
            try:
                delay = float(value)
            except ValueError:
                try:
                    delay = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
                except (TypeError, ValueError, OverflowError):
                    pass
        return max(0.0, min(delay, 60.0))

    async def markets(self, page: int) -> list[dict[str, Any]]:
        data = await self._get("coins/markets", {
            "vs_currency": "usd", "order": "volume_desc", "per_page": 250,
            "page": page, "sparkline": "false",
        })
        if not isinstance(data, list) or any(not isinstance(coin, dict) for coin in data):
            raise UpstreamError("CoinGecko returned an unexpected markets response.")
        return data

    async def detail(self, coin_id: str) -> dict[str, Any]:
        data = await self._get(f"coins/{quote(coin_id, safe='')}", {
            "localization": "false", "tickers": "false", "market_data": "true",
            "community_data": "false", "developer_data": "false", "sparkline": "false",
        })
        if not isinstance(data, dict) or data.get("id") != coin_id:
            raise UpstreamError("CoinGecko returned an unexpected coin details response.")
        return data
