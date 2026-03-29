import pytest

from duckdome.models.rule import Rule, RuleStatus
from duckdome.stores.rule_store import RuleStore
from duckdome.services.rule_service import RuleService


# --- Model tests ---

def test_rule_defaults():
    rule = Rule(text="Be concise")
    assert rule.status == RuleStatus.DRAFT
    assert rule.author is None
    assert rule.reason is None
    assert len(rule.id) > 0
    assert rule.created_at > 0


def test_rule_max_text_length():
    with pytest.raises(Exception):
        Rule(text="x" * 161)


def test_rule_max_reason_length():
    with pytest.raises(Exception):
        Rule(text="ok", reason="x" * 241)


def test_rule_serialization_roundtrip():
    rule = Rule(text="Test rule", author="claude", status=RuleStatus.ACTIVE)
    data = rule.model_dump()
    restored = Rule(**data)
    assert restored.text == "Test rule"
    assert restored.status == RuleStatus.ACTIVE
    assert restored.author == "claude"


# --- Store tests ---

def test_store_add_and_get(tmp_path):
    store = RuleStore(tmp_path)
    rule = Rule(text="Be kind")
    result = store.add(rule)
    assert result.id == rule.id
    assert store.get(rule.id) is not None


def test_store_epoch_increments_on_add(tmp_path):
    store = RuleStore(tmp_path)
    assert store.epoch == 0
    store.add(Rule(text="Rule 1"))
    assert store.epoch == 1
    store.add(Rule(text="Rule 2"))
    assert store.epoch == 2


def test_store_epoch_increments_on_update(tmp_path):
    store = RuleStore(tmp_path)
    rule = Rule(text="Draft rule")
    store.add(rule)
    assert store.epoch == 1
    rule.status = RuleStatus.ACTIVE
    store.update(rule.id, rule)
    assert store.epoch == 2


def test_store_list_by_status(tmp_path):
    store = RuleStore(tmp_path)
    r1 = Rule(text="Active rule", status=RuleStatus.ACTIVE)
    r2 = Rule(text="Draft rule", status=RuleStatus.DRAFT)
    store.add(r1)
    store.add(r2)
    active = store.list_by_status(RuleStatus.ACTIVE)
    assert len(active) == 1
    assert active[0].id == r1.id


def test_store_persistence(tmp_path):
    store1 = RuleStore(tmp_path)
    store1.add(Rule(text="Persisted rule"))
    store2 = RuleStore(tmp_path)
    assert len(store2.list_all()) == 1
    assert store2.list_all()[0].text == "Persisted rule"


def test_store_update_nonexistent(tmp_path):
    store = RuleStore(tmp_path)
    result = store.update("fake-id", Rule(text="nope"))
    assert result is None


def test_store_add_duplicate(tmp_path):
    store = RuleStore(tmp_path)
    rule = Rule(text="Dup")
    store.add(rule)
    store.add(rule)
    assert len(store.list_all()) == 1


# --- Service tests ---

def test_service_propose(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    rule = svc.propose("No yelling", author="claude")
    assert rule.text == "No yelling"
    assert rule.status == RuleStatus.DRAFT
    assert rule.author == "claude"


def test_service_activate(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    rule = svc.propose("Be clear")
    result = svc.activate(rule.id)
    assert result is not None
    assert result.status == RuleStatus.ACTIVE


def test_service_deactivate(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    rule = svc.propose("Old rule")
    svc.activate(rule.id)
    result = svc.deactivate(rule.id)
    assert result is not None
    assert result.status == RuleStatus.ARCHIVE


def test_service_activate_idempotent(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    rule = svc.propose("Stable")
    svc.activate(rule.id)
    epoch_before = svc.get_epoch()
    svc.activate(rule.id)
    assert svc.get_epoch() == epoch_before


def test_service_deactivate_idempotent(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    rule = svc.propose("Gone")
    svc.activate(rule.id)
    svc.deactivate(rule.id)
    epoch_before = svc.get_epoch()
    svc.deactivate(rule.id)
    assert svc.get_epoch() == epoch_before


def test_service_list_active(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    r1 = svc.propose("Active one")
    r2 = svc.propose("Draft one")
    svc.activate(r1.id)
    active = svc.list_active()
    assert len(active) == 1
    assert active[0].id == r1.id


def test_service_activate_nonexistent(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    assert svc.activate("nope") is None


def test_service_deactivate_nonexistent(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    assert svc.deactivate("nope") is None


def test_service_get_epoch(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    assert svc.get_epoch() == 0
    svc.propose("One")
    assert svc.get_epoch() == 1
    svc.propose("Two")
    assert svc.get_epoch() == 2


def test_service_reactivate_archived(tmp_path):
    svc = RuleService(RuleStore(tmp_path))
    rule = svc.propose("Revived")
    svc.activate(rule.id)
    svc.deactivate(rule.id)
    result = svc.activate(rule.id)
    assert result is not None
    assert result.status == RuleStatus.ACTIVE
