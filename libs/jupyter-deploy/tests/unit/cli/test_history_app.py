"""Tests for history CLI commands."""

import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch

from typer.testing import CliRunner

from jupyter_deploy.cli.history_app import history_app
from jupyter_deploy.cmd_history import LogFileDescriptor, LogFilesCleanupResult
from jupyter_deploy.exceptions import LogNotFoundError

runner = CliRunner()


def get_mock_history_handler() -> tuple[Mock, dict[str, Mock]]:
    """Create a mock CommandHistoryHandler with all methods mocked.

    Returns:
        Tuple of (mock_handler, mock_methods_dict)
    """
    mock_handler = Mock()
    mock_list_logs = Mock()
    mock_get_latest_log = Mock()
    mock_get_log_lines = Mock()
    mock_stream_log_lines = Mock()
    mock_clear_logs = Mock()

    mock_handler.list_logs = mock_list_logs
    mock_handler.get_latest_log = mock_get_latest_log
    mock_handler.get_log_lines = mock_get_log_lines
    mock_handler.stream_log_lines = mock_stream_log_lines
    mock_handler.clear_logs = mock_clear_logs

    # Default return values
    mock_list_logs.return_value = []
    mock_get_latest_log.return_value = None
    mock_get_log_lines.return_value = []
    mock_clear_logs.return_value = LogFilesCleanupResult()

    return mock_handler, {
        "list_logs": mock_list_logs,
        "get_latest_log": mock_get_latest_log,
        "get_log_lines": mock_get_log_lines,
        "stream_log_lines": mock_stream_log_lines,
        "clear_logs": mock_clear_logs,
    }


class TestHistoryListCommand(unittest.TestCase):
    """Test cases for 'jd history list' command."""

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    def test_list_shows_no_logs_message_when_empty(self, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that list command shows message when no logs exist."""
        mock_handler, mock_methods = get_mock_history_handler()
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["list", "config"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No execution logs found", result.stdout)
        mock_methods["list_logs"].assert_called_once_with("config", max_logs=20)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_list_displays_logs_in_table(
        self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that list command displays logs in a formatted table."""
        mock_cwd.return_value = Path("/fake/project")

        log1 = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )
        log2 = LogFileDescriptor(
            id="config/20260129-143023.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 23, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143023.log"),
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log2, log1]
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["list", "config"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Execution History Logs", result.stdout)
        self.assertIn("config", result.stdout)
        self.assertIn("file", result.stdout)
        mock_methods["list_logs"].assert_called_once_with("config", max_logs=20)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_list_with_text_flag_shows_plain_output(
        self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that list command with --text shows plain repr output."""
        mock_cwd.return_value = Path("/fake/project")

        log1 = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log1]
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["list", "config", "--text"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn(".jd-history/config/20260129-143022.log", result.stdout)
        mock_methods["list_logs"].assert_called_once_with("config", max_logs=20)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    def test_list_requires_command_argument(self, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that list command requires command argument."""
        result = runner.invoke(history_app, ["list"])

        self.assertNotEqual(result.exit_code, 0)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    def test_list_validates_command_type_via_enum(self, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that list command validates command type through enum."""
        result = runner.invoke(history_app, ["list", "invalid_command"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    def test_list_accepts_n_option(self, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that list command accepts -n option and passes it to handler."""
        mock_handler, mock_methods = get_mock_history_handler()
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["list", "config", "-n", "10"])

        self.assertEqual(result.exit_code, 0)
        mock_methods["list_logs"].assert_called_once_with("config", max_logs=10)


class TestHistoryShowCommand(unittest.TestCase):
    """Test cases for 'jd history show' command."""

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_show_displays_log_content(self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that show command displays log content."""
        mock_cwd.return_value = Path("/fake/project")

        log_descriptor = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )

        log_lines = ["Terraform initialized\n", "Plan: 65 to add, 0 to change, 0 to destroy\n"]

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log_descriptor]
        mock_methods["stream_log_lines"].return_value = iter(log_lines)
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show", "config"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Terraform initialized", result.stdout)
        mock_methods["list_logs"].assert_called_once_with("config", max_logs=1)
        mock_methods["stream_log_lines"].assert_called_once_with(log_descriptor)
        mock_methods["get_log_lines"].assert_not_called()

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_show_accepts_n_option(self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that show command accepts -n option to show Nth most recent log."""
        mock_cwd.return_value = Path("/fake/project")

        log1 = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )
        log2 = LogFileDescriptor(
            id="config/20260129-143023.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 23, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143023.log"),
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log2, log1]
        mock_methods["stream_log_lines"].return_value = iter(["log content\n"])
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show", "config", "-n", "2"])

        self.assertEqual(result.exit_code, 0)
        mock_methods["list_logs"].assert_called_once_with("config", max_logs=2)
        mock_methods["stream_log_lines"].assert_called_once_with(log1)
        mock_methods["get_log_lines"].assert_not_called()

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_show_accepts_lines_option(self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that show command accepts -l option to limit output lines."""
        mock_cwd.return_value = Path("/fake/project")

        log_descriptor = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )

        log_lines = [f"Line {i}\n" for i in range(100)]
        last_10_lines = log_lines[-10:]

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log_descriptor]
        mock_methods["get_log_lines"].return_value = last_10_lines
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show", "config", "-l", "10"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Line 99", result.stdout)
        self.assertNotIn("Line 0", result.stdout)
        mock_methods["get_log_lines"].assert_called_once_with(log_descriptor, max_lines=10, skip=0)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_show_accepts_skip_option(self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that show command accepts -s/--skip option for pagination."""
        mock_cwd.return_value = Path("/fake/project")

        log_descriptor = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )

        log_lines = [f"Line {i}\n" for i in range(100)]
        middle_lines = log_lines[40:50]

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log_descriptor]
        mock_methods["get_log_lines"].return_value = middle_lines
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show", "config", "-l", "10", "-s", "50"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Line 40", result.stdout)
        self.assertIn("Line 49", result.stdout)
        self.assertNotIn("Line 50", result.stdout)
        mock_methods["get_log_lines"].assert_called_once_with(log_descriptor, max_lines=10, skip=50)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    def test_show_displays_message_when_no_log_found(self, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that show command displays error when no log is found."""
        mock_handler, mock_methods = get_mock_history_handler()
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show", "config"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("No log found", result.stdout)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_show_handles_log_not_found_exception(
        self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that show command handles LogNotFoundError via error decorator."""
        mock_cwd.return_value = Path("/fake/project")

        log_descriptor = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log_descriptor]
        mock_methods["stream_log_lines"].side_effect = LogNotFoundError("Log file not found")
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show", "config"])

        self.assertEqual(result.exit_code, 1)
        # Error decorator displays the error and hint
        self.assertIn("Log file not found", result.stdout)
        self.assertIn("jd history list", result.stdout)
        mock_methods["stream_log_lines"].assert_called_once_with(log_descriptor)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_show_without_command_shows_latest_from_any(
        self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that show command without command arg shows latest log from any command."""
        mock_cwd.return_value = Path("/fake/project")

        log_descriptor = LogFileDescriptor(
            id="up/20260129-150000.log",
            command="up",
            timestamp=datetime(2026, 1, 29, 15, 0, 0, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/up/20260129-150000.log"),
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["get_latest_log"].return_value = log_descriptor
        mock_methods["stream_log_lines"].return_value = iter(["log content\n"])
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show"])

        self.assertEqual(result.exit_code, 0)
        mock_methods["get_latest_log"].assert_called_once()
        mock_methods["stream_log_lines"].assert_called_once_with(log_descriptor)
        mock_methods["get_log_lines"].assert_not_called()

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_show_uses_streaming_by_default(
        self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that show command uses streaming mode by default (no -l or -s)."""
        mock_cwd.return_value = Path("/fake/project")

        log_descriptor = LogFileDescriptor(
            id="config/20260129-143022.log",
            command="config",
            timestamp=datetime(2026, 1, 29, 14, 30, 22, tzinfo=UTC),
            path=Path("/fake/project/.jd-history/config/20260129-143022.log"),
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["list_logs"].return_value = [log_descriptor]
        mock_methods["stream_log_lines"].return_value = iter(["line 1\n", "line 2\n"])
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["show", "config"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("line 1", result.stdout)
        self.assertIn("line 2", result.stdout)
        mock_methods["stream_log_lines"].assert_called_once_with(log_descriptor)
        mock_methods["get_log_lines"].assert_not_called()


class TestHistoryClearCommand(unittest.TestCase):
    """Test cases for 'jd history clear' command."""

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_clear_displays_success_message_for_specific_command(
        self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that clear command displays success message."""
        mock_cwd.return_value = Path("/fake/project")

        cleanup_result = LogFilesCleanupResult(
            cleaned=[Path("/fake/log1.log"), Path("/fake/log2.log")],
            kept=[Path("/fake/log3.log")],
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["clear_logs"].return_value = cleanup_result
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["clear", "config"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("Cleared 2 old log file(s)", result.stdout)
        self.assertIn("kept 1 most recent", result.stdout)
        mock_methods["clear_logs"].assert_called_once_with("config", keep=20)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    def test_clear_displays_message_when_no_logs_to_clear(
        self, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that clear command displays message when no logs need clearing."""
        mock_handler, mock_methods = get_mock_history_handler()
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["clear", "config"])

        self.assertEqual(result.exit_code, 0)
        self.assertIn("No stale log files to clear", result.stdout)
        mock_methods["clear_logs"].assert_called_once_with("config", keep=20)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_clear_accepts_keep_option(self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that clear command accepts --keep option."""
        mock_cwd.return_value = Path("/fake/project")

        cleanup_result = LogFilesCleanupResult(
            cleaned=[Path("/fake/log1.log")],
            kept=[Path("/fake/log2.log")],
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["clear_logs"].return_value = cleanup_result
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["clear", "config", "--keep", "10"])

        self.assertEqual(result.exit_code, 0)
        mock_methods["clear_logs"].assert_called_once_with("config", keep=10)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    @patch("pathlib.Path.cwd")
    def test_clear_displays_failures_when_present(
        self, mock_cwd: Mock, mock_handler_class: Mock, mock_project_dir: Mock
    ) -> None:
        """Test that clear command displays failures when some deletions fail."""
        mock_cwd.return_value = Path("/fake/project")

        cleanup_result = LogFilesCleanupResult(
            cleaned=[Path("/fake/log1.log")],
            kept=[Path("/fake/log2.log")],
            failed=[(Path("/fake/log3.log"), OSError("Permission denied"))],
        )

        mock_handler, mock_methods = get_mock_history_handler()
        mock_methods["clear_logs"].return_value = cleanup_result
        mock_handler_class.return_value = mock_handler

        result = runner.invoke(history_app, ["clear", "config"])

        self.assertEqual(result.exit_code, 1)
        self.assertIn("Failed to delete 1 log file(s)", result.stdout)
        mock_methods["clear_logs"].assert_called_once_with("config", keep=20)

    @patch("jupyter_deploy.cli.history_app.cmd_utils.project_dir")
    @patch("jupyter_deploy.cli.history_app.CommandHistoryHandler")
    def test_clear_requires_command_argument(self, mock_handler_class: Mock, mock_project_dir: Mock) -> None:
        """Test that clear command requires command argument."""
        result = runner.invoke(history_app, ["clear"])

        self.assertNotEqual(result.exit_code, 0)


class TestParameterValidation(unittest.TestCase):
    """Test parameter validation for history commands."""

    def test_list_rejects_n_zero(self) -> None:
        """Test that list command rejects n=0."""
        result = runner.invoke(history_app, ["list", "config", "-n", "0"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_list_rejects_n_negative(self) -> None:
        """Test that list command rejects negative n."""
        result = runner.invoke(history_app, ["list", "config", "-n", "-1"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_show_rejects_n_zero(self) -> None:
        """Test that show command rejects n=0."""
        result = runner.invoke(history_app, ["show", "config", "-n", "0"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_show_rejects_n_negative(self) -> None:
        """Test that show command rejects negative n."""
        result = runner.invoke(history_app, ["show", "config", "-n", "-1"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_show_rejects_lines_zero(self) -> None:
        """Test that show command rejects lines=0."""
        result = runner.invoke(history_app, ["show", "config", "-l", "0"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_show_rejects_lines_negative(self) -> None:
        """Test that show command rejects negative lines."""
        result = runner.invoke(history_app, ["show", "config", "-l", "-1"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_show_rejects_skip_negative(self) -> None:
        """Test that show command rejects negative skip."""
        result = runner.invoke(history_app, ["show", "config", "-s", "-1"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_show_accepts_skip_zero(self) -> None:
        """Test that show command accepts skip=0 (valid value)."""
        # Note: This will fail due to missing logs, but validates skip=0 is accepted
        result = runner.invoke(history_app, ["show", "config", "-s", "0"])

        # Should fail on no logs found, NOT on parameter validation
        # If it were parameter validation error, output would mention "Invalid value"
        self.assertNotIn("Invalid value", result.output)

    def test_clear_rejects_keep_zero(self) -> None:
        """Test that clear command rejects keep=0."""
        result = runner.invoke(history_app, ["clear", "config", "--keep", "0"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)

    def test_clear_rejects_keep_negative(self) -> None:
        """Test that clear command rejects negative keep."""
        result = runner.invoke(history_app, ["clear", "config", "--keep", "-1"])

        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("Invalid value", result.output)
