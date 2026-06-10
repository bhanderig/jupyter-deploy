import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from jupyter_deploy.handlers.docs_generator import DocsGenerator


class TestDocsGenerator(unittest.TestCase):
    """Test class for DocsGenerator."""

    def setUp(self) -> None:
        """Set up test fixtures."""
        self.project_path = Path("/test/project")
        self.engine = "terraform"

        self.generator = DocsGenerator(
            project_path=self.project_path,
            engine=self.engine,
        )

    def test_init(self) -> None:
        """Test DocsGenerator initialization."""
        self.assertEqual(self.generator.project_path, self.project_path)
        self.assertEqual(self.generator.engine, self.engine)

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.exists")
    def test_generate_gitignore_terraform(self, mock_exists: Mock, mock_write_text: Mock, mock_read_text: Mock) -> None:
        """Test generate_gitignore with terraform engine."""
        # Setup
        mock_exists.return_value = True
        template_content = """# JD internal state and outputs
.jd-history/
jdout-*
jdinputs.*

# Terraform state files
.terraform/
*.tfstate
*.tfstate.*
.terraform.lock.hcl
"""
        mock_read_text.return_value = template_content

        # Execute
        self.generator.generate_gitignore()

        # Assert
        mock_exists.assert_called_once()
        mock_read_text.assert_called_once()
        mock_write_text.assert_called_once_with(template_content)

    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.exists")
    def test_generate_gitignore_pulumi(self, mock_exists: Mock, mock_write_text: Mock, mock_read_text: Mock) -> None:
        """Test generate_gitignore with pulumi engine."""
        # Setup
        self.generator.engine = "pulumi"
        mock_exists.return_value = True
        template_content = """# JD internal state and outputs
.jd-history/
jdout-*
jdinputs.*

# Pulumi state files
.pulumi/
Pulumi.*.yaml
"""
        mock_read_text.return_value = template_content

        # Execute
        self.generator.generate_gitignore()

        # Assert
        mock_exists.assert_called_once()
        mock_read_text.assert_called_once()
        mock_write_text.assert_called_once_with(template_content)

    @patch("pathlib.Path.exists")
    def test_generate_gitignore_no_template(self, mock_exists: Mock) -> None:
        """Test generate_gitignore when template file doesn't exist."""
        # Setup
        mock_exists.return_value = False

        # Execute
        self.generator.generate_gitignore()

        # Assert - should not raise, just return
        mock_exists.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_generate_gitignore_unknown_engine(self, mock_exists: Mock) -> None:
        """Test generate_gitignore with unknown engine."""
        # Setup
        self.generator.engine = "unknown-engine"
        mock_exists.return_value = False

        # Execute
        self.generator.generate_gitignore()

        # Assert - should not raise, just return (template doesn't exist for unknown engine)
        mock_exists.assert_called_once()

    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.exists")
    def test_generate_agent_md(
        self, mock_exists: Mock, mock_write_text: Mock, mock_read_text: Mock, mock_unlink: Mock
    ) -> None:
        """Test generate_agent_md with single snippet."""
        # Setup
        mock_exists.return_value = True

        # Simple template with one placeholder
        template_content = "Commands: {{ config-up-instructions }}"
        config_snippet = "```bash\njd config\njd up\n```"

        # First read is template, second is snippet
        mock_read_text.side_effect = [template_content, config_snippet]

        # Execute
        self.generator.generate_agent_md()

        # Assert
        assert mock_write_text.called
        output = mock_write_text.call_args[0][0]
        assert "jd config" in output
        assert "{{" not in output  # No placeholders remain
        mock_unlink.assert_called_once()  # Template file should be deleted

    @patch("pathlib.Path.exists")
    def test_generate_agent_md_no_template(self, mock_exists: Mock) -> None:
        """Test generate_agent_md when template doesn't exist."""
        # Setup
        mock_exists.return_value = False

        # Execute
        self.generator.generate_agent_md()

        # Assert - should not raise, just return
        mock_exists.assert_called_once()

    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.exists")
    def test_generate_agent_md_with_missing_snippet(
        self, mock_exists: Mock, mock_write_text: Mock, mock_read_text: Mock, mock_unlink: Mock
    ) -> None:
        """Test generate_agent_md when a snippet file doesn't exist."""
        # Setup
        template_content = "Commands: {{ missing-snippet }}"

        # First exists check for template returns True, second for snippet returns False
        mock_exists.side_effect = [True, False]
        mock_read_text.return_value = template_content

        # Execute
        self.generator.generate_agent_md()

        # Assert - placeholder should remain when snippet doesn't exist
        assert mock_write_text.called
        output = mock_write_text.call_args[0][0]
        assert "{{ missing-snippet }}" in output
        mock_unlink.assert_called_once()  # Template file should be deleted

    @patch("pathlib.Path.unlink")
    @patch("pathlib.Path.read_text")
    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.exists")
    def test_generate_troubleshoot_md(
        self, mock_exists: Mock, mock_write_text: Mock, mock_read_text: Mock, mock_unlink: Mock
    ) -> None:
        """Test generate_troubleshoot_md with single snippet."""
        # Setup
        mock_exists.return_value = True

        template_content = "Quota: {{ request-quota-increase-instructions }}"
        quota_snippet = "Request a higher limit:\n```bash\naws service-quotas ...\n```"

        # First read is template, second is snippet
        mock_read_text.side_effect = [template_content, quota_snippet]

        # Execute
        self.generator.generate_troubleshoot_md()

        # Assert
        assert mock_write_text.called
        output = mock_write_text.call_args[0][0]
        assert "service-quotas" in output
        assert "{{" not in output  # No placeholders remain
        mock_unlink.assert_called_once()  # Template file should be deleted

    @patch("pathlib.Path.exists")
    def test_generate_troubleshoot_md_no_template(self, mock_exists: Mock) -> None:
        """Test generate_troubleshoot_md when template doesn't exist."""
        # Setup
        mock_exists.return_value = False

        # Execute
        self.generator.generate_troubleshoot_md()

        # Assert - should not raise, just return
        mock_exists.assert_called_once()
