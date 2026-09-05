from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from oscarius import __version__
from oscarius.api.routes import router

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app() -> FastAPI:
    """Creates and configures the Oscarius FastAPI instance."""
    app = FastAPI(
        title="Oscarius API",
        description="Web backend and API for OSCAR sleep therapy and CPAP data analysis.",
        version=__version__,
    )

    # Enable CORS for local web development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok", "version": __version__}

    app.include_router(router)

    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")

    return app


app = create_app()
