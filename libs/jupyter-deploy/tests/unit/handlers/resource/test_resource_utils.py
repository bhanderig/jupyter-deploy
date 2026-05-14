import json
import unittest
from unittest.mock import Mock

from jupyter_deploy.handlers.resource.resource_utils import collect_results, evaluate_status_rules, resolve_path
from jupyter_deploy.manifest import JupyterDeployStatusRuleMatchV1, JupyterDeployStatusRuleV1


class TestResolvePath(unittest.TestCase):
    def test_simple_dot_access(self) -> None:
        resource = {"spec": {"desiredStatus": "Running"}}
        self.assertEqual(resolve_path(resource, ".spec.desiredStatus"), "Running")

    def test_array_filter(self) -> None:
        resource = {"status": {"conditions": [{"type": "Available", "status": "True"}]}}
        self.assertEqual(resolve_path(resource, ".status.conditions[type=Available].status"), "True")

    def test_array_filter_no_match(self) -> None:
        resource = {"status": {"conditions": [{"type": "Available", "status": "True"}]}}
        self.assertIsNone(resolve_path(resource, ".status.conditions[type=Degraded].status"))

    def test_missing_key(self) -> None:
        self.assertIsNone(resolve_path({}, ".spec.desiredStatus"))

    def test_non_string_leaf(self) -> None:
        resource = {"spec": {"replicas": 3}}
        self.assertIsNone(resolve_path(resource, ".spec.replicas"))

    def test_non_dict_root(self) -> None:
        self.assertIsNone(resolve_path({"status": "a string"}, ".status.field"))


class TestEvaluateStatusRules(unittest.TestCase):
    RULES = [
        JupyterDeployStatusRuleV1(
            display="Degraded",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Degraded].status", equals="True")],
        ),
        JupyterDeployStatusRuleV1(
            display="Starting",
            all=[
                JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Progressing].status", equals="True"),
                JupyterDeployStatusRuleMatchV1(path=".spec.desiredStatus", equals="Running"),
            ],
        ),
        JupyterDeployStatusRuleV1(
            display="Stopping",
            all=[
                JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Progressing].status", equals="True"),
                JupyterDeployStatusRuleMatchV1(path=".spec.desiredStatus", equals="Stopped"),
            ],
        ),
        JupyterDeployStatusRuleV1(
            display="Stopped",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Stopped].status", equals="True")],
        ),
        JupyterDeployStatusRuleV1(
            display="Running",
            all=[JupyterDeployStatusRuleMatchV1(path=".status.conditions[type=Available].status", equals="True")],
        ),
    ]

    def test_running(self) -> None:
        resource = json.dumps(
            {
                "status": {
                    "conditions": [{"type": "Available", "status": "True"}, {"type": "Stopped", "status": "False"}]
                }
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Running")

    def test_stopped(self) -> None:
        resource = json.dumps(
            {
                "status": {
                    "conditions": [{"type": "Available", "status": "False"}, {"type": "Stopped", "status": "True"}]
                }
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Stopped")

    def test_starting(self) -> None:
        resource = json.dumps(
            {
                "spec": {"desiredStatus": "Running"},
                "status": {
                    "conditions": [{"type": "Progressing", "status": "True"}, {"type": "Stopped", "status": "False"}]
                },
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Starting")

    def test_stopping(self) -> None:
        resource = json.dumps(
            {
                "spec": {"desiredStatus": "Stopped"},
                "status": {
                    "conditions": [{"type": "Progressing", "status": "True"}, {"type": "Available", "status": "False"}]
                },
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Stopping")

    def test_degraded(self) -> None:
        resource = json.dumps(
            {
                "status": {
                    "conditions": [{"type": "Available", "status": "True"}, {"type": "Degraded", "status": "True"}]
                }
            }
        )
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Degraded")

    def test_unknown_on_no_match(self) -> None:
        resource = json.dumps({"status": {"conditions": []}})
        self.assertEqual(evaluate_status_rules(resource, self.RULES), "Unknown")

    def test_unknown_on_invalid_json(self) -> None:
        self.assertEqual(evaluate_status_rules("not-json", self.RULES), "Unknown")

    def test_unknown_on_empty_string(self) -> None:
        self.assertEqual(evaluate_status_rules("", self.RULES), "Unknown")


class TestCollectResults(unittest.TestCase):
    def test_collects_and_strips_prefix(self) -> None:
        mock_runner = Mock()
        mock_runner.get_result_value_with_fallback.side_effect = ["my-ws", '{"spec": {}}']

        mock_result_def_1 = Mock()
        mock_result_def_1.result_name = "server.show.name"
        mock_result_def_2 = Mock()
        mock_result_def_2.result_name = "server.show.resource"

        mock_command = Mock()
        mock_command.cmd = "server.show"
        mock_command.results = [mock_result_def_1, mock_result_def_2]

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result["name"], "my-ws")
        self.assertEqual(result["resource"], {"spec": {}})

    def test_returns_empty_dict_when_no_results(self) -> None:
        mock_runner = Mock()
        mock_command = Mock()
        mock_command.cmd = "server.show"
        mock_command.results = None

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result, {})

    def test_non_json_values_returned_as_strings(self) -> None:
        mock_runner = Mock()
        mock_runner.get_result_value_with_fallback.return_value = "plain-text"

        mock_result_def = Mock()
        mock_result_def.result_name = "host.show.status"

        mock_command = Mock()
        mock_command.cmd = "host.show"
        mock_command.results = [mock_result_def]

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result["status"], "plain-text")

    def test_json_list_values_are_parsed(self) -> None:
        mock_runner = Mock()
        mock_runner.get_result_value_with_fallback.return_value = '["a", "b"]'

        mock_result_def = Mock()
        mock_result_def.result_name = "host.show.items"

        mock_command = Mock()
        mock_command.cmd = "host.show"
        mock_command.results = [mock_result_def]

        result = collect_results(mock_runner, mock_command)

        self.assertEqual(result["items"], ["a", "b"])
