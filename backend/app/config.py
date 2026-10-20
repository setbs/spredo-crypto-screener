from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_mode: Literal["live", "demo"] = "live"
    coingecko_api_key: SecretStr = SecretStr("")
    coingecko_api_tier: Literal["demo", "pro"] = "demo"
    market_pages: int = Field(default=4, ge=1, le=100)
    max_detail_requests: int = Field(default=25, ge=1, le=1000)
    cache_ttl_seconds: int = Field(default=300, ge=1)
    request_interval_seconds: float = Field(default=2.1, ge=0)

    @property
    def api_url(self) -> str:
        host = "pro-api" if self.coingecko_api_tier == "pro" else "api"
        return f"https://{host}.coingecko.com/api/v3/"
