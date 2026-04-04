from duckdome.stores.settings_store import SettingsStore


def test_default_show_windows_is_false(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    assert store.get("show_agent_windows") is False


def test_set_and_get(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    store.set("show_agent_windows", True)
    assert store.get("show_agent_windows") is True


def test_persists_across_reload(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    store.set("show_agent_windows", True)
    store2 = SettingsStore(data_dir=tmp_path)
    assert store2.get("show_agent_windows") is True


def test_get_all_includes_defaults(tmp_path):
    store = SettingsStore(data_dir=tmp_path)
    result = store.get_all()
    assert "show_agent_windows" in result
    assert result["show_agent_windows"] is False


def test_corrupt_file_falls_back_to_defaults(tmp_path):
    settings_file = tmp_path / "settings.json"
    settings_file.write_bytes(b"not valid json {{{{")
    store = SettingsStore(data_dir=tmp_path)
    assert store.get("show_agent_windows") is False


def test_wrong_type_is_ignored(tmp_path):
    import json
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(json.dumps({"show_agent_windows": "true"}))
    store = SettingsStore(data_dir=tmp_path)
    # String "true" should be rejected; default (False) should be used
    assert store.get("show_agent_windows") is False
