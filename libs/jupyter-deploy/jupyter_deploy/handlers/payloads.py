from dataclasses import dataclass
from enum import Enum

from jupyter_deploy.enum import StatusCategory


class HealthLayer(str, Enum):
    """Layers checked by the health command."""

    CLUSTER = "cluster"
    LOAD_BALANCER = "load-balancer"
    COMPONENTS = "components"


@dataclass
class HealthLayerResult:
    """Single row in the health check output table."""

    layer: HealthLayer
    name: str
    status_category: StatusCategory
    status_text: str
    detail: str
    sub_component: str = ""
    skipped: bool = False


@dataclass
class ConnectionResult:
    """Result of the end-to-end connection check."""

    status_category: StatusCategory
    detail: str
    skipped: bool = False
