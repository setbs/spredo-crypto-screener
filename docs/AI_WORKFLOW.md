# AI workflow

## Submission form draft

I used ChatGPT/Codex to turn the requirements into a small FastAPI and React application, check the CoinGecko field mappings against the official documentation, implement the API and UI, and write tests and setup instructions. Parallel AI tasks covered the frontend, API research, and backend tests. AI helped most with quickly identifying that preview status and TVL require per-coin detail requests, and with covering strict threshold and missing-data cases.

The generated implementation was reviewed for correct filtering, separation of frontend/backend responsibilities, request volume, caching, and honest handling of empty results and synthetic fixtures. Automated checks cover the filtering rules, mocked CoinGecko integration, and frontend search/filter/sort behavior. The frontend build also checks TypeScript.

Validation performed with AI assistance: 44 backend tests and 9 frontend tests passed, the production frontend build succeeded, and a browser smoke check verified the Python-served interface at desktop and mobile widths. A real CoinGecko market request succeeded, but a full unauthenticated scan hit the upstream rate limit; that limitation is documented.

## Human review — complete before submitting

The paragraph above describes AI-assisted development and automated review. It does **not** claim that the candidate has already reviewed or tested anything manually. After doing the following checks, add one sentence to the form describing what you personally reviewed or corrected:

- Start the Python backend and React frontend using the README.
- Try demo mode: search `eth`, lower the FDV limit, and sort both numeric columns.
- Inspect `backend/app/filters.py`, especially strict comparisons and the preview flag.
- Read the coverage and preview-listing limitations in the README.
- If you have a CoinGecko key, try live mode and inspect the returned metadata.

Report any unverified live behavior accurately. Do not claim an exhaustive market scan or real data in demo mode.
