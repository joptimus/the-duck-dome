import subprocess
from unittest.mock import patch, MagicMock

from duckdome.runner.claude import execute
from duckdome.runner.context import RunContext, ChannelContext, TriggerContext


def _general_ctx(text="help me"):
    return RunContext(
        channel=ChannelContext(
            channel_id="ch-1", channel_name="planning", channel_type="general",
        ),
        trigger=TriggerContext(
            source_message_id="msg-1", sender="human", text=text, timestamp=1234567890.0,
        ),
    )


def _repo_ctx(repo_path="/tmp/my-repo", text="review code"):
    return RunContext(
        channel=ChannelContext(
            channel_id="ch-2", channel_name="my-repo",
            channel_type="repo", repo_path=repo_path,
        ),
        trigger=TriggerContext(
            source_message_id="msg-2", sender="human", text=text, timestamp=1234567890.0,
        ),
    )


@patch("duckdome.runner.claude.subprocess.run")
def test_execute_success(mock_run):
    mock_run.return_value = MagicMock(stdout="Here is my response", stderr="", returncode=0)
    result = execute(_general_ctx())
    assert result.exit_code == 0
    assert result.stdout == "Here is my response"
    assert result.duration_ms >= 0

    args = mock_run.call_args
    cmd = args[0][0]
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "--no-session-persistence" in cmd
    assert args[1]["cwd"] is None


@patch("duckdome.runner.claude.subprocess.run")
def test_execute_repo_channel_sets_cwd(mock_run, tmp_path):
    repo = tmp_path / "my-repo"
    repo.mkdir()
    mock_run.return_value = MagicMock(stdout="done", stderr="", returncode=0)
    execute(_repo_ctx(repo_path=str(repo)))
    args = mock_run.call_args
    assert args[1]["cwd"] == str(repo)


@patch("duckdome.runner.claude.subprocess.run")
def test_execute_nonzero_exit(mock_run):
    mock_run.return_value = MagicMock(stdout="", stderr="error occurred", returncode=1)
    result = execute(_general_ctx())
    assert result.exit_code == 1
    assert result.stderr == "error occurred"


@patch("duckdome.runner.claude.subprocess.run")
def test_execute_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=5)
    result = execute(_general_ctx(), timeout_s=5)
    assert result.exit_code == -1
    assert "timed out" in result.stderr


@patch("duckdome.runner.claude.subprocess.run")
def test_execute_cli_not_found(mock_run):
    mock_run.side_effect = FileNotFoundError()
    result = execute(_general_ctx())
    assert result.exit_code == -2
    assert "not found" in result.stderr
