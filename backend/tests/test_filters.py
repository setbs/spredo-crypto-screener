from decimal import Decimal

import pytest

from app.filters import passes_market_filters, project_from_detail


@pytest.mark.parametrize(("field", "value"), [
    ("market_cap", 0),
    ("market_cap", -1),
    ("market_cap", None),
    ("market_cap", True),
    ("market_cap", float("inf")),
    ("market_cap", float("nan")),
    ("market_cap", "1000000"),
    ("fully_diluted_valuation", 100_000_000),
    ("fully_diluted_valuation", None),
    ("fully_diluted_valuation", -1),
    ("total_volume", 50_000),
    ("total_volume", 49_999),
    ("total_volume", False),
    ("total_supply", 0),
    ("max_supply", None),
    ("max_supply", 1_000_001),
    ("max_supply", Decimal("1000000.00000000001")),
])
def test_market_rejects_nonqualifying_or_unknown_numbers(market, field, value):
    market[field] = value
    assert passes_market_filters(market) is False


def test_strict_thresholds_allow_values_just_inside_boundaries(market, detail):
    market.update(market_cap=Decimal("0.01"),
                  fully_diluted_valuation=Decimal("99999999.99"),
                  total_volume=Decimal("50000.01"))
    assert passes_market_filters(market) is True
    detail["market_data"].update(
        market_cap={"usd": market["market_cap"]},
        fully_diluted_valuation={"usd": market["fully_diluted_valuation"]},
        total_volume={"usd": market["total_volume"]},
        total_value_locked={"usd": Decimal("50000.01")},
    )
    project = project_from_detail(detail)
    assert project is not None
    assert project.preview_listing is True
    assert project.total_supply == project.max_supply


@pytest.mark.parametrize("value", [False, None, 1, "true"])
def test_preview_listing_requires_json_boolean_true(detail, value):
    detail["preview_listing"] = value
    assert project_from_detail(detail) is None


@pytest.mark.parametrize(("field", "value"), [
    ("market_cap", {"usd": 0}),
    ("fully_diluted_valuation", {"usd": 100_000_000}),
    ("total_volume", {"usd": 50_000}),
    ("max_supply", 2_000_000),
    ("total_value_locked", {"usd": 50_000}),
    ("total_value_locked", None),
    ("total_value_locked", {"eth": 90_000}),
    ("total_value_locked", {"usd": True}),
])
def test_detail_snapshot_rechecks_all_criteria(detail, field, value):
    detail["market_data"][field] = value
    assert project_from_detail(detail) is None


def test_missing_fields_are_not_inferred(detail, market):
    del market["max_supply"]
    assert passes_market_filters(market) is False
    del detail["preview_listing"]
    assert project_from_detail(detail) is None
