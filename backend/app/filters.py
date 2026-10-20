"""Pure filtering functions shared by live data and demo fixtures."""

from decimal import Decimal, InvalidOperation
from typing import Any

from .models import Project

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
    cap = number(market.get("market_cap"))
    fdv = number(market.get("fully_diluted_valuation"))
    volume = number(market.get("total_volume"))
    total = number(market.get("total_supply"))
    maximum = number(market.get("max_supply"))
    return (
        cap is not None and cap > 0
        and fdv is not None and 0 <= fdv < FDV_LIMIT
        and volume is not None and volume > ACTIVITY_MINIMUM
        and total is not None and total > 0
        and maximum is not None and maximum == total
    )


def usd(value: Any) -> Any:
    return value.get("usd") if isinstance(value, dict) else value


def project_from_detail(detail: dict[str, Any]) -> Project | None:
    if detail.get("preview_listing") is not True:
        return None
    market_data = detail.get("market_data")
    if not isinstance(market_data, dict):
        return None
    market = {
        "market_cap": usd(market_data.get("market_cap")),
        "fully_diluted_valuation": usd(market_data.get("fully_diluted_valuation")),
        "total_volume": usd(market_data.get("total_volume")),
        "total_supply": market_data.get("total_supply"),
        "max_supply": market_data.get("max_supply"),
    }
    # Recheck ALL numeric criteria on the detail snapshot, not older list data.
    tvl = number(usd(market_data.get("total_value_locked")))
    if not passes_market_filters(market) or tvl is None or tvl <= ACTIVITY_MINIMUM:
        return None
    if any(not isinstance(detail.get(key), str) or not detail[key].strip()
           for key in ("id", "name", "symbol")):
        return None
    return Project(
        id=detail["id"], name=detail["name"], symbol=detail["symbol"],
        market_cap=market["market_cap"], fdv=market["fully_diluted_valuation"],
        volume_24h=market["total_volume"], tvl=tvl,
        total_supply=market["total_supply"], max_supply=market["max_supply"],
    )
