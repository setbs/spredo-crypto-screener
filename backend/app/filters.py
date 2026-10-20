"""Pure filtering functions shared by live data and demo fixtures."""

from decimal import Decimal, InvalidOperation
from typing import Any

from .models import InspectedProject, Project

FDV_LIMIT = Decimal("100000000")
ACTIVITY_MINIMUM = Decimal("50000")


def number(value: Any) -> Decimal | None:
    # Missing values never become zero; bool is a number subclass in Python.
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def passes_market_filters(market: dict[str, Any]) -> bool:
    return not market_rejection_reasons(market)


def market_rejection_reasons(market: dict[str, Any]) -> list[str]:
    cap = number(market.get("market_cap"))
    fdv = number(market.get("fully_diluted_valuation"))
    volume = number(market.get("total_volume"))
    total = number(market.get("total_supply"))
    maximum = number(market.get("max_supply"))
    reasons = []
    if cap is None or cap <= 0:
        reasons.append("Market capitalization must exceed $0")
    if fdv is None or not 0 <= fdv < FDV_LIMIT:
        reasons.append("FDV must be available and below $100 million")
    if volume is None or volume <= ACTIVITY_MINIMUM:
        reasons.append("24h volume must exceed $50,000")
    if total is None or total <= 0 or maximum is None or maximum != total:
        reasons.append("Max supply must equal a positive total supply")
    return reasons


def usd(value: Any) -> Any:
    return value.get("usd") if isinstance(value, dict) else value


def project_from_detail(detail: dict[str, Any]) -> Project | None:
    inspected = inspect_detail(detail)
    if inspected.rejection_reasons:
        return None
    market_data = detail["market_data"]
    return Project(
        id=detail["id"], name=detail["name"], symbol=detail["symbol"],
        market_cap=inspected.market_cap, fdv=inspected.fdv,
        volume_24h=inspected.volume_24h, tvl=inspected.tvl,
        total_supply=market_data["total_supply"], max_supply=market_data["max_supply"],
    )


def inspect_detail(detail: dict[str, Any]) -> InspectedProject:
    market_data = detail.get("market_data")
    market_data = market_data if isinstance(market_data, dict) else {}
    market = {
        "market_cap": usd(market_data.get("market_cap")),
        "fully_diluted_valuation": usd(market_data.get("fully_diluted_valuation")),
        "total_volume": usd(market_data.get("total_volume")),
        "total_supply": market_data.get("total_supply"),
        "max_supply": market_data.get("max_supply"),
    }
    # Recheck ALL criteria on the detail snapshot. Decimal supply comparisons
    # happen before converting values for the JSON-facing presentation models.
    reasons = market_rejection_reasons(market)
    preview = detail.get("preview_listing")
    if preview is not True:
        reasons.append("preview_listing is false" if preview is False else "preview_listing is missing")
    tvl = number(usd(market_data.get("total_value_locked")))
    if tvl is None:
        reasons.append("TVL is unavailable")
    elif tvl <= ACTIVITY_MINIMUM:
        reasons.append("TVL must exceed $50,000")
    if any(not isinstance(detail.get(key), str) or not detail[key].strip()
           for key in ("id", "name", "symbol")):
        reasons.append("Project identity is incomplete")
    return InspectedProject(
        id=detail.get("id") if isinstance(detail.get("id"), str) else "unknown",
        name=detail.get("name") if isinstance(detail.get("name"), str) else "Unknown project",
        symbol=detail.get("symbol") if isinstance(detail.get("symbol"), str) else "?",
        market_cap=number(market["market_cap"]),
        fdv=number(market["fully_diluted_valuation"]),
        volume_24h=number(market["total_volume"]), tvl=tvl,
        preview_listing=preview if isinstance(preview, bool) else None,
        rejection_reasons=reasons,
    )
