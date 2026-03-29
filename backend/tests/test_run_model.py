from duckdome.models.run import RunRecord


def test_run_record_defaults():
    r = RunRecord(trigger_id="t-1", channel_id="ch-1", agent_type="claude")
    assert r.id is not None
    assert r.started_at is not None
    assert r.ended_at is None
    assert r.duration_ms is None
    assert r.exit_code is None
    assert r.error_summary is None


def test_run_record_roundtrip():
    r = RunRecord(trigger_id="t-1", channel_id="ch-1", agent_type="claude")
    data = r.model_dump()
    restored = RunRecord(**data)
    assert restored.id == r.id
