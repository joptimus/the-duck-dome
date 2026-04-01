"""Tests for console_monitor module."""
from unittest.mock import MagicMock, patch

from duckdome.wrapper.console_monitor import ConsoleMonitor
from duckdome.models.tool_approval import ToolApproval, ToolApprovalStatus


class TestConsoleMonitor:

    def _make_monitor(self, **overrides):
        defaults = dict(
            pid=1234,
            agent_type="claude",
            channel_id="test-channel",
            approval_service=MagicMock(),
            inject_delay=0.05,
            poll_interval=0.1,
        )
        defaults.update(overrides)
        return ConsoleMonitor(**defaults)

    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_detects_permission_prompt_and_creates_approval(self, mock_read):
        """When a permission prompt appears, an approval is created."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        svc = MagicMock()
        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={"command": "git status"},
            channel="test-channel",
        )
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()

        svc.request.assert_called_once()
        call_kwargs = svc.request.call_args.kwargs
        assert call_kwargs["tool"] == "Bash"
        assert call_kwargs["agent"] == "claude"
        assert call_kwargs["channel"] == "test-channel"

    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_does_not_duplicate_same_prompt(self, mock_read):
        """Same prompt appearing twice only creates one approval."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        svc = MagicMock()
        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={},
            channel="test-channel",
        )
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()
        monitor._poll_once()

        assert svc.request.call_count == 1

    @patch("duckdome.wrapper.console_monitor._inject_response")
    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_injects_y_on_approval(self, mock_read, mock_inject):
        """When approval is resolved as approved, inject 'y' + Enter."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={},
            channel="test-channel",
        )
        svc = MagicMock()
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )
        svc.get.return_value = approval

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()  # detect prompt, create approval

        # Simulate user approving
        approval.status = ToolApprovalStatus.APPROVED
        monitor._poll_once()  # check resolution, inject

        mock_inject.assert_called_once_with(1234, "y", 0.05)

    @patch("duckdome.wrapper.console_monitor._inject_response")
    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_injects_n_on_denial(self, mock_read, mock_inject):
        """When approval is resolved as denied, inject 'n' + Enter."""
        prompt_text = (
            "  \u276f Do you want to allow Claude to use Bash?\n"
            "    Command: git status\n"
            "    (Y)es | (N)o | Yes, and don't ask again for this tool"
        )
        mock_read.return_value = prompt_text

        approval = ToolApproval(
            agent="claude", tool="Bash", arguments={},
            channel="test-channel",
        )
        svc = MagicMock()
        svc.request.return_value = MagicMock(
            status="pending", approval=approval,
        )
        svc.get.return_value = approval

        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()

        approval.status = ToolApprovalStatus.DENIED
        monitor._poll_once()

        mock_inject.assert_called_once_with(1234, "n", 0.05)

    @patch("duckdome.wrapper.console_monitor._read_console_buffer")
    def test_no_match_does_nothing(self, mock_read):
        """Regular output does not create approvals."""
        mock_read.return_value = "Hello world\nProcessing files..."

        svc = MagicMock()
        monitor = self._make_monitor(approval_service=svc)
        monitor._poll_once()

        svc.request.assert_not_called()
