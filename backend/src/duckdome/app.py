from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from duckdome.routes.health import router as health_router

DEV_ORIGINS = [
    "http://localhost:5173",
]


def create_app() -> FastAPI:
    app = FastAPI(title="DuckDome")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    return app
