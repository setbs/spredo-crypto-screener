from typing import Literal

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    symbol: str
    market_cap: float
    fdv: float
    volume_24h: float
    tvl: float
    total_supply: float
    max_supply: float
    preview_listing: Literal[True] = True


class ScanMeta(BaseModel):
    mode: Literal["live", "demo"]
    fetched_at: str
    cached: bool = False
    market_coins_scanned: int
    candidates: int
    details_checked: int
    market_scan_truncated: bool = False
    detail_scan_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class ProjectsResponse(BaseModel):
    projects: list[Project]
    meta: ScanMeta
