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
    cache_ttl_seconds: int = Field(default=3600, ge=1)
    request_interval_seconds: float = Field(default=0.75, ge=0)
    scan_cache_path: Path | None = Path(__file__).resolve().parents[1] / ".cache" / "live-scan.json"

    @property
    def api_url(self) -> str:
        host = "pro-api" if self.coingecko_api_tier == "pro" else "api"
        return f"https://{host}.coingecko.com/api/v3/"
