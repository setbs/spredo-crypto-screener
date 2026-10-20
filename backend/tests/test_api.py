import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest

from app.coingecko import CoinGeckoClient
from app.config import Settings
from app.main import create_app
from app.service import ProjectService

pytestmark = pytest.mark.asyncio


@asynccontextmanager
async def client_for(app):
    # ASGITransport does not run lifespan automatically. Enter it explicitly so
    # these requests exercise the same initialized service as the running API.
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            base_url="http://testserver", transport=httpx.ASGITransport(app=app)
        ) as client:
            yield client


def settings(**overrides):
    return Settings(_env_file=None, request_interval_seconds=0,
                    coingecko_api_key="test-secret", **overrides)


async def test_live_endpoint_filters_sorts_and_reuses_cache(make_coin):
    small, small_detail = make_coin("small", cap=1_000_000)
    big, big_detail = make_coin("big", cap=5_000_000)
    changed, changed_detail = make_coin("changed")
    changed_detail["market_data"]["total_volume"]["usd"] = 50_000
    rejected, _ = make_coin("rejected", cap=0)
    not_preview, not_preview_detail = make_coin("not-preview")
    not_preview_detail["preview_listing"] = False
    snapshots = {p["id"]: p for p in [small_detail, big_detail, changed_detail,
                                         not_preview_detail]}
    requests = []

    def upstream(request):
        requests.append(request)
        assert request.headers["x-cg-demo-api-key"] == "test-secret"
        if request.url.path.endswith("/markets"):
            assert request.url.params["vs_currency"] == "usd"
            assert request.url.params["order"] == "volume_desc"
            return httpx.Response(200, json=[small, big, changed, rejected, not_preview, small])
        return httpx.Response(200, json=snapshots[request.url.path.rsplit("/", 1)[1]])

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        first = await client.get("/api/projects")
        second = await client.get("/api/projects")

    assert first.status_code == second.status_code == 200
    payload = first.json()
    assert [p["id"] for p in payload["projects"]] == ["big", "small"]
    assert payload["projects"][0]["tvl"] == 60_000
    assert payload["meta"] | {"fetched_at": None} == {
        "mode": "live", "fetched_at": None, "cached": False,
        "market_coins_scanned": 6, "candidates": 4, "details_checked": 4,
        "market_scan_truncated": False, "detail_scan_truncated": False, "warnings": [],
    }
    assert second.json()["meta"]["cached"] is True
    assert second.json()["projects"] == payload["projects"]
    assert second.json()["meta"]["fetched_at"] == payload["meta"]["fetched_at"]
    assert len(requests) == 5


async def test_pagination_and_detail_budget_are_reported(make_coin):
    first, first_detail = make_coin("first")
    second, _ = make_coin("second")
    third, _ = make_coin("third")
    filler = [{"id": f"excluded-{i}", "total_volume": 60_000} for i in range(248)]
    pages = []
    details = []

    def upstream(request):
        if request.url.path.endswith("/markets"):
            page = int(request.url.params["page"])
            pages.append(page)
            return httpx.Response(200, json=[first, second, *filler] if page == 1 else [third])
        details.append(request.url.path)
        return httpx.Response(200, json=first_detail)

    app = create_app(settings(market_pages=3, max_detail_requests=1), httpx.MockTransport(upstream))
    async with client_for(app) as client:
        payload = (await client.get("/api/projects")).json()

    assert pages == [1, 2]
    assert len(details) == 1
    assert [p["id"] for p in payload["projects"]] == ["first"]
    assert payload["meta"]["market_coins_scanned"] == 251
    assert payload["meta"]["candidates"] == 3
    assert payload["meta"]["details_checked"] == 1
    assert payload["meta"]["detail_scan_truncated"] is True
    assert payload["meta"]["market_scan_truncated"] is False
    assert "1 of 3" in payload["meta"]["warnings"][0]


@pytest.mark.parametrize(("last_volume", "truncated"), [(60_000, True), (50_000, False)])
async def test_page_limit_and_volume_cutoff_have_distinct_metadata(last_volume, truncated):
    listings = [{"id": f"no-cap-{i}", "total_volume": last_volume} for i in range(250)]
    requests = []

    def upstream(request):
        requests.append(request)
        assert request.url.path.endswith("/markets")
        return httpx.Response(200, json=listings)

    async with client_for(create_app(settings(market_pages=1), httpx.MockTransport(upstream))) as client:
        payload = (await client.get("/api/projects")).json()

    assert len(requests) == 1
    assert payload["projects"] == []
    assert payload["meta"]["market_scan_truncated"] is truncated
    assert bool(payload["meta"]["warnings"]) is truncated


@pytest.mark.parametrize(("failure", "expected_status", "message"), [
    (429, 503, "rate limit"),
    (401, 503, "denied access"),
    (500, 502, "Unable to read"),
    ("timeout", 504, "timed out"),
    ("invalid-json", 502, "Unable to read"),
    ("invalid-shape", 502, "unexpected markets"),
])
async def test_upstream_failures_are_actionable_and_not_cached(failure, expected_status, message):
    calls = 0

    def upstream(request):
        nonlocal calls
        calls += 1
        if calls > 1:
            return httpx.Response(200, json=[])
        if failure == "timeout":
            raise httpx.ReadTimeout("contains a secret upstream URL", request=request)
        if failure == "invalid-json":
            return httpx.Response(200, text="not JSON")
        if failure == "invalid-shape":
            return httpx.Response(200, json={"message": "bad response"})
        return httpx.Response(failure, text="test-secret")

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        failed = await client.get("/api/projects")
        recovered = await client.get("/api/projects")

    assert failed.status_code == expected_status
    assert message in failed.json()["detail"]
    assert "test-secret" not in failed.text
    assert "secret upstream URL" not in failed.text
    assert recovered.status_code == 200
    assert recovered.json()["meta"]["mode"] == "live"
    assert recovered.json()["projects"] == []
    assert calls == 2


async def test_wrong_detail_identity_is_an_upstream_error(make_coin):
    listing, snapshot = make_coin("requested")
    snapshot["id"] = "different-project"

    def upstream(request):
        return httpx.Response(200, json=[listing] if request.url.path.endswith("/markets") else snapshot)

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        response = await client.get("/api/projects")
    assert response.status_code == 502
    assert "unexpected coin details" in response.json()["detail"]


async def test_demo_is_explicit_and_never_calls_external_api():
    def upstream(request):
        pytest.fail(f"Demo must not send an upstream request: {request.url.path}")

    async with client_for(create_app(settings(data_mode="demo"), httpx.MockTransport(upstream))) as client:
        assert (await client.get("/api/health")).json() == {"status": "ok", "mode": "demo"}
        response = await client.get("/api/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["mode"] == "demo"
    assert "Synthetic" in payload["meta"]["warnings"][0]
    assert payload["projects"]
    assert all(p["preview_listing"] is True and p["tvl"] > 50_000 for p in payload["projects"])


async def test_concurrent_requests_share_scan_and_cached_responses_are_independent(make_coin, monkeypatch):
    listing, snapshot = make_coin("shared")
    calls = 0
    now = [100.0]
    monkeypatch.setattr("app.service.time.monotonic", lambda: now[0])

    async def upstream(request):
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return httpx.Response(200, json=[listing] if request.url.path.endswith("/markets") else snapshot)

    config = settings(cache_ttl_seconds=60)
    async with httpx.AsyncClient(base_url=config.api_url, transport=httpx.MockTransport(upstream)) as http:
        service = ProjectService(CoinGeckoClient(http, config), config)
        responses = await asyncio.gather(*(service.get_projects() for _ in range(5)))
        assert calls == 2
        assert sum(not r.meta.cached for r in responses) == 1
        responses[0].projects.clear()
        responses[1].meta.warnings.append("consumer mutation")
        cached = await service.get_projects()
        assert len(cached.projects) == 1
        assert cached.meta.warnings == []

        now[0] += 61
        refreshed = await service.get_projects()
        assert calls == 4
        assert refreshed.meta.cached is False
