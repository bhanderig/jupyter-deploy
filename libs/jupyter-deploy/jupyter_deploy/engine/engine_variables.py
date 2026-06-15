from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from jupyter_deploy import constants, fs_utils
from jupyter_deploy.constants import MASKED_SECRET_VALUE
from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.engine.vardefs import TemplateVariableDefinition
from jupyter_deploy.exceptions import InvalidVariablesDotYamlError
from jupyter_deploy.handlers import base_project_handler
from jupyter_deploy.manifest import JupyterDeployManifest
from jupyter_deploy.variables_config import (
    VARIABLES_CONFIG_V2_COMMENTS,
    VARIABLES_CONFIG_V2_KEYS_ORDER,
    JupyterDeployVariablesConfig,
    JupyterDeployVariablesConfigV1,
    JupyterDeployVariablesConfigV2,
    migrate_variables_dot_yaml_to_latest,
)


class EngineVariablesHandler(ABC):
    def __init__(
        self,
        project_path: Path,
        project_manifest: JupyterDeployManifest,
        display_manager: DisplayManager,
    ) -> None:
        """Instantiate the base handler for the decorator.

        Args:
            project_path: Path to the project directory
            project_manifest: The project manifest
            display_manager: Display manager for status updates
        """
        self.project_path = project_path
        self.project_manifest = project_manifest
        self.display_manager = display_manager
        self._variables_config: JupyterDeployVariablesConfigV2 | None = None

    def get_variables_config_path(self) -> Path:
        return self.project_path / constants.VARIABLES_FILENAME

    def get_defaults_reference_path(self) -> Path:
        return self.project_path / constants.JD_DIR / constants.VARIABLES_DEFAULTS_FILENAME

    def _get_reset_variables_config(self) -> JupyterDeployVariablesConfigV2:
        """Retrieve the template variables, return reset variables config."""
        vardefs = self.get_template_variables()

        required: dict[str, Any] = {k: None for k, v in vardefs.items() if not v.has_default and not v.sensitive}
        sensitive: dict[str, Any] = {k: None for k, v in vardefs.items() if v.sensitive}
        return JupyterDeployVariablesConfigV2(
            schema_version=2,
            required=required,
            required_sensitive=sensitive,
            overrides={},
        )

    def _load_and_migrate(self, variables_config: JupyterDeployVariablesConfig) -> JupyterDeployVariablesConfigV2:
        """Ensure config is V2. Migrate from V1 if needed."""
        if isinstance(variables_config, JupyterDeployVariablesConfigV1):
            return migrate_variables_dot_yaml_to_latest(variables_config)
        return variables_config

    @property
    def variables_config(self) -> JupyterDeployVariablesConfigV2:
        if self._variables_config:
            return self._variables_config

        variables_config_path = self.project_path / constants.VARIABLES_FILENAME
        try:
            variables_config = base_project_handler.retrieve_variables_config(variables_config_path)
            self._variables_config = self._load_and_migrate(variables_config)
            return self._variables_config
        except FileNotFoundError:
            # the user has deleted their variables.yaml, reset it to a fallback
            if self.display_manager:
                self.display_manager.warning(
                    f"Variables config not found at: {variables_config_path.absolute()}, resetting to defaults"
                )
            reset_variables_config = self._get_reset_variables_config()
            self._variables_config = reset_variables_config
            return self._variables_config
        except InvalidVariablesDotYamlError:
            # the user has corrupted their variables.yaml, reset to a fallback
            if self.display_manager:
                self.display_manager.warning("Variables config was not a dict, resetting to defaults")
            reset_variables_config = self._get_reset_variables_config()
            self._variables_config = reset_variables_config
            return self._variables_config
        except ValidationError as e:
            # the user has corrupted their variables.yaml, reset to a fallback
            if self.display_manager:
                self.display_manager.warning(f"Variables config is invalid, resetting to defaults: {e}")
            reset_variables_config = self._get_reset_variables_config()
            self._variables_config = reset_variables_config
            return self._variables_config

    @abstractmethod
    def is_template_directory(self) -> bool:
        """Return True if the directory corresponds to a jupyter-deploy directory."""
        pass

    @abstractmethod
    def get_template_variables(self) -> dict[str, TemplateVariableDefinition]:
        """Return the dict of variable-name->variable-definition.

        This operation presumably requires file system operations and should
        be cached within each VariableHandler.
        """
        pass

    @abstractmethod
    def update_variable_records(self, varvalues: dict[str, Any], sensitive: bool = False) -> None:
        """Update the recorded values of all variables passed.

        Raises:
            KeyError if any of the variable name is not found
            TypeError if the any of the variable definition is not of the right type.
        """
        pass

    def _collect_varvalues_from_config(self) -> tuple[dict[str, Any], dict[str, Any]]:
        """Collect non-sensitive and sensitive variable values from the config.

        Returns:
            Tuple of (varvalues, sensitive_varvalues) with None/masked entries excluded.
        """
        required = self.variables_config.required
        sensitive = self.variables_config.required_sensitive
        overrides = self.variables_config.overrides
        varvalues: dict[str, Any] = {}
        sensitive_varvalues: dict[str, Any] = {}

        for var_name, var_value in required.items():
            if var_value is None:
                continue
            varvalues[var_name] = var_value

        for var_name, var_value in overrides.items():
            if var_value is None:
                continue
            varvalues[var_name] = var_value

        for sensitive_var_name, sensitive_var_value in sensitive.items():
            if sensitive_var_value is None or sensitive_var_value == MASKED_SECRET_VALUE:
                continue
            sensitive_varvalues[sensitive_var_name] = sensitive_var_value

        return varvalues, sensitive_varvalues

    def sync_engine_varfiles_with_project_variables_config(self) -> None:
        """Update engine specific variable files from the variables config.

        Bypass all variables set to `null`.
        """
        varvalues, sensitive_varvalues = self._collect_varvalues_from_config()
        self.update_variable_records(varvalues)
        self.update_variable_records(sensitive_varvalues, sensitive=True)

    def _get_defaults_for_comments(self) -> dict[str, Any]:
        """Get default values for writing as comments in variables.yaml."""
        defaults_path = self.get_defaults_reference_path()
        defaults = fs_utils.read_yaml_reference_file(defaults_path)
        if defaults:
            return defaults
        # Fallback: derive from template variables
        vardefs = self.get_template_variables()
        return {k: v.default for k, v in vardefs.items() if v.has_default}

    def _write_variables_config(self, config: JupyterDeployVariablesConfigV2) -> None:
        """Write a V2 variables config to disk."""
        variables_config_path = self.get_variables_config_path()
        defaults_for_comments = self._get_defaults_for_comments()
        fs_utils.write_yaml_file_with_comments(
            file_path=variables_config_path,
            content=config.model_dump(),
            key_order=VARIABLES_CONFIG_V2_KEYS_ORDER,
            comments=VARIABLES_CONFIG_V2_COMMENTS,
            commented_entries={"overrides": defaults_for_comments},
        )
        self._variables_config = config

    def generate_defaults_reference_file(self) -> None:
        """Generate (or regenerate) the .jd/variables-defaults.yaml file from template definitions."""
        vardefs = self.get_template_variables()
        defaults = {k: v.default for k, v in vardefs.items() if v.has_default}
        defaults_path = self.get_defaults_reference_path()
        fs_utils.write_yaml_reference_file(
            defaults_path, defaults, header="auto-generated by jupyter-deploy — do not edit"
        )

    def mask_secrets(self) -> None:
        """Rewrite variables.yaml replacing all required_sensitive values with the mask."""
        curr_vars = self.variables_config
        masked_sensitive = {k: MASKED_SECRET_VALUE for k in curr_vars.required_sensitive}

        new_variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required=curr_vars.required,
            required_sensitive=masked_sensitive,
            overrides=curr_vars.overrides,
        )
        self._write_variables_config(new_variables_config)

    def get_variable_names_assigned_in_config(self) -> list[str]:
        """Return the variable names for which the user specified a value in `variables.yaml`."""
        assigned_variable_names: list[str] = []
        assigned_variable_names.extend([k for k, v in self.variables_config.required.items() if v is not None])
        assigned_variable_names.extend(
            [k for k, v in self.variables_config.required_sensitive.items() if v is not None]
        )
        assigned_variable_names.extend([k for k, v in self.variables_config.overrides.items() if v is not None])

        return assigned_variable_names

    def sync_project_variables_config(self, updated_values: dict[str, Any]) -> None:
        """Update the project variables.yaml to match the values."""

        curr_vars = self.variables_config
        new_required_dict = curr_vars.required.copy()
        new_sensitive_dict = curr_vars.required_sensitive.copy()
        new_overrides_dict = curr_vars.overrides.copy()

        for var_name, var_value in updated_values.items():
            if var_name in new_required_dict:
                new_required_dict[var_name] = var_value
            elif var_name in new_sensitive_dict:
                new_sensitive_dict[var_name] = var_value
            elif var_value is not None:  # only pass non-None values for overrides
                new_overrides_dict[var_name] = var_value

        new_variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required=new_required_dict,
            required_sensitive=new_sensitive_dict,
            overrides=new_overrides_dict,
        )
        self._write_variables_config(new_variables_config)

    def reset_recorded_variables(self) -> bool:
        """Reset non-sensitive variables to their original values.

        Returns:
            bool: False (this method modifies config but doesn't delete files)
        """
        new_variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required={k: None for k in self.variables_config.required},
            required_sensitive={k: None for k in self.variables_config.required_sensitive},
            overrides={},
        )
        self._write_variables_config(new_variables_config)
        return False

    def reset_recorded_secrets(self) -> bool:
        """Reset sensitive variables to their original values.

        Returns:
            bool: False (this method modifies config but doesn't delete files)
        """
        variables_config = self.variables_config
        new_variables_config = JupyterDeployVariablesConfigV2(
            schema_version=2,
            required=variables_config.required,
            required_sensitive={k: None for k in variables_config.required_sensitive},
            overrides=variables_config.overrides,
        )
        self._write_variables_config(new_variables_config)
        return False
