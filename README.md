# Spredo · Crypto Screener

A small full-stack application: **Python / FastAPI** fetches and filters CoinGecko data; **React / TypeScript / Vite** displays it. The browser communicates only with the Python API.

![Completed real CoinGecko scan with rejection diagnostics](docs/screenshot.png)

## Run locally

Requires Python 3.11+, Node.js 22.12+ (or Node 24 LTS), npm, and optionally [uv](https://docs.astral.sh/uv/).

**1. Backend — terminal one**

```bash
cd backend
cp .env.example .env
uv sync --frozen
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The default is live CoinGecko data. Set `COINGECKO_API_KEY` in `backend/.env` to your free [Demo API key](https://docs.coingecko.com/demo/reference/authentication). Keys stay on the server. If using a paid key, also set `COINGECKO_API_TIER=pro`.

CoinGecko's **Demo API** is its free plan and serves real data. It is separate from this application's optional synthetic demo mode.

To explore a populated UI without an API key, set `DATA_MODE=demo` in `backend/.env` before starting the backend. This uses six **synthetic** projects and is visibly labelled in the UI and API. Live failures never fall back to demo data.

Without uv:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**2. Frontend — terminal two**

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to Python on port 8000, so no CORS configuration or client-side API key is needed. API documentation: http://127.0.0.1:8000/docs.

**Serve a production build with Python**

```bash
cd frontend
npm ci
npm run build
cd ../backend
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Build the frontend **before** starting Python; FastAPI mounts `frontend/dist` when the app starts.

## Completed

- REST endpoint `GET /api/projects` returns projects satisfying all six backend conditions, together with explicit scan progress.
- Full two-stage retrieval: paginate market data until the sorted volume reaches the threshold or the market list ends, then check details for **every** numeric candidate. There is no page or candidate cap.
- Exact supply comparison with `Decimal`; missing, malformed, Boolean, and non-finite numeric values are excluded.
- A single background task handles scanning; browser requests return promptly and poll progress. Progress is saved locally after each page and detail check and survives restarts.
- Completed scans are cached for one hour. Upstream calls are paced, have a 15-second timeout per call, and use bounded retries for transient failures.
- Search by partial project name or symbol, additional strict FDV ceiling, and market cap / 24h volume sorting in both directions.
- Responsive UI with progress, completed empty results, retry, and explicit demo states. A separate diagnostic table shows real inspected projects and their rejection reasons; rejected projects are never included in the qualifying list.
- Mocked backend integration tests and frontend filter/sort tests; locked dependencies.

## API

```bash
curl http://127.0.0.1:8000/api/health
curl http://127.0.0.1:8000/api/projects
```

`GET /api/projects` returns `{ "projects": [...], "inspected_projects": [...], "meta": {...} }`.

Each qualifying project includes `id`, `name`, `symbol`, `market_cap`, `fdv`, `volume_24h`, `tvl`, `max_supply`, `total_supply`, and `preview_listing`. All monetary values are USD.

The first request starts a background scan. While `meta.status` is `scanning`, clients poll this endpoint; any projects already found are provisional until the scan completes. `meta.phase` distinguishes market discovery from detail checks. `meta.status=complete` is returned only after all relevant pages and candidates have been processed. An empty list during scanning is not a final result.

`meta.rejection_counts` summarizes why checked candidates failed. `inspected_projects` contains up to ten real inspected examples for diagnosis, with nullable metrics, preview status, and rejection reasons. It is separate from the strictly filtered `projects` list.

If bounded upstream retries fail, `meta.status=error` and `meta.error` explain the problem. The saved progress remains available; `GET /api/projects?retry=true` resumes from the unfinished request. Ordinary polling does not repeatedly retry an errored scan or create duplicate scans.

## Assumptions and limitations

| Condition | CoinGecko detail field | Rule |
| --- | --- | --- |
| Market capitalization | `market_data.market_cap.usd` | `> 0` |
| Preview listing | `preview_listing` | Boolean `true` only |
| Supply | `market_data.max_supply`, `market_data.total_supply` | Both known, positive, and exactly equal |
| FDV | `market_data.fully_diluted_valuation.usd` | `>= 0` and `< 100,000,000` |
| 24h trading volume | `market_data.total_volume.usd` | `> 50,000` |
| TVL | `market_data.total_value_locked` | `> 50,000`; accepts a USD number or an object containing `usd` |

- [`/coins/markets`](https://docs.coingecko.com/demo/reference/coins-markets) does not include preview status or TVL; those come from [`/coins/{id}`](https://docs.coingecko.com/demo/reference/coins-id). Unknown values fail the filter. Equality is not treated as passing a strict threshold.
- **A valid live result can be empty.** CoinGecko [describes preview listings](https://support.coingecko.com/articles/2654097937-how-to-list-an-upcoming-token-preview-mode) as upcoming tokens. Such projects may have no reported trading activity, market cap, or TVL. The implementation keeps the requested `preview_listing == true` rule.
- **A cold scan can take several minutes.** All relevant market pages and all numeric candidates are checked. The UI displays progress throughout. There are no arbitrary 4-page or 25-candidate limits.
- The default request interval is 0.75 seconds with a key; keyless requests use at least 2.1 seconds. Shared-IP and monthly [CoinGecko quotas](https://docs.coingecko.com/docs/errors-and-rate-limits) still apply. Repeated transient failures pause the scan with an actionable error, preserving progress for an explicit retry.
- Run **one Python worker** for this exercise. Cache and progress are stored in ignored `backend/.cache/live-scan.json`; they contain project data, not API keys. A restart resumes unfinished work. After the one-hour cache expires, a new request starts a fresh scan. There is no database or separate worker service.
- Market and detail responses are not an atomic snapshot; values can change during a scan. All six rules are rechecked on each detail response before accepting a project. Unknown or invalid fields fail closed.
- Search/filter/sort operate locally over the already filtered response, so typing never causes additional CoinGecko requests. The UI cannot relax the backend's $100M FDV limit.

## Checks

```bash
cd backend
uv sync --frozen
uv run pytest -q
cd ../frontend
npm ci
npm test
npm run build
```

The backend tests mock CoinGecko; they require no key and do not consume API quota. `npm run build` includes TypeScript checking.

**54 backend tests and 13 frontend tests pass**, and the production build succeeds. Tests cover strict thresholds, all-candidate scanning, background progress, shared refreshes, persistence/resume, errors, and frontend search/filter/sort behavior. Browser checks covered progress-to-completion polling, retry, search/filter/sort, real diagnostics, and mobile layout.

**Completed live verification on 2026-10-20:** an authenticated scan retrieved 2,500 market listings, discovered 626 numeric candidates, and checked **all 626** candidates. Every candidate had `preview_listing=false`, so zero projects met all six requested conditions. Both truncation flags were false and no error occurred. The browser displayed completion and real rejected-project examples. See the [captured verification report](docs/live-verification.json) and screenshot above. The API key is not included in the repository.

## Structure

```text
backend/
  app/main.py       FastAPI routes and application lifecycle
  app/coingecko.py  Upstream requests, pacing, safe errors
  app/filters.py    Pure normalization and filtering functions
  app/service.py    Background scan, persisted progress, completed response cache
  data/demo.json    Explicit synthetic fixtures
  tests/           Filter and mocked API tests
frontend/
  src/             React UI, typed API contract, view filters and tests
docs/
  AI_WORKFLOW.md    AI usage notes for the submission form
  REVIEW_GUIDE_RU.md  Short explanation for the candidate
```

With more time I would add a shared database/cache for multiple workers, scheduled refreshes, and a committed browser regression suite. I would also confirm with the task author whether `preview_listing == true` is intentional given its meaning.

AI assisted this implementation; see [workflow notes](docs/AI_WORKFLOW.md).
