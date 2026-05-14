import contextlib
import json
import re
from typing import Any

from jupyter_deploy.manifest import JupyterDeployStatusRuleV1
from jupyter_deploy.provider import manifest_command_runner as cmd_runner

_ARRAY_FILTER_RE = re.compile(r"^([^\[]+)\[([^=]+)=([^\]]+)\]$")


def resolve_path(resource: dict[str, Any], path: str) -> str | None:
    """Resolve a dotted path against a resource dict.

    Supports two segment forms:
      - Simple key: .spec.desiredStatus
      - Array filter: .status.conditions[type=Degraded].status
    """
    segments = [s for s in path.split(".") if s]
    current: Any = resource
    for segment in segments:
        if not isinstance(current, dict):
            return None
        match = _ARRAY_FILTER_RE.match(segment)
        if match:
            array_key, filter_key, filter_val = match.group(1), match.group(2), match.group(3)
            items = current.get(array_key)
            if not isinstance(items, list):
                return None
            current = next(
                (item for item in items if isinstance(item, dict) and item.get(filter_key) == filter_val), None
            )
            if current is None:
                return None
        else:
            current = current.get(segment)
            if current is None:
                return None
    if isinstance(current, str):
        return current
    return None


def evaluate_status_rules(resource_json: str, rules: list[JupyterDeployStatusRuleV1]) -> str:
    try:
        resource = json.loads(resource_json)
    except (json.JSONDecodeError, TypeError):
        return "Unknown"

    if not isinstance(resource, dict):
        return "Unknown"

    for rule in rules:
        if all(resolve_path(resource, m.path) == m.equals for m in rule.all):
            return rule.display

    return "Unknown"


def collect_results(
    runner: cmd_runner.ManifestCommandRunner,
    command: cmd_runner.JupyterDeployCommandV1,
) -> dict[str, Any]:
    """Collect all results from a command, stripping the command prefix from keys.

    JSON string values are parsed into dicts/lists so callers get structured data.
    """
    prefix = f"{command.cmd}."
    result: dict[str, Any] = {}
    for result_def in command.results or []:
        key = result_def.result_name.removeprefix(prefix)
        value: Any = runner.get_result_value_with_fallback(command, result_def.result_name, str, "")
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            value = json.loads(value)
        result[key] = value
    return result
