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


def build_prompt(ctx: RunContext) -> str:
    """Build a short prompt envelope for Claude CLI."""
    lines: list[str] = []

    if ctx.channel.channel_type == "repo" and ctx.channel.repo_path:
        lines.append(
            f"You are Claude, running as a DuckDome channel-scoped assistant "
            f"in repo channel #{ctx.channel.channel_name}."
        )
        lines.append(f"Working directory: {ctx.channel.repo_path}")
        if ctx.repo_preflight and not ctx.repo_preflight.valid:
            lines.append(f"Warning: repo preflight failed — {ctx.repo_preflight.error}")
        lines.append(
            "For repo channels, do not modify files unless the task clearly asks for it."
        )
    else:
        lines.append(
            f"You are Claude, running as a DuckDome channel-scoped assistant "
            f"in general channel #{ctx.channel.channel_name}."
        )
        lines.append("This is a discussion/planning channel with no repo binding.")

    lines.append("")

    if ctx.history:
        lines.append("Recent conversation:")
        for h in ctx.history:
            lines.append(f"  [{h['sender']}]: {h['text']}")
        lines.append("")

    lines.append(f"[{ctx.trigger.sender}]: {ctx.trigger.text}")
    lines.append("")
    lines.append(
        "Make progress when possible. State assumptions if needed. "
        "Ask one focused follow-up only when blocked."
    )

    return "\n".join(lines)
