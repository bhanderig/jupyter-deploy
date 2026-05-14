import json
import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.api.k8s.custom import CustomObjectResult, CustomResourceRef
from jupyter_deploy.engine.supervised_execution import NullDisplay
from jupyter_deploy.exceptions import InstructionNotFoundError
from jupyter_deploy.provider.k8s.k8s_custom_runner import K8sCustomRunner
from jupyter_deploy.provider.resolved_argdefs import ResolvedInstructionArgument, StrResolvedInstructionArgument

WORKSPACE_REF = CustomResourceRef(group="workspace.jupyter.org", version="v1alpha1", plural="workspaces")


def _crd_args(
    scope: str = "default",
) -> dict[str, ResolvedInstructionArgument]:
    args: dict[str, ResolvedInstructionArgument] = {
        "group": StrResolvedInstructionArgument(argument_name="group", value=WORKSPACE_REF.group),
        "version": StrResolvedInstructionArgument(argument_name="version", value=WORKSPACE_REF.version),
        "plural": StrResolvedInstructionArgument(argument_name="plural", value=WORKSPACE_REF.plural),
    }
    if scope:
        args["scope"] = StrResolvedInstructionArgument(argument_name="scope", value=scope)
    return args


class TestK8sCustomRunner(unittest.TestCase):
    def _make_runner(self) -> K8sCustomRunner:
        mock_api_client: Mock = Mock()
        with patch("jupyter_deploy.provider.k8s.k8s_custom_runner.client") as mock_client_mod:
            mock_client_mod.CustomObjectsApi.return_value = Mock()
            runner = K8sCustomRunner(NullDisplay(), api_client=mock_api_client)
        return runner

    @patch("jupyter_deploy.provider.k8s.k8s_custom_runner.k8s_custom")
    def test_list_returns_names_and_items(self, mock_k8s_custom: Mock) -> None:
        runner = self._make_runner()
        items = [{"metadata": {"name": "ws-1"}}, {"metadata": {"name": "ws-2"}}]
        mock_k8s_custom.list_namespaced.return_value = (items, None)

        result = runner.execute_instruction(instruction_name="list", resolved_arguments=_crd_args())

        self.assertEqual(result["Names"].value, ["ws-1", "ws-2"])
        self.assertEqual(json.loads(result["Items"].value), items)
        self.assertEqual(result["NextToken"].value, "")
        mock_k8s_custom.list_namespaced.assert_called_once_with(
            runner.custom_api, ref=WORKSPACE_REF, namespace="default", limit=None, _continue=None
        )

    @patch("jupyter_deploy.provider.k8s.k8s_custom_runner.k8s_custom")
    def test_get_returns_resource(self, mock_k8s_custom: Mock) -> None:
        runner = self._make_runner()
        resource = {"metadata": {"name": "ws-1"}, "spec": {"image": "jupyter/base-notebook"}}
        mock_k8s_custom.get_namespaced.return_value = CustomObjectResult(name="ws-1", resource=resource)

        args = _crd_args()
        args["name"] = StrResolvedInstructionArgument(argument_name="name", value="ws-1")

        result = runner.execute_instruction(instruction_name="get", resolved_arguments=args)

        self.assertEqual(result["Name"].value, "ws-1")
        self.assertEqual(json.loads(result["Resource"].value)["spec"]["image"], "jupyter/base-notebook")
        mock_k8s_custom.get_namespaced.assert_called_once_with(
            runner.custom_api, ref=WORKSPACE_REF, namespace="default", name="ws-1"
        )

    @patch("jupyter_deploy.provider.k8s.k8s_custom_runner.k8s_custom")
    def test_patch_parses_body_json(self, mock_k8s_custom: Mock) -> None:
        runner = self._make_runner()
        patch_body = {"spec": {"replicas": 2}}
        mock_k8s_custom.patch_namespaced.return_value = CustomObjectResult(
            name="ws-1", resource={"metadata": {"name": "ws-1"}, "spec": {"replicas": 2}}
        )

        args = _crd_args()
        args["name"] = StrResolvedInstructionArgument(argument_name="name", value="ws-1")
        args["body"] = StrResolvedInstructionArgument(argument_name="body", value=json.dumps(patch_body))

        result = runner.execute_instruction(instruction_name="patch", resolved_arguments=args)

        self.assertEqual(result["Name"].value, "ws-1")
        mock_k8s_custom.patch_namespaced.assert_called_once_with(
            runner.custom_api, ref=WORKSPACE_REF, namespace="default", name="ws-1", body=patch_body
        )

    @patch("jupyter_deploy.provider.k8s.k8s_custom_runner.k8s_custom")
    def test_list_cluster_returns_names(self, mock_k8s_custom: Mock) -> None:
        runner = self._make_runner()
        mock_k8s_custom.list_cluster.return_value = ([{"metadata": {"name": "cr-1"}}], None)

        args = _crd_args(scope="")

        result = runner.execute_instruction(instruction_name="list-cluster", resolved_arguments=args)

        self.assertEqual(result["Names"].value, ["cr-1"])
        self.assertEqual(result["NextToken"].value, "")
        mock_k8s_custom.list_cluster.assert_called_once_with(
            runner.custom_api, ref=WORKSPACE_REF, limit=None, _continue=None
        )

    def test_unknown_instruction_raises_error(self) -> None:
        runner = self._make_runner()

        with self.assertRaises(InstructionNotFoundError):
            runner.execute_instruction(instruction_name="unknown", resolved_arguments={})
