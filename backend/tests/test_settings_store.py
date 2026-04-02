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
