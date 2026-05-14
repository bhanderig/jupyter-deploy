import webbrowser
from typing import Any

from jupyter_deploy.engine.engine_open import EngineOpenHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.engine.terraform import tf_open, tf_variables
from jupyter_deploy.exceptions import OpenWebBrowserError, UrlNotAvailableError, UrlNotSecureError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter


class OpenHandler(BaseProjectHandler):
    _handler: EngineOpenHandler

    def __init__(self) -> None:
        """Base class to manage the open command of a jupyter-deploy project."""
        super().__init__(display_manager=NullDisplay())

        if self.engine == EngineType.TERRAFORM:
            self._handler = tf_open.TerraformOpenHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"OpenHandler implementation not found for engine: {self.engine}")

    def _resolve_scope(self, scope: str | None) -> str:
        output_handler = self._handler.output_handler
        if scope:
            return scope
        try:
            scope_def = output_handler.get_declared_output_def("server_default_scope", StrTemplateOutputDefinition)
            if scope_def.value:
                return scope_def.value
        except (NotImplementedError, KeyError, ValueError):
            pass
        return "default"

    def get_url(self) -> str:
        """Return the URL to access the Jupyter app.

        Raises:
            UrlNotAvailableError: If URL cannot be retrieved or is empty
        """
        return self._handler.get_url()

    def get_server_url(self, name: str, scope: str | None = None) -> str:
        """Resolve and return the URL for a specific server.

        Runs the open.server manifest command which fetches the server resource
        and extracts the access URL from it.

        Raises:
            CommandNotImplementedError: If open.server is not in the manifest
            ResourceNotFoundError: If the server does not exist
            UrlNotAvailableError: If the server has no access URL
        """
        resolved_scope = self._resolve_scope(scope)
        command = self.project_manifest.get_command("open.server")
        output_handler = self._handler.output_handler
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "name": StrResolvedCliParameter(parameter_name="name", value=name),
            "scope": StrResolvedCliParameter(parameter_name="scope", value=resolved_scope),
        }
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)

        try:
            url = runner.get_result_value(command, "open.server.url", str)
        except KeyError as e:
            raise UrlNotAvailableError(
                f"Could not resolve URL for server '{name}' in scope '{resolved_scope}'. Is the server running?"
            ) from e
        if not url:
            raise UrlNotAvailableError(
                f"Could not resolve URL for server '{name}' in scope '{resolved_scope}'. Is the server running?"
            )

        return url

    def open(self, name: str | None = None, scope: str | None = None) -> str:
        """Open the application or a specific server in the browser.

        When name is provided, resolves the server URL via the open.server
        manifest command. Otherwise falls back to the project open_url output.

        Returns:
            str: The URL that was opened

        Raises:
            UrlNotAvailableError: If URL cannot be retrieved or is empty
            UrlNotSecureError: If URL is not HTTPS
            OpenWebBrowserError: If opening URL in browser fails
            CommandNotImplementedError: If name given but open.server not in manifest
            ResourceNotFoundError: If the named server does not exist
        """
        url = self.get_url() if name is None else self.get_server_url(name, scope)

        if not url.startswith("https://"):
            raise UrlNotSecureError("Insecure URL detected. Only HTTPS URLs are allowed for security reasons.", url)

        open_status = webbrowser.open(url, new=2)
        if not open_status:
            raise OpenWebBrowserError("Failed to open URL in browser.", url)

        return url
