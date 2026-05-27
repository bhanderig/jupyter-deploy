from jupyter_deploy.engine.supervised_execution import DisplayManager
from jupyter_deploy.enum import StatusCategory
from jupyter_deploy.exceptions import CommandNotImplementedError
from jupyter_deploy.handlers.base_project_handler import BaseProjectHandler
from jupyter_deploy.handlers.payloads import ConnectionResult, HealthLayer, HealthLayerResult
from jupyter_deploy.handlers.project.open_handler import OpenHandler
from jupyter_deploy.handlers.resource.cluster_handler import ClusterHandler
from jupyter_deploy.handlers.resource.component_handler import ComponentHandler


class HealthHandler(BaseProjectHandler):
    """Handler class to orchestrate full-stack health checks."""

    _cluster_handler: ClusterHandler | None
    _component_handler: ComponentHandler | None
    _open_handler: OpenHandler | None

    def __init__(self, display_manager: DisplayManager) -> None:
        super().__init__(display_manager=display_manager)

        health_config = self.project_manifest.health
        if not health_config or not health_config.active:
            raise CommandNotImplementedError("health command is not enabled for this template")

        if self.project_manifest.has_command("cluster.status"):
            self._cluster_handler = ClusterHandler(display_manager=display_manager)
        else:
            self._cluster_handler = None

        try:
            self.project_manifest.get_components()
            self._component_handler = ComponentHandler(display_manager=display_manager)
        except CommandNotImplementedError:
            self._component_handler = None

        if any(v.name == "open_url" for v in (self.project_manifest.values or [])):
            self._open_handler = OpenHandler()
        else:
            self._open_handler = None

    def check_all(self) -> tuple[list[HealthLayerResult], ConnectionResult]:
        """Run all health layers and return layer results + connection result."""
        results: list[HealthLayerResult] = []
        results.append(self._check_cluster())
        results.append(self._check_load_balancer())
        results.extend(self._check_components())
        connection = self._check_connection()
        return results, connection

    def check_layer(self, layer: HealthLayer | str) -> list[HealthLayerResult]:
        """Run a single health layer by name."""
        if layer == HealthLayer.CLUSTER:
            return [self._check_cluster()]
        elif layer == HealthLayer.LOAD_BALANCER:
            return [self._check_load_balancer()]
        elif layer == HealthLayer.COMPONENTS:
            return self._check_components()
        valid = ", ".join(h.value for h in HealthLayer)
        raise ValueError(f"Unknown health layer: '{layer}'. Valid layers: {valid}")

    def check_connection(self) -> ConnectionResult:
        """Run just the connection check."""
        return self._check_connection()

    def _check_cluster(self) -> HealthLayerResult:
        if not self._cluster_handler:
            return HealthLayerResult(
                layer=HealthLayer.CLUSTER,
                name="",
                status_category=StatusCategory.HEALTHY,
                status_text="",
                detail="",
                skipped=True,
            )
        return self._cluster_handler.health()

    def _check_components(self) -> list[HealthLayerResult]:
        if not self._component_handler:
            return [
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name="",
                    status_category=StatusCategory.HEALTHY,
                    status_text="",
                    detail="",
                    skipped=True,
                )
            ]

        statuses = self._component_handler.get_all_status()
        results: list[HealthLayerResult] = []

        for comp in statuses:
            category = comp.get("status_category", "")
            if category == StatusCategory.DEGRADED:
                status_category = StatusCategory.DEGRADED
            elif category == StatusCategory.IN_PROGRESS:
                status_category = StatusCategory.IN_PROGRESS
            else:
                status_category = StatusCategory.HEALTHY

            results.append(
                HealthLayerResult(
                    layer=HealthLayer.COMPONENTS,
                    name=comp["name"],
                    status_category=status_category,
                    status_text=comp.get("status", ""),
                    detail=comp.get("details", ""),
                    sub_component=comp.get("sub_component", ""),
                )
            )

        return results

    def _check_load_balancer(self) -> HealthLayerResult:
        if not self._cluster_handler or not self.project_manifest.has_command("cluster.loadbalancer.health"):
            return HealthLayerResult(
                layer=HealthLayer.LOAD_BALANCER,
                name="",
                status_category=StatusCategory.HEALTHY,
                status_text="",
                detail="",
                skipped=True,
            )
        return self._cluster_handler.get_load_balancer_health()

    def _check_connection(self) -> ConnectionResult:
        if not self._open_handler:
            return ConnectionResult(
                status_category=StatusCategory.HEALTHY,
                detail="",
                skipped=True,
            )

        health_config = self.project_manifest.health
        expected_status_code = health_config.expected_status_code if health_config else 200
        port = health_config.load_balancer_port if health_config else 443

        result = self._open_handler.health(expected_status_code=expected_status_code, port=port)

        if result.healthy:
            return ConnectionResult(
                status_category=StatusCategory.HEALTHY,
                detail=result.detail,
            )
        return ConnectionResult(
            status_category=StatusCategory.DEGRADED,
            detail=result.detail,
        )
