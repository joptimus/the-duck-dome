from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from duckdome.routes.health import router as health_router
from duckdome.routes import messages as messages_mod
from duckdome.routes import deliveries as deliveries_mod
from duckdome.services.message_service import MessageService
from duckdome.stores.message_store import MessageStore

DEV_ORIGINS = [
    "http://localhost:5173",
]

DEFAULT_AGENTS = ["claude", "codex", "gemini"]


def create_app(data_dir: Path | None = None) -> FastAPI:
    if data_dir is None:
        data_dir = Path.home() / ".duckdome" / "data"

    app = FastAPI(title="DuckDome")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEV_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Stores
    store = MessageStore(data_dir=data_dir)

    # Services
    message_service = MessageService(store=store, known_agents=DEFAULT_AGENTS)

    # Init routes with dependencies
    messages_mod.init(message_service)
    deliveries_mod.init(message_service)

    # Register routers
    app.include_router(health_router)
    app.include_router(messages_mod.router)
    app.include_router(deliveries_mod.router)

    return app
