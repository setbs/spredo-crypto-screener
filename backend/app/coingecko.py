import asyncio
import time
from decimal import Decimal
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
        # Sequential, paced calls keep the free API budget predictable.
        delay = self.settings.request_interval_seconds - (time.monotonic() - self._last_request)
        if delay > 0:
            await asyncio.sleep(delay)
        self._last_request = time.monotonic()
        headers = {}
        key = self.settings.coingecko_api_key.get_secret_value()
        if key:
            headers[f"x-cg-{self.settings.coingecko_api_tier}-api-key"] = key
        try:
            response = await self.http.get(path, params=params, headers=headers)
            if response.status_code == 429:
                raise UpstreamError("CoinGecko rate limit reached. Wait a minute and try again.", 503)
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
