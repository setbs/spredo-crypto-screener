import asyncio
from contextlib import asynccontextmanager

import httpx
import pytest

from app.config import Settings
from app.coingecko import CoinGeckoClient
from app.main import create_app

pytestmark = pytest.mark.asyncio


@asynccontextmanager
async def client_for(app):
    # ASGITransport does not run lifespan automatically, including cancellation
    # of an unfinished scan when the Python application shuts down.
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            base_url="http://testserver", transport=httpx.ASGITransport(app=app)
        ) as client:
            yield client


def settings(**overrides):
    values = {
        "_env_file": None,
        "request_interval_seconds": 0,
        "coingecko_api_key": "test-secret",
        # Persistence tests explicitly use tmp_path, never the live cache.
        "scan_cache_path": None,
    }
    return Settings(**(values | overrides))


async def terminal_payload(client, *, status="complete"):
    # Mocks complete locally; timeout detects a stalled background task.
    async with asyncio.timeout(5):
        while True:
            response = await client.get("/api/projects")
            assert response.status_code == 200, response.text
            payload = response.json()
            if payload["meta"]["status"] != "scanning":
                assert payload["meta"]["status"] == status, payload
                return payload
            await asyncio.sleep(0)


async def test_live_endpoint_filters_sorts_and_reuses_complete_cache(make_coin):
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
        initial = await client.get("/api/projects")
        assert initial.status_code == 200
        assert initial.json()["meta"]["status"] == "scanning"
        payload = await terminal_payload(client)
        cached = (await client.get("/api/projects")).json()

    assert [p["id"] for p in payload["projects"]] == ["big", "small"]
    assert payload["projects"][0]["tvl"] == 60_000
    meta = payload["meta"]
    assert meta["mode"] == "live"
    assert meta["phase"] == "complete"
    assert meta["market_coins_scanned"] == 6
    assert meta["candidates"] == meta["details_checked"] == 4
    assert meta["market_scan_truncated"] is meta["detail_scan_truncated"] is False
    assert cached["meta"]["cached"] is True
    assert cached["projects"] == payload["projects"]
    assert cached["meta"]["fetched_at"] == meta["fetched_at"]
    assert len(requests) == 5


async def test_scan_covers_more_than_four_pages_and_twenty_five_candidates(make_coin):
    listings, snapshots = zip(*(make_coin(f"project-{i}") for i in range(31)))
    pages = []
    details = []

    def upstream(request):
        if request.url.path.endswith("/markets"):
            page = int(request.url.params["page"])
            pages.append(page)
            candidates = list(listings[(page - 1) * 7:page * 7])
            if page <= 5:
                candidates += [
                    {"id": f"excluded-{page}-{i}", "total_volume": 60_000}
                    for i in range(250 - len(candidates))
                ]
            return httpx.Response(200, json=candidates)
        coin_id = request.url.path.rsplit("/", 1)[1]
        details.append(coin_id)
        return httpx.Response(200, json=next(p for p in snapshots if p["id"] == coin_id))

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        payload = await terminal_payload(client)

    assert pages == [1, 2, 3, 4, 5, 6]
    assert len(details) == len(set(details)) == 31
    assert {p["id"] for p in payload["projects"]} == {p["id"] for p in listings}
    assert payload["meta"]["candidates"] == payload["meta"]["details_checked"] == 31
    assert payload["meta"]["market_coins_scanned"] == 1250


async def test_volume_cutoff_finishes_scan_without_requesting_later_pages():
    requests = []
    listings = [{"id": f"excluded-{i}", "total_volume": 50_000} for i in range(250)]

    def upstream(request):
        requests.append(request)
        assert request.url.path.endswith("/markets")
        return httpx.Response(200, json=listings)

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        payload = await terminal_payload(client)

    assert len(requests) == 1
    assert payload["projects"] == []
    assert payload["meta"]["market_coins_scanned"] == 250
    assert payload["meta"]["details_checked"] == 0


async def test_polling_is_nonblocking_and_never_duplicates_an_inflight_scan(make_coin):
    first, first_detail = make_coin("first")
    last, last_detail = make_coin("last")
    last_started = asyncio.Event()
    allow_last = asyncio.Event()
    requests = []

    async def upstream(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/markets"):
            return httpx.Response(200, json=[first, last])
        if request.url.path.endswith("/first"):
            return httpx.Response(200, json=first_detail)
        last_started.set()
        await allow_last.wait()
        return httpx.Response(200, json=last_detail)

    app = create_app(settings(), httpx.MockTransport(upstream))
    async with client_for(app) as client:
        initial = await client.get("/api/projects")
        assert initial.json()["meta"]["status"] == "scanning"
        async with asyncio.timeout(2):
            await last_started.wait()
            polls = await asyncio.gather(*(client.get("/api/projects") for _ in range(8)))
        for response in polls:
            payload = response.json()
            assert payload["meta"]["status"] == "scanning"
            assert payload["meta"]["phase"] == "details"
            assert payload["meta"]["details_checked"] == 1
            assert payload["meta"]["candidates"] == 2
        assert len(requests) == 3
        allow_last.set()
        payload = await terminal_payload(client)

    assert payload["meta"]["details_checked"] == 2
    assert len(payload["projects"]) == 2
    assert len(requests) == 3


@pytest.mark.parametrize(("failure", "message"), [
    (401, "denied access"),
    (500, "Unable to read"),
    ("timeout", "timed out"),
    ("invalid-json", "Unable to read"),
    ("invalid-shape", "unexpected markets"),
])
async def test_upstream_errors_are_explicit_private_and_retried_only_on_request(failure, message):
    calls = 0
    recovered_upstream = False

    def upstream(request):
        nonlocal calls
        calls += 1
        if recovered_upstream:
            return httpx.Response(200, json=[])
        if failure == "timeout":
            raise httpx.ReadTimeout("contains a secret upstream URL", request=request)
        if failure == "invalid-json":
            return httpx.Response(200, text="not JSON")
        if failure == "invalid-shape":
            return httpx.Response(200, json={"message": "bad response"})
        return httpx.Response(failure, text="test-secret", headers={"Retry-After": "0"})

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        failed = await terminal_payload(client, status="error")
        assert message in str(failed["meta"]["error"])
        assert "test-secret" not in str(failed)
        assert "secret upstream URL" not in str(failed)
        repeated = (await client.get("/api/projects")).json()
        assert repeated["meta"]["status"] == "error"
        failed_calls = 3 if failure == 500 else 1
        assert calls == failed_calls
        recovered_upstream = True
        retry = await client.get("/api/projects?retry=true")
        assert retry.status_code == 200
        recovered = await terminal_payload(client)

    assert recovered["projects"] == []
    assert calls == failed_calls + 1


async def test_failed_detail_retry_preserves_progress_without_rechecking_successes(make_coin):
    first, first_detail = make_coin("first")
    last, last_detail = make_coin("last")
    requests = []
    fail_last = True

    def upstream(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/markets"):
            return httpx.Response(200, json=[first, last])
        if request.url.path.endswith("/first"):
            return httpx.Response(200, json=first_detail)
        if fail_last:
            return httpx.Response(500, text="private upstream response", headers={"Retry-After": "0"})
        return httpx.Response(200, json=last_detail)

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        failed = await terminal_payload(client, status="error")
        assert failed["meta"]["details_checked"] == 1
        assert [p["id"] for p in failed["projects"]] == ["first"]
        fail_last = False
        await client.get("/api/projects?retry=true")
        complete = await terminal_payload(client)

    assert complete["meta"]["details_checked"] == 2
    assert {p["id"] for p in complete["projects"]} == {"first", "last"}
    assert sum(p.endswith("/markets") for p in requests) == 1
    assert sum(p.endswith("/first") for p in requests) == 1
    assert sum(p.endswith("/last") for p in requests) == 4


async def test_wrong_detail_identity_is_a_scan_error(make_coin):
    listing, snapshot = make_coin("requested")
    snapshot["id"] = "different-project"

    def upstream(request):
        return httpx.Response(200, json=[listing] if request.url.path.endswith("/markets") else snapshot)

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        payload = await terminal_payload(client, status="error")
    assert "unexpected coin details" in str(payload["meta"]["error"])
    assert payload["meta"]["details_checked"] == 0
    assert payload["projects"] == []


async def test_rate_limit_retries_the_same_request_then_succeeds():
    calls = 0

    def upstream(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[])

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        payload = await terminal_payload(client)

    assert payload["projects"] == []
    assert calls == 2


async def test_rate_limit_retries_are_bounded_and_failure_is_not_complete():
    requests = []

    def upstream(request):
        requests.append(request)
        return httpx.Response(429, headers={"Retry-After": "0"}, text="private response")

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        payload = await terminal_payload(client, status="error")
        assert "rate limit" in payload["meta"]["error"]
        assert payload["meta"]["phase"] == "markets"
        assert payload["meta"]["market_coins_scanned"] == 0
        assert (await client.get("/api/projects")).json()["meta"]["status"] == "error"

    assert len(requests) == 3


@pytest.mark.parametrize(("header", "expected"), [("1000000", 60), ("-5", 0), ("0", 0), (None, 2), ("invalid", 2)])
async def test_retry_after_delay_is_safe_and_bounded(header, expected):
    assert CoinGeckoClient._retry_delay(header, attempt=1) == expected


async def test_rejected_real_candidates_are_diagnostic_only_and_counts_cover_all(make_coin):
    listings, details = zip(*(make_coin(f"rejected-{i}") for i in range(12)))
    for i, snapshot in enumerate(details):
        if i % 2:
            snapshot["preview_listing"] = False
            snapshot["market_data"]["total_value_locked"] = {"usd": 50_000}
        else:
            del snapshot["preview_listing"]
            del snapshot["market_data"]["total_value_locked"]
    snapshots = {p["id"]: p for p in details}

    def upstream(request):
        if request.url.path.endswith("/markets"):
            return httpx.Response(200, json=list(listings))
        return httpx.Response(200, json=snapshots[request.url.path.rsplit("/", 1)[1]])

    async with client_for(create_app(settings(), httpx.MockTransport(upstream))) as client:
        payload = await terminal_payload(client)

    assert payload["projects"] == []
    assert payload["meta"]["details_checked"] == 12
    assert payload["meta"]["rejection_counts"] == {
        "preview_listing is false": 6,
        "preview_listing is missing": 6,
        "TVL is unavailable": 6,
        "TVL must exceed $50,000": 6,
    }
    assert len(payload["inspected_projects"]) == 10
    assert all(p["rejection_reasons"] for p in payload["inspected_projects"])
    assert payload["inspected_projects"][0]["preview_listing"] is None
    assert payload["inspected_projects"][0]["tvl"] is None
    assert payload["inspected_projects"][1]["preview_listing"] is False
    assert payload["inspected_projects"][1]["tvl"] == 50_000


async def test_completed_cache_expires_and_starts_a_fresh_background_scan(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("app.service.time.time", lambda: now[0])
    calls = 0

    def upstream(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, json=[])

    app = create_app(settings(cache_ttl_seconds=60), httpx.MockTransport(upstream))
    async with client_for(app) as client:
        await terminal_payload(client)
        now[0] += 59
        assert (await client.get("/api/projects")).json()["meta"]["status"] == "complete"
        assert calls == 1
        now[0] += 2
        assert (await client.get("/api/projects")).json()["meta"]["status"] == "scanning"
        await terminal_payload(client)

    assert calls == 2


async def test_completed_scan_survives_restart_without_more_api_calls(make_coin, tmp_path):
    listing, snapshot = make_coin("persisted")
    requests = []

    def upstream(request):
        requests.append(request.url.path)
        return httpx.Response(200, json=[listing] if request.url.path.endswith("/markets") else snapshot)

    config = settings(scan_cache_path=tmp_path / "scan.json")
    async with client_for(create_app(config, httpx.MockTransport(upstream))) as client:
        original = await terminal_payload(client)
    assert config.scan_cache_path.is_file()
    async with client_for(create_app(config, httpx.MockTransport(upstream))) as client:
        restored = (await client.get("/api/projects")).json()

    assert restored["meta"]["status"] == "complete"
    assert restored["meta"]["cached"] is True
    assert restored["meta"]["fetched_at"] == original["meta"]["fetched_at"]
    assert restored["projects"] == original["projects"]
    assert len(requests) == 2
    assert "test-secret" not in config.scan_cache_path.read_text()


async def test_restart_resumes_unfinished_details_and_preserves_supply_values(make_coin, tmp_path):
    first, first_detail = make_coin("first")
    last, last_detail = make_coin("last")
    last_started = asyncio.Event()
    last_cancelled = asyncio.Event()
    requests = []

    async def interrupted_upstream(request):
        requests.append(request.url.path)
        if request.url.path.endswith("/markets"):
            return httpx.Response(200, json=[first, last])
        if request.url.path.endswith("/first"):
            return httpx.Response(200, json=first_detail)
        last_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            last_cancelled.set()
            raise

    config = settings(scan_cache_path=tmp_path / "scan.json")
    async with client_for(create_app(config, httpx.MockTransport(interrupted_upstream))) as client:
        await client.get("/api/projects")
        async with asyncio.timeout(2):
            await last_started.wait()
    assert last_cancelled.is_set(), "lifespan shutdown must cancel the active HTTP request"

    def resumed_upstream(request):
        requests.append(request.url.path)
        assert request.url.path.endswith("/last"), "successful pages/details must not be fetched again"
        return httpx.Response(200, json=last_detail)

    async with client_for(create_app(config, httpx.MockTransport(resumed_upstream))) as client:
        restored = await terminal_payload(client)

    assert restored["meta"]["details_checked"] == 2
    assert {p["id"] for p in restored["projects"]} == {"first", "last"}
    assert all(p["total_supply"] == p["max_supply"] == 1_000_000 for p in restored["projects"])
    assert sum(p.endswith("/markets") for p in requests) == 1
    assert sum(p.endswith("/first") for p in requests) == 1
    assert sum(p.endswith("/last") for p in requests) == 2


async def test_demo_is_explicit_and_never_calls_external_api():
    def upstream(request):
        pytest.fail(f"Demo must not send an upstream request: {request.url.path}")

    async with client_for(create_app(settings(data_mode="demo"), httpx.MockTransport(upstream))) as client:
        assert (await client.get("/api/health")).json() == {"status": "ok", "mode": "demo"}
        response = await client.get("/api/projects")

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"]["status"] == "complete"
    assert payload["meta"]["mode"] == "demo"
    assert "Synthetic" in payload["meta"]["warnings"][0]
    assert payload["projects"]
    assert all(p["preview_listing"] is True and p["tvl"] > 50_000 for p in payload["projects"])
