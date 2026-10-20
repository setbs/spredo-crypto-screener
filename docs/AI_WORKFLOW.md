# AI workflow

## Submission form draft

I used ChatGPT/Codex to turn the requirements into a small FastAPI and React application, check the CoinGecko field mappings against the official documentation, implement the API and UI, and write tests and setup instructions. Parallel AI tasks covered the frontend, API research, and backend tests. AI helped most with quickly identifying that preview status and TVL require per-coin detail requests, and with covering strict threshold and missing-data cases.

The generated implementation was reviewed for correct filtering, separation of frontend/backend responsibilities, request volume, caching, and honest handling of empty results. Review exposed a material limitation in the first version: it checked only a capped subset of candidates. This was replaced with a background scan that checks every relevant candidate, saves progress, and distinguishes scanning, completed, and error states. Real inspected examples and rejection counts make an empty result explainable without weakening the requested conditions.

Validation passed: 54 backend tests, 13 frontend tests, TypeScript checking, and the production build. A completed authenticated live scan retrieved 2,500 market listings and checked all 626 numeric candidates. All 626 had `preview_listing=false`, so no projects passed every requested condition. Browser checks verified real progress-to-completion polling, separate rejection diagnostics, and desktop/mobile layouts. The API key remains only in local server configuration. Captured counts and real inspected examples are in `docs/live-verification.json`.

## Human review — complete before submitting

The paragraph above describes AI-assisted development and automated review. It does **not** claim that the candidate has already reviewed or tested anything manually. After doing the following checks, add one sentence to the form describing what you personally reviewed or corrected:

- Start the Python backend and React frontend using the README.
- Try demo mode: search `eth`, lower the FDV limit, and sort both numeric columns.
- Inspect `backend/app/filters.py`, especially strict comparisons and the preview flag.
- Read the coverage and preview-listing limitations in the README.
- With a CoinGecko key, try live mode, wait for `meta.status=complete`, and inspect the coverage and rejection diagnostics.

Report any unverified live behavior accurately. Do not claim an exhaustive market scan or real data in demo mode.
