"""HTTP hook receiver for Claude Code agents.

Exposes a FastAPI router that Claude Code POSTs hook events to.  The
receiver routes events to the appropriate ClaudeBridge instance via a
registry keyed by agent_id (passed as a query parameter).
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/hooks", tags=["hooks"])

# agent_id → callback that returns a hook response dict
_JsonDict = dict[str, Any]
HookHandler = Callable[[str, _JsonDict], _JsonDict]
_handlers: dict[str, HookHandler] = {}


def register_hook_handler(agent_id: str, handler: HookHandler) -> None:
    """Register a ClaudeBridge as the handler for a given agent's hooks."""
    _handlers[agent_id] = handler


def unregister_hook_handler(agent_id: str) -> None:
    """Remove the handler when the agent stops."""
    _handlers.pop(agent_id, None)


@router.post("/claude")
async def receive_claude_hook(
    request: Request,
    agent: str = Query(..., description="Agent ID"),
) -> JSONResponse:
    """Receive a hook event from Claude Code.

    Claude Code POSTs the hook input as JSON.  For sync hooks
    (PreToolUse, PermissionRequest) the response body is interpreted
    as the hook output — it can approve, block, or modify the action.
    For async hooks the response is ignored by the CLI.
    """
    try:
        body = await request.json()
    except Exception:
        logger.warning("Invalid JSON in hook POST from agent %s", agent)
        return JSONResponse({}, status_code=400)

    handler = _handlers.get(agent)
    if handler is None:
        logger.warning("Hook received for unknown agent %s", agent)
        return JSONResponse({})

    hook_event = body.get("hook_event_name", "")
    logger.debug("Hook %s from agent %s", hook_event, agent)

    try:
        response = handler(hook_event, body)
    except Exception:
        logger.exception("Hook handler error for agent %s event %s", agent, hook_event)
        response = {}

    return JSONResponse(response)
