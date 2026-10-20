from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from .coingecko import CoinGeckoClient, UpstreamError
from .config import Settings
from .models import ProjectsResponse
from .service import ProjectService


def create_app(settings: Settings | None = None, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(
            base_url=settings.api_url, timeout=15.0, transport=transport,
        ) as http:
            app.state.projects = ProjectService(CoinGeckoClient(http, settings), settings)
            yield

    app = FastAPI(title="Spredo Crypto Screener", version="0.1.0", lifespan=lifespan)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": settings.data_mode}

    @app.get("/api/projects", response_model=ProjectsResponse)
    async def projects(request: Request) -> ProjectsResponse:
        try:
            return await request.app.state.projects.get_projects()
        except UpstreamError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    # After `npm run build`, Python can serve both UI and API on one origin.
    frontend = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if frontend.is_dir():
        app.mount("/", StaticFiles(directory=frontend, html=True), name="frontend")
    return app


app = create_app()
