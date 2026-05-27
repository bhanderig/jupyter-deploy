from typing import Any

from jupyter_deploy.engine.engine_outputs import EngineOutputsHandler
from jupyter_deploy.engine.enum import EngineType
from jupyter_deploy.engine.outdefs import StrTemplateOutputDefinition
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.terraform import tf_outputs, tf_variables
from jupyter_deploy.exceptions import InvalidComponentVerbError, ResourceNotFoundError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.resource.resource_utils import collect_results
from jupyter_deploy.manifest import JupyterDeployComponentDefinitionV1
from jupyter_deploy.provider import manifest_command_runner as cmd_runner
from jupyter_deploy.provider.resolved_clidefs import ResolvedCliParameter, StrResolvedCliParameter


class ComponentHandler(BaseProjectHandler):
    """Handler class to interact with platform components."""

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

    def _resolve_namespace(self, component: JupyterDeployComponentDefinitionV1) -> str:
        output_defs = self._output_handler.get_full_project_outputs()
        ns_key = component.scope
        if ns_key not in output_defs:
            raise KeyError(f"Output '{ns_key}' not found for component namespace resolution")
        ns_def = output_defs[ns_key]
        if isinstance(ns_def, StrTemplateOutputDefinition) and ns_def.value:
            return ns_def.value
        raise ValueError(f"Output '{ns_key}' is not resolved")

    def _validate_verb(self, name: str, component: JupyterDeployComponentDefinitionV1, verb: str) -> None:
        if verb not in component.verbs:
            raise InvalidComponentVerbError(name, verb, component.type, list(component.verbs.keys()))

    def _get_command_name(self, component: JupyterDeployComponentDefinitionV1, verb: str) -> str:
        return f"component.{component.type.lower()}.{verb}"

    def _get_resource_name(self, name: str, component: JupyterDeployComponentDefinitionV1) -> str:
        return component.resource_name or name

    def _build_cli_paramdefs(
        self,
        name: str,
        component: JupyterDeployComponentDefinitionV1,
        namespace: str,
        extra: dict[str, str] | None = None,
    ) -> dict[str, ResolvedCliParameter[Any]]:
        cli_paramdefs: dict[str, ResolvedCliParameter[Any]] = {
            "name": StrResolvedCliParameter(parameter_name="name", value=name),
            "scope": StrResolvedCliParameter(parameter_name="scope", value=namespace),
        }
        if component.query:
            cli_paramdefs["query"] = StrResolvedCliParameter(parameter_name="query", value=component.query)
        if extra:
            for k, v in extra.items():
                cli_paramdefs[k] = StrResolvedCliParameter(parameter_name=k, value=v)
        return cli_paramdefs

    def list_components(self) -> list[dict[str, str]]:
        """Return the list of components with name, type, and description."""
        components = self.project_manifest.get_components()
        return [{"name": name, "type": comp.type, "description": comp.description} for name, comp in components.items()]

    def get_component_description(self, name: str) -> str:
        """Return the description string for a single component."""
        component = self.project_manifest.get_component(name)
        return component.description

    def get_all_status(self) -> list[dict[str, str]]:
        """Return status of all components for dashboard display."""
        components = self.project_manifest.get_components()
        results: list[dict[str, str]] = []
        for name, comp_def in components.items():
            namespace = self._resolve_namespace(comp_def)
            try:
                cmd_name = self._get_command_name(comp_def, "status")
                command = self.project_manifest.get_command(cmd_name)
                runner = cmd_runner.ManifestCommandRunner(
                    display_manager=self.display_manager,
                    output_handler=self._output_handler,
                    variable_handler=self._variable_handler,
                )
                resource_name = self._get_resource_name(name, comp_def)
                cli_paramdefs = self._build_cli_paramdefs(resource_name, comp_def, namespace)
                runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
                status = runner.get_result_value(command, f"{cmd_name}.status", str)
                status_category = runner.get_result_value_with_fallback(command, f"{cmd_name}.status_category", str, "")
                details = runner.get_result_value_with_fallback(command, f"{cmd_name}.details", str, "")
                sub_component = runner.get_result_value_with_fallback(command, f"{cmd_name}.sub_component", str, "")
            except ResourceNotFoundError:
                status = "Not Found"
                status_category = "degraded"
                details = f"{comp_def.type.lower()} '{name}' not found"
                sub_component = ""
            results.append(
                {
                    "name": name,
                    "type": comp_def.type,
                    "status": status,
                    "status_category": status_category,
                    "details": details,
                    "sub_component": sub_component,
                }
            )
        return results

    def get_component_status(self, name: str) -> str:
        """Return the status string for a single component."""
        component = self.project_manifest.get_component(name)
        self._validate_verb(name, component, "status")
        namespace = self._resolve_namespace(component)
        resource_name = self._get_resource_name(name, component)
        cmd_name = self._get_command_name(component, "status")
        command = self.project_manifest.get_command(cmd_name)
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(resource_name, component, namespace)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        return runner.get_result_value(command, f"{cmd_name}.status", str)

    def show_component(self, name: str) -> dict[str, Any]:
        """Return detailed information about a component."""
        component = self.project_manifest.get_component(name)
        self._validate_verb(name, component, "show")
        namespace = self._resolve_namespace(component)
        resource_name = self._get_resource_name(name, component)
        cmd_name = self._get_command_name(component, "show")
        command = self.project_manifest.get_command(cmd_name)
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(resource_name, component, namespace)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        return collect_results(runner, command)

    def get_component_logs(self, name: str, extra: list[str] | None = None) -> str:
        """Return logs for a component."""
        component = self.project_manifest.get_component(name)
        self._validate_verb(name, component, "logs")
        namespace = self._resolve_namespace(component)
        resource_name = self._get_resource_name(name, component)
        cmd_name = self._get_command_name(component, "logs")
        command = self.project_manifest.get_command(cmd_name)
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        extra_params: dict[str, str] = {"extra": " ".join(extra) if extra else ""}
        runner.run_command_sequence(
            command, cli_paramdefs=self._build_cli_paramdefs(resource_name, component, namespace, extra=extra_params)
        )
        return runner.get_result_value(command, f"{cmd_name}.logs", str)

    def restart_component(self, name: str) -> None:
        """Rolling restart a component (Deployment only)."""
        component = self.project_manifest.get_component(name)
        self._validate_verb(name, component, "restart")
        namespace = self._resolve_namespace(component)
        resource_name = self._get_resource_name(name, component)
        cmd_name = self._get_command_name(component, "restart")
        command = self.project_manifest.get_command(cmd_name)
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(resource_name, component, namespace)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)

    def trigger_component(self, name: str) -> str:
        """Trigger a Job from a CronJob component. Returns the Job name."""
        component = self.project_manifest.get_component(name)
        self._validate_verb(name, component, "trigger")
        namespace = self._resolve_namespace(component)
        resource_name = self._get_resource_name(name, component)
        cmd_name = self._get_command_name(component, "trigger")
        command = self.project_manifest.get_command(cmd_name)
        runner = cmd_runner.ManifestCommandRunner(
            display_manager=self.display_manager,
            output_handler=self._output_handler,
            variable_handler=self._variable_handler,
        )
        cli_paramdefs = self._build_cli_paramdefs(resource_name, component, namespace)
        runner.run_command_sequence(command, cli_paramdefs=cli_paramdefs)
        return runner.get_result_value(command, f"{cmd_name}.job_name", str)
