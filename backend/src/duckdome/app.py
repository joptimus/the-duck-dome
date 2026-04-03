from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send

from duckdome.routes.health import router as health_router
from duckdome.routes import messages as messages_mod
from duckdome.routes import deliveries as deliveries_mod
from duckdome.routes import channels as channels_mod
from duckdome.routes import triggers as triggers_mod
from duckdome.routes import runners as runners_mod
from duckdome.routes import tool_approvals as tool_approvals_mod
from duckdome.routes import jobs as jobs_mod
from duckdome.routes import rules as rules_mod
from duckdome.routes import repos as repos_mod
from duckdome.routes import websocket as websocket_mod
from duckdome.routes import wrapper as wrapper_mod
from duckdome.routes import settings as settings_mod
from duckdome.bridges import hooks_router
from duckdome.services.wrapper_service import WrapperService
from duckdome.services.channel_service import ChannelService
from duckdome.services.job_service import JobService
from duckdome.services.repo_service import RepoService
from duckdome.services.message_service import MessageService
from duckdome.services.trigger_service import TriggerService
from duckdome.services.runner_service import RunnerService
from duckdome.services.rule_service import RuleService
from duckdome.services.tool_approval_service import ToolApprovalService
from duckdome.stores.channel_store import ChannelStore
from duckdome.stores.job_store import JobStore
from duckdome.stores.repo_store import RepoStore
from duckdome.stores.message_store import MessageStore
from duckdome.stores.rule_store import RuleStore
from duckdome.stores.tool_approval_store import ToolApprovalStore
from duckdome.stores.trigger_store import TriggerStore
from duckdome.stores.settings_store import SettingsStore
from duckdome.ws import ConnectionManager

DEV_ORIGINS = [
    "http://localhost:5173",
]


class _WsPassthrough:
    """Wrap CORSMiddleware so WebSocket upgrades skip CORS checks entirely."""

    def __init__(self, app: ASGIApp) -> None:
        self._cors = CORSMiddleware(
            app,
            allow_origins=DEV_ORIGINS,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "websocket":
            await self._app(scope, receive, send)
        else:
            await self._cors(scope, receive, send)


DEFAULT_AGENTS = ["claude", "codex", "gemini"]


def create_app(data_dir: Path | None = None) -> FastAPI:
    if data_dir is None:
        data_dir = Path.home() / ".duckdome" / "data"

    app = FastAPI(title="DuckDome")
    app.add_middleware(_WsPassthrough)

    # Stores
    message_store = MessageStore(data_dir=data_dir)
    channel_store = ChannelStore(data_dir=data_dir)
    trigger_store = TriggerStore(data_dir=data_dir)
    tool_approval_store = ToolApprovalStore(data_dir=data_dir)
    rule_store = RuleStore(data_dir=data_dir)
    job_store = JobStore(data_dir=data_dir)
    repo_store = RepoStore(data_dir=data_dir)
    settings_store = SettingsStore(data_dir=data_dir)

    # WebSocket manager
    ws_manager = ConnectionManager()

    # Services
    channel_service = ChannelService(store=channel_store)
    trigger_service = TriggerService(
        trigger_store=trigger_store,
        channel_store=channel_store,
        ws_manager=ws_manager,
    )
    message_service = MessageService(
        store=message_store,
        known_agents=DEFAULT_AGENTS,
        channel_service=channel_service,
        trigger_service=trigger_service,
        ws_manager=ws_manager,
    )
    trigger_service.set_message_service(message_service)
    tool_approval_service = ToolApprovalService(
        store=tool_approval_store,
        ws_manager=ws_manager,
    )
    rule_service = RuleService(store=rule_store)
    job_service = JobService(store=job_store, ws_manager=ws_manager)
    repo_service = RepoService(store=repo_store)

    runner_service = RunnerService(
        trigger_service=trigger_service,
        message_service=message_service,
        channel_store=channel_store,
        message_store=message_store,
    )

    wrapper_service = WrapperService(
        data_dir=data_dir,
        tool_approval_service=tool_approval_service,
        ws_manager=ws_manager,
    )

    # Apply persisted settings to services before routes are ready
    if settings_store.get("show_agent_windows"):
        wrapper_service.set_show_windows(True)

    # Init routes with dependencies
    settings_mod.init(settings_store, wrapper_service=wrapper_service)
    messages_mod.init(message_service)
    deliveries_mod.init(message_service)
    channels_mod.init(
        channel_service,
        wrapper_service=wrapper_service,
        message_store=message_store,
        ws_manager=ws_manager,
    )
    triggers_mod.init(trigger_service)
    runners_mod.init(runner_service)
    wrapper_mod.init(wrapper_service, channel_service=channel_service)
    tool_approvals_mod.init(tool_approval_service)
    rules_mod.init(rule_service)
    jobs_mod.init(job_service)
    repos_mod.init(repo_service)
    websocket_mod.init(ws_manager)

    # Expose services on app.state for MCP bridge wiring
    app.state.message_service = message_service
    app.state.rule_service = rule_service
    app.state.trigger_service = trigger_service
    app.state.wrapper_service = wrapper_service

    # Register routers
    app.include_router(health_router)
    app.include_router(messages_mod.router)
    app.include_router(deliveries_mod.router)
    app.include_router(channels_mod.router)
    app.include_router(triggers_mod.router)
    app.include_router(runners_mod.router)
    app.include_router(wrapper_mod.router)
    app.include_router(tool_approvals_mod.router)
    app.include_router(rules_mod.router)
    app.include_router(jobs_mod.router)
    app.include_router(repos_mod.router)
    app.include_router(websocket_mod.router)
    app.include_router(settings_mod.router)
    app.include_router(hooks_router)

    return app
