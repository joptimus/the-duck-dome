from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from duckdome.routes.health import router as health_router
from duckdome.routes import messages as messages_mod
from duckdome.routes import deliveries as deliveries_mod
from duckdome.routes import channels as channels_mod
from duckdome.routes import triggers as triggers_mod
from duckdome.routes import runners as runners_mod
from duckdome.routes import websocket as websocket_mod
from duckdome.services.channel_service import ChannelService
from duckdome.services.message_service import MessageService
from duckdome.services.trigger_service import TriggerService
from duckdome.services.runner_service import RunnerService
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.message_store import MessageStore
from duckdome.stores.trigger_store import TriggerStore
from duckdome.ws import ConnectionManager

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
    message_store = MessageStore(data_dir=data_dir)
    channel_store = ChannelStore(data_dir=data_dir)
    trigger_store = TriggerStore(data_dir=data_dir)

    # WebSocket manager
    ws_manager = ConnectionManager()

    # Services
    channel_service = ChannelService(store=channel_store)
    message_service = MessageService(
        store=message_store,
        known_agents=DEFAULT_AGENTS,
        channel_service=channel_service,
        ws_manager=ws_manager,
    )
    trigger_service = TriggerService(
        trigger_store=trigger_store,
        channel_store=channel_store,
        ws_manager=ws_manager,
    )

    runner_service = RunnerService(
        trigger_service=trigger_service,
        message_service=message_service,
        channel_store=channel_store,
        message_store=message_store,
    )

    # Init routes with dependencies
    messages_mod.init(message_service)
    deliveries_mod.init(message_service)
    channels_mod.init(channel_service)
    triggers_mod.init(trigger_service)
    runners_mod.init(runner_service)
    websocket_mod.init(ws_manager)

    # Register routers
    app.include_router(health_router)
    app.include_router(messages_mod.router)
    app.include_router(deliveries_mod.router)
    app.include_router(channels_mod.router)
    app.include_router(triggers_mod.router)
    app.include_router(runners_mod.router)
    app.include_router(websocket_mod.router)

    return app
