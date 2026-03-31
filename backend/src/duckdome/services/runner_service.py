# DEPRECATED: This module uses one-shot subprocess.run and will be removed.
# See duckdome.wrapper for the persistent process replacement.
from __future__ import annotations

import logging
import time

from duckdome.models.run import RunRecord
from duckdome.models.trigger import Trigger
from duckdome.runner.context import build_context, RunContext
from duckdome.runner.base import RunResult
from duckdome.runner.factory import get_executor
from duckdome.services.trigger_service import TriggerService
from duckdome.services.message_service import MessageService
from duckdome.stores.base import BaseChannelStore
from duckdome.stores.message_store import MessageStore


log = logging.getLogger(__name__)


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
        """Claim next trigger, build context, run agent, post response."""

        # 1. Claim
        log.info("[%s] claim_trigger channel=%s", agent_type, channel_id)
        trigger = self._triggers.claim_trigger(channel_id, agent_type)
        if trigger is None:
            log.info("[%s] no claimable trigger for channel=%s", agent_type, channel_id)
            return None

        log.info("[%s] claimed trigger=%s", agent_type, trigger.id)

        run = RunRecord(
            trigger_id=trigger.id,
            channel_id=channel_id,
            agent_type=agent_type,
        )

        try:
            # 2. Build context
            ctx = build_context(trigger, self._channels, self._msg_store)

            # 3. Execute
            log.info("[%s] executing runner...", agent_type)
            result = get_executor(agent_type).execute(ctx)

            run.ended_at = time.time()
            run.duration_ms = result.duration_ms
            run.exit_code = result.exit_code

            log.info(
                "[%s] exit_code=%d duration=%dms stdout=%d bytes stderr=%d bytes",
                agent_type, result.exit_code, result.duration_ms,
                len(result.stdout), len(result.stderr),
            )

            if result.exit_code == 0 and result.stdout.strip():
                # 4. Post response
                self._messages.send(
                    text=result.stdout.strip(),
                    channel=channel_id,
                    sender=agent_type,
                )
                # 5. Complete trigger
                self._triggers.complete_trigger(trigger.id)
                log.info("[%s] trigger completed", agent_type)
            else:
                error = result.stderr.strip() or f"exit code {result.exit_code}"
                run.error_summary = error[:500]
                self._triggers.fail_trigger(trigger.id, error[:500])
                log.info("[%s] trigger failed (exit_code=%d)", agent_type, result.exit_code)

        except Exception as e:
            run.ended_at = time.time()
            run.duration_ms = int((run.ended_at - run.started_at) * 1000)
            run.exit_code = -99
            run.error_summary = str(e)[:500]
            self._triggers.fail_trigger(trigger.id, str(e)[:500])
            log.exception("[%s] runner exception", agent_type)

        return run
