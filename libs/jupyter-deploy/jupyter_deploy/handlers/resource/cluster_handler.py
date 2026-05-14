from typing import Any

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.resource.resource_utils import collect_results
from jupyter_deploy.provider import manifest_command_runner as cmd_runner


class ClusterHandler(BaseProjectHandler):
    """Handler class to interact with the cluster running the deployment."""

    _output_handler: EngineOutputsHandler

    def __init__(self, display_manager: DisplayManager) -> None:
        super().__init__(display_manager=display_manager)

        if self.engine == EngineType.TERRAFORM:
            self._output_handler = tf_outputs.TerraformOutputsHandler(
                project_path=self.project_path, project_manifest=self.project_manifest
            )
            self._variable_handler = tf_variables.TerraformVariablesHandler(
                project_path=self.project_path,
                project_manifest=self.project_manifest,
                display_manager=self.display_manager,
            )
        else:
            raise NotImplementedError(f"OutputsHandler implementation not found for engine: {self.engine}")

    def login(self) -> str:
        """Configure local client to access to the cluster, returns the output message."""
        command = self.project_manifest.get_command("cluster.login")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "cluster.login.output", str)

    def get_cluster_status(self) -> str:
        """Returns the control plane state string."""
        command = self.project_manifest.get_command("cluster.status")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return runner.get_result_value(command, "cluster.status", str)

    def show_cluster(self) -> dict[str, Any]:
        """Returns cluster metadata dict."""
        command = self.project_manifest.get_command("cluster.show")
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        runner.run_command_sequence(command, cli_paramdefs={})
        return collect_results(runner, command)
