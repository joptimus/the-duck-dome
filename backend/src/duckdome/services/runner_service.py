from __future__ import annotations

import time

from duckdome.models.run import RunRecord
from duckdome.models.trigger import Trigger
from duckdome.runner.context import build_context, RunContext
from duckdome.runner.claude import execute as claude_execute, RunResult
from duckdome.services.trigger_service import TriggerService
from duckdome.services.message_service import MessageService
from duckdome.stores.base import BaseChannelStore
from duckdome.stores.message_store import MessageStore


class RunnerService:
    def __init__(
        self,
        trigger_service: TriggerService,
        message_service: MessageService,
        channel_store: BaseChannelStore,
        message_store: MessageStore,
    ) -> None:
        self._triggers = trigger_service
        self._messages = message_service
        self._channels = channel_store
        self._msg_store = message_store

    def execute_next(
        self, channel_id: str, agent_type: str = "claude"
    ) -> RunRecord | None:
        """Claim next trigger, build context, run Claude, post response."""

        # 1. Claim
        trigger = self._triggers.claim_trigger(channel_id, agent_type)
        if trigger is None:
            return None

        run = RunRecord(
            trigger_id=trigger.id,
            channel_id=channel_id,
            agent_type=agent_type,
        )

        try:
            # 2. Build context
            ctx = build_context(trigger, self._channels, self._msg_store)

            # 3. Execute
            result = claude_execute(ctx)

            run.ended_at = time.time()
            run.duration_ms = result.duration_ms
            run.exit_code = result.exit_code

            if result.exit_code == 0 and result.stdout.strip():
                # 4. Post response
                self._messages.send(
                    text=result.stdout.strip(),
                    channel=channel_id,
                    sender=agent_type,
                )
                # 5. Complete trigger
                self._triggers.complete_trigger(trigger.id)
            else:
                error = result.stderr.strip() or f"exit code {result.exit_code}"
                run.error_summary = error[:500]
                self._triggers.fail_trigger(trigger.id, error[:500])

        except Exception as e:
            run.ended_at = time.time()
            run.duration_ms = int((run.ended_at - run.started_at) * 1000)
            run.exit_code = -99
            run.error_summary = str(e)[:500]
            self._triggers.fail_trigger(trigger.id, str(e)[:500])

        return run
