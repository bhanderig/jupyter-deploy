import unittest
from unittest.mock import Mock, patch

from kubernetes.client import AppsV1Api
from kubernetes.client.exceptions import ApiException

from jupyter_deploy.api.k8s.apps import (
    DeploymentInfo,
    DeploymentStatus,
    get_deployment,
    get_deployment_status,
    rollout_restart,
)


def _mock_deployment(
    name: str = "traefik",
    ready: int = 1,
    total: int = 1,
    image: str = "traefik:v2.10",
    available: bool = True,
) -> Mock:
    deployment: Mock = Mock()
    deployment.metadata.name = name
    deployment.spec.replicas = total
    deployment.spec.template.spec.containers = [Mock(image=image)]
    deployment.spec.selector.match_labels = {"app": name}
    deployment.status.replicas = total
    deployment.status.ready_replicas = ready

    condition: Mock = Mock()
    condition.type = "Available"
    condition.status = "True" if available else "False"
    condition.message = "Deployment has minimum availability."
    deployment.status.conditions = [condition]

    return deployment


class TestGetDeploymentStatus(unittest.TestCase):
    def test_returns_ready_when_available(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.return_value = _mock_deployment()

        result = get_deployment_status(mock_api, name="traefik", namespace="kube-system")

        self.assertIsInstance(result, DeploymentStatus)
        self.assertEqual(result.name, "traefik")
        self.assertTrue(result.available)
        self.assertEqual(result.ready_replicas, 1)
        self.assertEqual(result.total_replicas, 1)

    def test_returns_not_available_when_degraded(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.return_value = _mock_deployment(ready=0, available=False)

        result = get_deployment_status(mock_api, name="traefik", namespace="kube-system")

        self.assertFalse(result.available)
        self.assertEqual(result.ready_replicas, 0)

    def test_passes_name_and_namespace(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.return_value = _mock_deployment()

        get_deployment_status(mock_api, name="dex", namespace="auth")

        mock_api.read_namespaced_deployment.assert_called_once_with(name="dex", namespace="auth")

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_deployment_status(mock_api, name="missing", namespace="default")


class TestGetDeployment(unittest.TestCase):
    @patch("jupyter_deploy.api.k8s.apps.ApiClient")
    def test_returns_deployment_info(self, mock_api_client_cls: Mock) -> None:
        mock_api_client_cls.return_value.sanitize_for_serialization.return_value = {"kind": "Deployment"}
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.return_value = _mock_deployment(image="dex:v2.36")

        result = get_deployment(mock_api, name="dex", namespace="auth")

        self.assertIsInstance(result, DeploymentInfo)
        self.assertEqual(result.name, "traefik")
        self.assertEqual(result.image, "dex:v2.36")
        self.assertEqual(result.replicas, 1)
        self.assertEqual(result.ready_replicas, 1)
        self.assertIsInstance(result.resource, dict)

    def test_raises_on_not_found(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.read_namespaced_deployment.side_effect = ApiException(status=404, reason="Not Found")

        with self.assertRaises(ApiException):
            get_deployment(mock_api, name="missing", namespace="default")


class TestRolloutRestart(unittest.TestCase):
    def test_patches_deployment_with_annotation(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)

        rollout_restart(mock_api, name="traefik", namespace="kube-system")

        mock_api.patch_namespaced_deployment.assert_called_once()
        call_kwargs = mock_api.patch_namespaced_deployment.call_args
        self.assertEqual(call_kwargs.kwargs["name"], "traefik")
        self.assertEqual(call_kwargs.kwargs["namespace"], "kube-system")
        body = call_kwargs.kwargs["body"]
        annotations = body["spec"]["template"]["metadata"]["annotations"]
        self.assertIn("kubectl.kubernetes.io/restartedAt", annotations)

    def test_raises_on_api_error(self) -> None:
        mock_api: Mock = Mock(spec=AppsV1Api)
        mock_api.patch_namespaced_deployment.side_effect = ApiException(status=403, reason="Forbidden")

        with self.assertRaises(ApiException):
            rollout_restart(mock_api, name="traefik", namespace="kube-system")
