from fastapi import FastAPI
from duckdome.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="DuckDome")
    app.include_router(health_router)
    return app
