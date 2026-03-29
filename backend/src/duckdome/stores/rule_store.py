from __future__ import annotations

import json
import os
from pathlib import Path

from duckdome.models.rule import Rule, RuleStatus


class RuleStore:
    """JSONL-backed rule store with epoch versioning."""

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._file = self._data_dir / "rules.jsonl"
        self._rules: dict[str, Rule] = {}
        self._order: list[str] = []
        self._epoch: int = 0
        self._load()

    def _load(self) -> None:
        if not self._file.exists():
            return
        with open(self._file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rule = Rule(**json.loads(line))
                self._rules[rule.id] = rule
                if rule.id not in self._order:
                    self._order.append(rule.id)

    def _rewrite(self) -> None:
        tmp = self._file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for rule_id in self._order:
                f.write(self._rules[rule_id].model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp.rename(self._file)

    def _append(self, rule: Rule) -> None:
        with open(self._file, "a", encoding="utf-8") as f:
            f.write(rule.model_dump_json() + "\n")
            f.flush()
            os.fsync(f.fileno())

    @property
    def epoch(self) -> int:
        return self._epoch

    def add(self, rule: Rule) -> Rule:
        if rule.id in self._rules:
            return self._rules[rule.id]
        self._rules[rule.id] = rule
        self._order.append(rule.id)
        self._append(rule)
        self._epoch += 1
        return rule

    def get(self, rule_id: str) -> Rule | None:
        return self._rules.get(rule_id)

    def update(self, rule_id: str, rule: Rule) -> Rule | None:
        if rule_id not in self._rules:
            return None
        self._rules[rule_id] = rule
        self._rewrite()
        self._epoch += 1
        return rule

    def list_all(self) -> list[Rule]:
        return [self._rules[rid] for rid in self._order]

    def list_by_status(self, status: RuleStatus) -> list[Rule]:
        return [self._rules[rid] for rid in self._order if self._rules[rid].status == status]
