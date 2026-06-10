import re
from pathlib import Path


class DocsGenerator:
    """Generator for documentation files in jupyter-deploy projects."""

    # Path to static init templates relative to this file
    INIT_STATIC_DIR = Path(__file__).parent / "init_static"

    def __init__(
        self,
        project_path: Path,
        engine: str,
    ) -> None:
        """Initialize the documentation generator.

        Args:
            project_path: Path to the project directory where docs will be written
            engine: Infrastructure-as-code engine (e.g., "terraform")
        """
        self.project_path = project_path
        self.engine = engine

    def generate_gitignore(self) -> None:
        """Generate .gitignore file from engine-specific template."""
        # Determine template path based on engine
        template_filename = f".gitignore.{self.engine.lower()}.template"
        template_path = self.INIT_STATIC_DIR / "gitignore" / template_filename

        # If template doesn't exist, skip generation
        if not template_path.exists():
            return

        # Read template and write to project
        template_content = template_path.read_text()
        output_path = self.project_path / ".gitignore"
        output_path.write_text(template_content)

    def generate_agent_md(self) -> None:
        """Generate AGENT.md file from template with CLI snippet substitutions."""
        self._generate_from_template(template_filename="AGENT.md.template", snippet_dir_name="agent")

    def generate_troubleshoot_md(self) -> None:
        """Generate TROUBLESHOOT.md file from template with snippet substitutions."""
        self._generate_from_template(template_filename="TROUBLESHOOT.md.template", snippet_dir_name="troubleshoot")

    def _generate_from_template(self, template_filename: str, snippet_dir_name: str) -> None:
        """Render a project doc by substituting snippets into its `.template` file.

        Reads `<template_filename>` from the project directory, replaces every
        `{{ placeholder }}` with the matching snippet from
        `init_static/<snippet_dir_name>/<placeholder>.md`, writes the result to the
        file without the `.template` suffix, then removes the template.

        No-op if the template file does not exist.
        """
        template_path = self.project_path / template_filename

        if not template_path.exists():
            return

        template_content = template_path.read_text()
        snippet_dir = self.INIT_STATIC_DIR / snippet_dir_name
        output_content = self._substitute_snippets(template_content, snippet_dir)

        output_path = self.project_path / template_filename.removesuffix(".template")
        output_path.write_text(output_content)

        # Remove the template file after generation
        template_path.unlink()

    @staticmethod
    def _substitute_snippets(template_content: str, snippet_dir: Path) -> str:
        """Replace `{{ placeholder }}` tokens with snippets loaded from `snippet_dir`.

        Placeholders without a matching `<placeholder>.md` file are left untouched.
        """
        result = template_content

        # Find all placeholders in the template
        placeholders = re.findall(r"\{\{\s*([a-zA-Z0-9_-]+)\s*\}\}", template_content)

        # Load and substitute each snippet
        for placeholder in placeholders:
            snippet_path = snippet_dir / f"{placeholder}.md"
            if snippet_path.exists():
                snippet_content = snippet_path.read_text().rstrip()
                result = result.replace(f"{{{{ {placeholder} }}}}", snippet_content)

        return result
