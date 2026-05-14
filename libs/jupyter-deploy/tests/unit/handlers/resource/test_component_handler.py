import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.exceptions import ComponentNotFoundError, InvalidComponentVerbError
from jupyter_deploy.handlers.resource.component_handler import ComponentHandler
from jupyter_deploy.manifest import JupyterDeployComponentDefinitionV1, JupyterDeployComponentVerbV1


def _mock_component_deployment() -> JupyterDeployComponentDefinitionV1:
    return JupyterDeployComponentDefinitionV1(
        type="Deployment",
        scope="workspace_router_namespace",
        verbs={
            "status": JupyterDeployComponentVerbV1(method="k8s.apps.get-deployment-status"),
            "show": JupyterDeployComponentVerbV1(method="k8s.apps.get-deployment"),
            "logs": JupyterDeployComponentVerbV1(method="k8s.core.deployment-logs"),
            "restart": JupyterDeployComponentVerbV1(method="k8s.apps.rollout-restart"),
        },
    )


def _mock_component_cronjob() -> JupyterDeployComponentDefinitionV1:
    return JupyterDeployComponentDefinitionV1(
        type="CronJob",
        scope="workspace_router_namespace",
        query="app=jwt-rotator",
        verbs={
            "status": JupyterDeployComponentVerbV1(method="k8s.batch.get-cronjob-status"),
            "show": JupyterDeployComponentVerbV1(method="k8s.batch.get-cronjob"),
            "logs": JupyterDeployComponentVerbV1(method="k8s.batch.get-job-logs"),
            "trigger": JupyterDeployComponentVerbV1(method="k8s.batch.create-job-from-cronjob"),
        },
    )


_NS_OUTPUTS = {
    "workspace_router_namespace": StrTemplateOutputDefinition(
        output_name="workspace_router_namespace", value="router-ns"
    )
}


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerGetComponentStatus(unittest.TestCase):
    def test_returns_status_for_deployment(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "Ready"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            mock_command: Mock = Mock()
            manifest.get_command.return_value = mock_command

            handler = ComponentHandler(display_manager=Mock())
            result = handler.get_component_status("traefik")

        self.assertEqual(result, "Ready")
        manifest.get_command.assert_called_once_with("component.deployment.status")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")

    def test_passes_query_for_cronjob(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "Idle"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            handler.get_component_status("jwt-rotator")

        manifest.get_command.assert_called_once_with("component.cronjob.status")
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["query"].value, "app=jwt-rotator")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.get_component_status("traefik")

    def test_raises_component_not_found(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.side_effect = ComponentNotFoundError("unknown", ["traefik", "dex"])
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())

        with self.assertRaises(ComponentNotFoundError) as ctx:
            handler.get_component_status("unknown")

        self.assertEqual(ctx.exception.component_name, "unknown")
        self.assertIn("traefik", ctx.exception.valid_components)


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerVerbValidation(unittest.TestCase):
    def test_raises_invalid_verb_for_restart_on_cronjob(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())

        with self.assertRaises(InvalidComponentVerbError) as ctx:
            handler.restart_component("jwt-rotator")

        self.assertEqual(ctx.exception.verb, "restart")
        self.assertEqual(ctx.exception.component_type, "CronJob")
        self.assertIn("trigger", ctx.exception.valid_verbs)

    def test_raises_invalid_verb_for_trigger_on_deployment(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        handler = ComponentHandler(display_manager=Mock())

        with self.assertRaises(InvalidComponentVerbError) as ctx:
            handler.trigger_component("traefik")

        self.assertEqual(ctx.exception.verb, "trigger")
        self.assertEqual(ctx.exception.component_type, "Deployment")
        self.assertIn("restart", ctx.exception.valid_verbs)


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerGetAllStatus(unittest.TestCase):
    def test_returns_status_for_all_components(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_components.return_value = {
            "traefik": _mock_component_deployment(),
            "jwt-rotator": _mock_component_cronjob(),
        }
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "Ready"
        mock_runner.get_result_value_with_fallback.return_value = "1/1 replicas"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            results = handler.get_all_status()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["name"], "traefik")
        self.assertEqual(results[0]["status"], "Ready")
        self.assertEqual(results[1]["name"], "jwt-rotator")
        manifest.get_command.assert_any_call("component.deployment.status")
        manifest.get_command.assert_any_call("component.cronjob.status")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_components.return_value = {
            "traefik": _mock_component_deployment(),
        }
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch(
            "jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner"
        ) as mock_runner_cls:
            mock_runner_cls.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()
            handler = ComponentHandler(display_manager=Mock())

            with self.assertRaises(RuntimeError):
                handler.get_all_status()


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerShowComponent(unittest.TestCase):
    def test_calls_show_command_with_correct_args(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = ""

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            mock_command: Mock = Mock()
            mock_command.results = []
            manifest.get_command.return_value = mock_command

            handler = ComponentHandler(display_manager=Mock())
            handler.show_component("traefik")

        manifest.get_command.assert_called_once_with("component.deployment.show")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.show_component("traefik")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerGetComponentLogs(unittest.TestCase):
    def test_calls_logs_command_with_extra(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "log line"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            result = handler.get_component_logs("traefik", extra=["--tail=50", "--since=1h"])

        self.assertEqual(result, "log line")
        manifest.get_command.assert_called_once_with("component.deployment.logs")
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")
        self.assertEqual(cli_paramdefs["extra"].value, "--tail=50 --since=1h")

    def test_passes_empty_extra_when_none(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = ""

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            handler.get_component_logs("traefik")

        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["extra"].value, "")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.get_component_logs("traefik")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerRestartComponent(unittest.TestCase):
    def test_calls_restart_command(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            handler.restart_component("traefik")

        manifest.get_command.assert_called_once_with("component.deployment.restart")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "traefik")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_deployment()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.restart_component("traefik")


@patch("jupyter_deploy.handlers.resource.component_handler.tf_variables.TerraformVariablesHandler")
@patch("jupyter_deploy.handlers.resource.component_handler.tf_outputs.TerraformOutputsHandler")
@patch("jupyter_deploy.handlers.base_project_handler.retrieve_project_manifest")
class TestComponentHandlerTriggerComponent(unittest.TestCase):
    def test_calls_trigger_command_and_returns_job_name(
        self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock
    ) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        mock_runner: Mock = Mock()
        mock_runner.get_result_value.return_value = "jwt-rotator-manual-20250514"

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value = mock_runner
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            result = handler.trigger_component("jwt-rotator")

        self.assertEqual(result, "jwt-rotator-manual-20250514")
        manifest.get_command.assert_called_once_with("component.cronjob.trigger")
        mock_runner.run_command_sequence.assert_called_once()
        cli_paramdefs = mock_runner.run_command_sequence.call_args.kwargs["cli_paramdefs"]
        self.assertEqual(cli_paramdefs["name"].value, "jwt-rotator")
        self.assertEqual(cli_paramdefs["scope"].value, "router-ns")
        self.assertEqual(cli_paramdefs["query"].value, "app=jwt-rotator")

    def test_error_bubbles_up(self, mock_manifest_fn: Mock, mock_outputs: Mock, mock_variables: Mock) -> None:
        manifest: Mock = Mock()
        manifest.get_engine.return_value = "terraform"
        manifest.template.engine = "terraform"
        manifest.get_component.return_value = _mock_component_cronjob()
        mock_manifest_fn.return_value = manifest

        mock_output_handler: Mock = mock_outputs.return_value
        mock_output_handler.get_full_project_outputs.return_value = _NS_OUTPUTS

        with patch("jupyter_deploy.handlers.resource.component_handler.cmd_runner.ManifestCommandRunner") as mock_cmd:
            mock_cmd.return_value.run_command_sequence.side_effect = RuntimeError("API failure")
            manifest.get_command.return_value = Mock()

            handler = ComponentHandler(display_manager=Mock())
            with self.assertRaises(RuntimeError):
                handler.trigger_component("jwt-rotator")
