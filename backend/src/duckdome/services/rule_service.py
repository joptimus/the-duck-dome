from __future__ import annotations

from duckdome.models.rule import Rule, RuleStatus
from duckdome.stores.rule_store import RuleStore


class RuleService:
    def __init__(self, store: RuleStore) -> None:
        self._store = store

    def get(self, rule_id: str) -> Rule | None:
        return self._store.get(rule_id)

    def propose(self, text: str, author: str | None = None, reason: str | None = None) -> Rule:
        rule = Rule(text=text, author=author, reason=reason)
        return self._store.add(rule)

    def edit(self, rule_id: str, text: str) -> Rule | None:
        rule = self._store.get(rule_id)
        if rule is None:
            return None
        updated = rule.model_copy(update={"text": text})
        return self._store.update(rule_id, updated)

    def activate(self, rule_id: str) -> Rule | None:
        rule = self._store.get(rule_id)
        if rule is None:
            return None
        if rule.status == RuleStatus.ACTIVE:
            return rule
        rule.status = RuleStatus.ACTIVE
        return self._store.update(rule_id, rule)

    def deactivate(self, rule_id: str) -> Rule | None:
        rule = self._store.get(rule_id)
        if rule is None:
            return None
        if rule.status == RuleStatus.ARCHIVE:
            return rule
        rule.status = RuleStatus.ARCHIVE
        return self._store.update(rule_id, rule)

    def list_active(self) -> list[Rule]:
        return self._store.list_by_status(RuleStatus.ACTIVE)

    def list_all(self) -> list[Rule]:
        return self._store.list_all()

    def get_epoch(self) -> int:
        return self._store.epoch
