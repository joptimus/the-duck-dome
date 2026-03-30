# DEPRECATED: This module uses one-shot subprocess.run and will be removed.
# See duckdome.wrapper for the persistent process replacement.
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from duckdome.models.channel import Channel, ChannelType
from duckdome.models.message import Message
from duckdome.models.trigger import Trigger
from duckdome.stores.message_store import MessageStore
from duckdome.stores.base import BaseChannelStore

HISTORY_LIMIT = 12


@dataclass
class TriggerContext:
    source_message_id: str
    sender: str
    text: str
    timestamp: float


@dataclass
class ChannelContext:
    channel_id: str
    channel_name: str
    channel_type: str
    repo_path: str | None = None


@dataclass
class RepoPreflightResult:
    valid: bool
    path: str
    error: str | None = None


@dataclass
class RunContext:
    channel: ChannelContext
    trigger: TriggerContext
    history: list[dict] = field(default_factory=list)
    repo_preflight: RepoPreflightResult | None = None


def build_context(
    trigger: Trigger,
    channel_store: BaseChannelStore,
    message_store: MessageStore,
) -> RunContext:
    channel = channel_store.get_channel(trigger.channel_id)
    if channel is None:
        raise ValueError(f"Channel not found: {trigger.channel_id}")

    source_msg = message_store.get(trigger.source_message_id)
    if source_msg is None:
        raise ValueError(f"Source message not found: {trigger.source_message_id}")
    if source_msg.channel != trigger.channel_id:
        raise ValueError(
            f"Source message channel mismatch: message in {source_msg.channel}, "
            f"trigger in {trigger.channel_id}"
        )

    channel_ctx = ChannelContext(
        channel_id=channel.id,
        channel_name=channel.name,
        channel_type=channel.type,
        repo_path=channel.repo_path,
    )

    trigger_ctx = TriggerContext(
        source_message_id=source_msg.id,
        sender=source_msg.sender,
        text=source_msg.text,
        timestamp=source_msg.timestamp,
    )

    # Bounded recent history (last 12 messages before the trigger message)
    all_msgs = message_store.list_by_channel(channel.id)
    history: list[dict] = []
    for msg in all_msgs:
        if msg.id == source_msg.id:
            break
        history.append({
            "sender": msg.sender,
            "text": msg.text,
            "timestamp": msg.timestamp,
        })
    history = history[-HISTORY_LIMIT:]

    repo_preflight = None
    if channel.type == ChannelType.REPO and channel.repo_path:
        repo_preflight = _repo_preflight(channel.repo_path)

    return RunContext(
        channel=channel_ctx,
        trigger=trigger_ctx,
        history=history,
        repo_preflight=repo_preflight,
    )


def _repo_preflight(repo_path: str) -> RepoPreflightResult:
    p = Path(repo_path)
    if not p.is_dir():
        return RepoPreflightResult(valid=False, path=repo_path, error="directory does not exist")
    if not (p / ".git").exists():
        return RepoPreflightResult(valid=False, path=repo_path, error="not a git repository")
    return RepoPreflightResult(valid=True, path=repo_path)


def build_system_context(ctx: RunContext) -> str:
    """Build system context for the agent (channel info, history, instructions)."""
    lines: list[str] = []

    if ctx.channel.channel_type == "repo" and ctx.channel.repo_path:
        lines.append(f"You are responding in DuckDome repo channel #{ctx.channel.channel_name}.")
        lines.append(f"Working directory: {ctx.channel.repo_path}")
        if ctx.repo_preflight and not ctx.repo_preflight.valid:
            lines.append(f"Warning: repo preflight failed — {ctx.repo_preflight.error}")
    else:
        lines.append(f"You are responding in DuckDome general channel #{ctx.channel.channel_name}.")
        lines.append("This channel has no repo binding.")

    lines.append("")

    if ctx.history:
        lines.append("Recent conversation:")
        for h in ctx.history:
            lines.append(f"  [{h['sender']}]: {h['text']}")
        lines.append("")

    lines.append(
        "Respond directly to the user's message. Do not introduce yourself. "
        "Do not ask what you can help with. Act on the request immediately. "
        "If you need clarification, ask one specific question."
    )

    return "\n".join(lines)


def build_user_message(ctx: RunContext) -> str:
    """Extract the user's actual message text."""
    return ctx.trigger.text


# Backward-compatible: single combined prompt for agents that don't support
# separate system/user messages (e.g. codex, gemini).
def build_prompt(ctx: RunContext) -> str:
    """Build a combined prompt envelope for CLI agents."""
    return build_system_context(ctx) + "\n\n" + build_user_message(ctx)
