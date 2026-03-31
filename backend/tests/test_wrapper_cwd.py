from pathlib import Path

from duckdome.wrapper.manager import _resolve_launch_cwd


def test_resolve_launch_cwd_defaults_to_process_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    assert _resolve_launch_cwd(None) == str(tmp_path.resolve())


def test_resolve_launch_cwd_preserves_explicit_path(tmp_path):
    target = tmp_path / "repo"
    target.mkdir()

    assert _resolve_launch_cwd(str(target)) == str(target.resolve())
