from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from kubernetes.client import ApiClient, AppsV1Api, CoreV1Api


@dataclass(frozen=True)
class DeploymentStatus:
    name: str
    available: bool
    ready_replicas: int
    total_replicas: int
    conditions: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class DeploymentInfo:
    name: str
    image: str
    replicas: int
    ready_replicas: int
    conditions: list[dict[str, str]]
    resource: dict[str, Any] = field(default_factory=dict)


def _parse_conditions(deployment: object) -> list[dict[str, str]]:
    status = getattr(deployment, "status", None)
    conditions = getattr(status, "conditions", None) if status else None
    if not conditions:
        return []
    return [
        {
            "type": getattr(c, "type", ""),
            "status": getattr(c, "status", ""),
            "message": getattr(c, "message", "") or "",
        }
        for c in conditions
    ]


def _is_available(conditions: list[dict[str, str]]) -> bool:
    for c in conditions:
        if c["type"] == "Available":
            return c["status"] == "True"
    return False


def get_deployment_status(apps_api: AppsV1Api, name: str, namespace: str) -> DeploymentStatus:
    """Return replica counts and availability for a Deployment."""
    deployment = apps_api.read_namespaced_deployment(name=name, namespace=namespace)
    deploy_name = deployment.metadata.name if deployment.metadata else ""
    status = deployment.status
    ready = status.ready_replicas or 0 if status else 0
    total = status.replicas or 0 if status else 0
    conditions = _parse_conditions(deployment)
    return DeploymentStatus(
        name=deploy_name,
        available=_is_available(conditions),
        ready_replicas=ready,
        total_replicas=total,
        conditions=conditions,
    )


def get_deployment(apps_api: AppsV1Api, name: str, namespace: str) -> DeploymentInfo:
    """Return detailed info including the full serialized resource."""
    deployment = apps_api.read_namespaced_deployment(name=name, namespace=namespace)
    deploy_name = deployment.metadata.name if deployment.metadata else ""
    spec = deployment.spec
    image = ""
    if spec and spec.template and spec.template.spec and spec.template.spec.containers:
        image = spec.template.spec.containers[0].image or ""
    status = deployment.status
    replicas = spec.replicas or 0 if spec else 0
    ready = status.ready_replicas or 0 if status else 0
    conditions = _parse_conditions(deployment)
    resource: dict[str, Any] = ApiClient().sanitize_for_serialization(deployment)
    return DeploymentInfo(
        name=deploy_name,
        image=image,
        replicas=replicas,
        ready_replicas=ready,
        conditions=conditions,
        resource=resource,
    )


@dataclass(frozen=True)
class PodHealthInfo:
    name: str
    phase: str
    reason: str
    last_transition: str


def get_deployment_oldest_pod(
    apps_api: AppsV1Api, core_api: CoreV1Api, name: str, namespace: str
) -> PodHealthInfo | None:
    """Return health info for the oldest pod of a deployment."""
    deployment = apps_api.read_namespaced_deployment(name=name, namespace=namespace)
    match_labels = deployment.spec.selector.match_labels if deployment.spec and deployment.spec.selector else None
    if not match_labels:
        return None
    label_selector = ",".join(f"{k}={v}" for k, v in match_labels.items())
    pods = core_api.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
    if not pods.items:
        return None

    pods.items.sort(
        key=lambda p: (
            p.metadata.creation_timestamp
            if p.metadata and p.metadata.creation_timestamp
            else datetime.max.replace(tzinfo=UTC)
        ),
    )
    oldest = pods.items[0]
    pod_name = oldest.metadata.name if oldest.metadata else ""
    status = oldest.status
    phase = status.phase or "Unknown" if status else "Unknown"
    reason = ""
    last_transition = ""

    if status and status.container_statuses:
        for cs in status.container_statuses:
            state = cs.state
            if state and state.waiting:
                reason = state.waiting.reason or ""
                break
            if state and state.terminated:
                reason = state.terminated.reason or ""
                break

    if status and status.conditions:
        transitions = [c.last_transition_time for c in status.conditions if c.last_transition_time]
        if transitions:
            latest = max(transitions)
            last_transition = _format_time(latest)

    return PodHealthInfo(name=pod_name, phase=phase, reason=reason, last_transition=last_transition)


def _format_time(dt: object | None) -> str:
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.isoformat()
    return str(dt)


def rollout_restart(apps_api: AppsV1Api, name: str, namespace: str) -> None:
    """Trigger a rolling restart by changing the annotation that the deployment controller watches.

    The K8s API has no rollout verb; this replicates what kubectl does."""
    body = {
        "spec": {
            "template": {
                "metadata": {"annotations": {"kubectl.kubernetes.io/restartedAt": datetime.now(UTC).isoformat()}}
            }
        }
    }
    apps_api.patch_namespaced_deployment(name=name, namespace=namespace, body=body)
