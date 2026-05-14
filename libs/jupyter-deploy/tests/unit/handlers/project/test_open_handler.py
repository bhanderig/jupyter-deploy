import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.exceptions import UrlNotAvailableError
from jupyter_deploy.handlers.project.open_handler import OpenHandler
from jupyter_deploy.manifest import JupyterDeployManifestV1


def _make_open_server_manifest() -> JupyterDeployManifestV1:
    return _make_manifest(
        values=[
            {"name": "open_url", "source": "output", "source-key": "jupyter_url"},
            {"name": "server_default_scope", "source": "output", "source-key": "server_default_scope"},
        ],
        commands=[
            {
                "cmd": "open.server",
                "sequence": [
                    {
                        "api-name": "k8s.custom.get",
                        "arguments": [
                            {"api-attribute": "group", "source": "output", "source-key": "workspace_crd_group"},
                            {"api-attribute": "version", "source": "output", "source-key": "workspace_crd_version"},
                            {"api-attribute": "plural", "source": "output", "source-key": "workspace_crd_plural"},
                            {"api-attribute": "scope", "source": "cli", "source-key": "scope"},
                            {"api-attribute": "name", "source": "cli", "source-key": "name"},
                        ],
                    }
                ],
                "results": [
                    {
                        "result-name": "open.server.url",
                        "source": "result",
                        "source-key": "[0].Resource",
                        "extract": "status.accessURL",
                    }
                ],
            }
        ],
    )


def _make_manifest(
    values: list[dict[str, str]] | None = None, commands: list[dict] | None = None
) -> JupyterDeployManifestV1:
    return JupyterDeployManifestV1(
        **{  # type: ignore
            "schema_version": 1,
            "template": {
                "name": "mock-template-name",
                "engine": "terraform",
                "version": "1.0.0",
            },
            "values": values or [{"name": "open_url", "source": "output", "source-key": "jupyter_url"}],
            "commands": commands or [],
        }
    )


class TestOpenHandler(unittest.TestCase):
    def test_init(self) -> None:
        mock_manifest = _make_manifest()
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            self.assertIsNotNone(handler._handler)
            self.assertEqual(handler.engine, EngineType.TERRAFORM)
            self.assertEqual(handler.project_manifest, mock_manifest)

    def test_get_url_success(self) -> None:
        mock_manifest = _make_manifest()
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            with patch.object(handler._handler, "get_url", return_value="https://example.com/jupyter") as mock_get_url:
                url = handler.get_url()
                mock_get_url.assert_called_once()
                self.assertEqual(url, "https://example.com/jupyter")

    def test_open_success(self) -> None:
        mock_manifest = _make_manifest()
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve_manifest:
            mock_retrieve_manifest.return_value = mock_manifest
            handler = OpenHandler()
            with (
                patch.object(handler._handler, "get_url", return_value="https://example.com/jupyter"),
                patch("jupyter_deploy.handlers.project.open_handler.webbrowser.open", return_value=True) as mock_open,
            ):
                url = handler.open()
                self.assertEqual(url, "https://example.com/jupyter")
                mock_open.assert_called_once_with("https://example.com/jupyter", new=2)

    def test_open_with_server_name(self) -> None:
        mock_manifest = _make_open_server_manifest()
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve:
            mock_retrieve.return_value = mock_manifest
            handler = OpenHandler()

            with (
                patch(
                    "jupyter_deploy.handlers.project.open_handler.cmd_runner.ManifestCommandRunner"
                ) as mock_runner_cls,
                patch("jupyter_deploy.handlers.project.open_handler.webbrowser.open", return_value=True) as mock_open,
            ):
                mock_runner = Mock()
                mock_runner.get_result_value.return_value = "https://example.com/workspaces/team-a/my-ws/"
                mock_runner_cls.return_value = mock_runner

                url = handler.open(name="my-ws", scope="team-a")
                self.assertEqual(url, "https://example.com/workspaces/team-a/my-ws/")
                mock_runner.run_command_sequence.assert_called_once()
                mock_open.assert_called_once_with("https://example.com/workspaces/team-a/my-ws/", new=2)

    def test_get_server_url_empty_url(self) -> None:
        mock_manifest = _make_open_server_manifest()
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve:
            mock_retrieve.return_value = mock_manifest
            handler = OpenHandler()

            with (
                patch(
                    "jupyter_deploy.handlers.project.open_handler.cmd_runner.ManifestCommandRunner"
                ) as mock_runner_cls,
            ):
                mock_runner = Mock()
                mock_runner.get_result_value.return_value = ""
                mock_runner_cls.return_value = mock_runner

                with self.assertRaises(UrlNotAvailableError):
                    handler.get_server_url("my-ws", scope="default")

    def test_resolve_scope_uses_default_from_output(self) -> None:
        mock_manifest = _make_manifest(
            values=[
                {"name": "open_url", "source": "output", "source-key": "jupyter_url"},
                {"name": "server_default_scope", "source": "output", "source-key": "server_default_scope"},
            ],
        )
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve:
            mock_retrieve.return_value = mock_manifest
            handler = OpenHandler()

            mock_output_def = Mock()
            mock_output_def.value = "production-ns"
            with patch.object(handler._handler.output_handler, "get_declared_output_def", return_value=mock_output_def):
                result = handler._resolve_scope(None)
                self.assertEqual(result, "production-ns")

    def test_resolve_scope_explicit_overrides_default(self) -> None:
        mock_manifest = _make_manifest()
        with patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest") as mock_retrieve:
            mock_retrieve.return_value = mock_manifest
            handler = OpenHandler()
            result = handler._resolve_scope("custom-ns")
            self.assertEqual(result, "custom-ns")
