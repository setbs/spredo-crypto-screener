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
    status: Literal["scanning", "complete", "error"] = "complete"
    phase: Literal["markets", "details", "complete"] = "complete"
    rejection_counts: dict[str, int] = Field(default_factory=dict)
    error: str | None = None
    market_scan_truncated: bool = False
    detail_scan_truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class InspectedProject(BaseModel):
    """Real inspected candidates, kept separate from qualifying results."""

    id: str
    name: str
    symbol: str
    market_cap: float | None = None
    fdv: float | None = None
    volume_24h: float | None = None
    tvl: float | None = None
    preview_listing: bool | None = None
    rejection_reasons: list[str] = Field(default_factory=list)


class ProjectsResponse(BaseModel):
    projects: list[Project]
    inspected_projects: list[InspectedProject] = Field(default_factory=list)
    meta: ScanMeta
