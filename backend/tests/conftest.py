from copy import deepcopy

import pytest


@pytest.fixture
def market():
    return {
        "id": "sample",
        "market_cap": 2_000_000,
        "fully_diluted_valuation": 8_000_000,
        "total_volume": 75_000,
        "total_supply": 1_000_000,
        "max_supply": 1_000_000,
    }


@pytest.fixture
def detail(market):
    return {
        "id": market["id"],
        "name": "Sample Project",
        "symbol": "smp",
        "preview_listing": True,
        "market_data": {
            key: {"usd": value} if key in {
                "market_cap", "fully_diluted_valuation", "total_volume"
            } else value
            for key, value in market.items() if key != "id"
        } | {"total_value_locked": {"usd": 60_000}},
    }


@pytest.fixture
def make_coin(market, detail):
    """Create independent snapshots, like /markets and /coins/{id} return."""
    def make(coin_id, *, cap=2_000_000):
        listing, snapshot = deepcopy(market), deepcopy(detail)
        listing.update(id=coin_id, market_cap=cap)
        snapshot.update(id=coin_id, name=coin_id.title())
        snapshot["market_data"]["market_cap"]["usd"] = cap
        return listing, snapshot

    return make
