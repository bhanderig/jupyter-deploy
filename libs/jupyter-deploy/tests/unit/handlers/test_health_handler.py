import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.handlers.health_handler import HealthHandler
from jupyter_deploy.handlers.payloads import HealthLayer, HealthLayerResult
from jupyter_deploy.handlers.project.open_handler import OpenHealthResult


def _make_handler(
    has_cluster: bool = True,
    has_components: bool = True,
    has_lb: bool = True,
    has_open: bool = True,
) -> tuple[HealthHandler, Mock, Mock, Mock, Mock]:
    with patch.object(HealthHandler, "__init__", lambda self, **kwargs: None):
        handler = HealthHandler.__new__(HealthHandler)
    mock_manifest: Mock = Mock()
    mock_cluster_handler: Mock = Mock()
    mock_component_handler: Mock = Mock()
    mock_open_handler: Mock = Mock()

    handler.display_manager = Mock()
    handler.project_manifest = mock_manifest  # type: ignore[assignment]
    handler._cluster_handler = mock_cluster_handler if has_cluster else None  # type: ignore[assignment]
    handler._component_handler = mock_component_handler if has_components else None  # type: ignore[assignment]
    handler._open_handler = mock_open_handler if has_open else None  # type: ignore[assignment]
    mock_manifest.has_command.side_effect = lambda cmd: cmd == "cluster.loadbalancer.health" and has_lb
    mock_manifest.health = None

    return handler, mock_manifest, mock_cluster_handler, mock_component_handler, mock_open_handler


class TestHealthHandlerCheckCluster(unittest.TestCase):
    def test_cluster_skipped_when_no_handler(self) -> None:
        handler, _, _, _, _ = _make_handler(has_cluster=False)

        result = handler._check_cluster()

        self.assertTrue(result.skipped)
        self.assertEqual(result.layer, "cluster")

    def test_cluster_delegates_to_handler(self) -> None:
        handler, _, mock_cluster, _, _ = _make_handler()
        mock_cluster.health.return_value = HealthLayerResult(
            layer=HealthLayer.CLUSTER,
            name="AWS EKS cluster",
            status_category=StatusCategory.HEALTHY,
            status_text="Active",
            detail="v1.30",
        )

        result = handler._check_cluster()

        self.assertEqual(result.status_category, StatusCategory.HEALTHY)
        self.assertEqual(result.name, "AWS EKS cluster")
        self.assertEqual(result.detail, "v1.30")


class TestHealthHandlerCheckComponents(unittest.TestCase):
    def test_components_skipped_when_no_handler(self) -> None:
        handler, _, _, _, _ = _make_handler(has_components=False)

        results = handler._check_components()

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].skipped)

    def test_components_returns_row_per_component(self) -> None:
        handler, _, _, mock_comp, _ = _make_handler()
        mock_comp.get_all_status.return_value = [
            {"name": "traefik", "status_category": StatusCategory.HEALTHY, "details": "3/3 pods", "sub_component": ""},
            {"name": "dex", "status_category": StatusCategory.DEGRADED, "details": "0/1 pods", "sub_component": ""},
        ]

        results = handler._check_components()

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].name, "traefik")
        self.assertEqual(results[0].status_category, StatusCategory.HEALTHY)
        self.assertEqual(results[1].name, "dex")
        self.assertEqual(results[1].status_category, StatusCategory.DEGRADED)


class TestHealthHandlerCheckLoadBalancer(unittest.TestCase):
    def test_lb_skipped_when_no_cluster_handler(self) -> None:
        handler, _, _, _, _ = _make_handler(has_cluster=False)

        result = handler._check_load_balancer()

        self.assertTrue(result.skipped)

    def test_lb_skipped_when_command_missing(self) -> None:
        handler, _, _, _, _ = _make_handler(has_lb=False)

        result = handler._check_load_balancer()

        self.assertTrue(result.skipped)

    def test_lb_degraded_when_not_found(self) -> None:
        handler, _, mock_cluster, _, _ = _make_handler()
        mock_cluster.get_load_balancer_health.return_value = HealthLayerResult(
            layer=HealthLayer.LOAD_BALANCER,
            name="",
            status_category=StatusCategory.DEGRADED,
            status_text="Not Found",
            detail="no load balancer found",
        )

        result = handler._check_load_balancer()

        self.assertEqual(result.status_category, StatusCategory.DEGRADED)
        self.assertIn("no load balancer found", result.detail)

    def test_lb_healthy_when_active(self) -> None:
        handler, _, mock_cluster, _, _ = _make_handler()
        mock_cluster.get_load_balancer_health.return_value = HealthLayerResult(
            layer=HealthLayer.LOAD_BALANCER,
            name="AWS NLB",
            status_category=StatusCategory.HEALTHY,
            status_text="Active",
            detail="",
        )

        result = handler._check_load_balancer()

        self.assertEqual(result.status_category, StatusCategory.HEALTHY)
        self.assertEqual(result.name, "AWS NLB")
        self.assertEqual(result.status_text, "Active")

    def test_lb_in_progress_when_provisioning(self) -> None:
        handler, _, mock_cluster, _, _ = _make_handler()
        mock_cluster.get_load_balancer_health.return_value = HealthLayerResult(
            layer=HealthLayer.LOAD_BALANCER,
            name="AWS NLB",
            status_category=StatusCategory.IN_PROGRESS,
            status_text="Provisioning",
            detail="",
        )

        result = handler._check_load_balancer()

        self.assertEqual(result.status_category, StatusCategory.IN_PROGRESS)
        self.assertEqual(result.status_text, "Provisioning")


class TestHealthHandlerCheckConnection(unittest.TestCase):
    def test_connection_skipped_when_no_open_handler(self) -> None:
        handler, _, _, _, _ = _make_handler(has_open=False)

        result = handler._check_connection()

        self.assertTrue(result.skipped)

    def test_connection_healthy_when_expected_status(self) -> None:
        handler, _, _, _, mock_open = _make_handler()
        mock_open.health.return_value = OpenHealthResult(
            url="https://app.example.com",
            healthy=True,
            detail="app.example.com -> 1.2.3.4, status=200",
        )

        result = handler._check_connection()

        self.assertEqual(result.status_category, StatusCategory.HEALTHY)
        self.assertIn("app.example.com", result.detail)

    def test_connection_degraded_when_dns_fails(self) -> None:
        handler, _, _, _, mock_open = _make_handler()
        mock_open.health.return_value = OpenHealthResult(
            url="https://app.example.com",
            healthy=False,
            detail="app.example.com does not resolve: [Errno -2] Name or service not known",
        )

        result = handler._check_connection()

        self.assertEqual(result.status_category, StatusCategory.DEGRADED)
        self.assertIn("does not resolve", result.detail)

    def test_connection_uses_manifest_expected_status(self) -> None:
        handler, mock_manifest, _, _, mock_open = _make_handler()
        mock_health_config: Mock = Mock()
        mock_health_config.expected_status_code = 302
        mock_health_config.load_balancer_port = 443
        mock_manifest.health = mock_health_config
        mock_open.health.return_value = OpenHealthResult(
            url="https://app.example.com",
            healthy=True,
            detail="app.example.com -> 1.2.3.4, status=302",
        )

        result = handler._check_connection()

        mock_open.health.assert_called_once_with(expected_status_code=302, port=443)
        self.assertEqual(result.status_category, StatusCategory.HEALTHY)


class TestHealthHandlerCheckLayer(unittest.TestCase):
    def test_check_layer_raises_on_unknown(self) -> None:
        handler, _, _, _, _ = _make_handler()

        with self.assertRaises(ValueError) as ctx:
            handler.check_layer("bogus")

        self.assertIn("Unknown health layer", str(ctx.exception))

    def test_check_layer_raises_on_connection(self) -> None:
        handler, _, _, _, _ = _make_handler()

        with self.assertRaises(ValueError):
            handler.check_layer("connection")

    def test_check_layer_returns_list(self) -> None:
        handler, _, mock_cluster, _, _ = _make_handler()
        mock_cluster.health.return_value = HealthLayerResult(
            layer=HealthLayer.CLUSTER,
            name="c",
            status_category=StatusCategory.HEALTHY,
            status_text="Active",
            detail="v1.30",
        )

        results = handler.check_layer("cluster")

        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 1)
