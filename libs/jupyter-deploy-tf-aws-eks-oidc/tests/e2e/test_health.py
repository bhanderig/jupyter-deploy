"""E2E tests for the jd health command on the EKS OIDC template."""

import json

from pytest_jupyter_deploy.deployment import EndToEndDeployment

EXPECTED_CRONJOBS = [
    "jwt-rotator",
]


def test_health_all_layers(e2e_deployment: EndToEndDeployment) -> None:
    """Verify jd health runs all layers and reports status for each."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health"])
    output = result.stdout

    for layer in ["cluster", "load-balancer", "components"]:
        assert layer in output, f"Expected layer '{layer}' in health output"
    assert "Connection" in output, "Expected 'Connection' in health output"


def test_health_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --json returns valid JSON with expected fields."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--json"])
    data = json.loads(result.stdout)

    assert "layers" in data, f"Expected 'layers' key, got: {list(data.keys())}"
    assert "connection" in data, f"Expected 'connection' key, got: {list(data.keys())}"

    layers = data["layers"]
    assert len(layers) >= 3, f"Expected at least 3 layer rows, got {len(layers)}"

    for entry in layers:
        assert "layer" in entry
        assert "name" in entry
        assert "status" in entry
        assert "status_category" in entry
        assert "detail" in entry
        assert "sub_component" in entry
        assert "skipped" in entry
        assert entry["status_category"] in ("healthy", "in-progress", "degraded")

    conn = data["connection"]
    assert "status_category" in conn
    assert "detail" in conn
    assert "skipped" in conn
    assert conn["status_category"] in ("healthy", "degraded")


def test_health_cluster_layer(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --cluster reports healthy with version."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--cluster", "--json"])
    data = json.loads(result.stdout)

    layers = data["layers"]
    assert len(layers) == 1
    assert layers[0]["layer"] == "cluster"
    assert layers[0]["status_category"] == "healthy"
    assert layers[0]["name"] != ""
    assert layers[0]["status"] == "Active"
    assert layers[0]["detail"].startswith("v")
    assert layers[0]["skipped"] is False


def test_health_components_layer(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --components returns one row per manifest component."""
    e2e_deployment.ensure_deployed()

    manifest = e2e_deployment.get_manifest()
    manifest_components = manifest.get_components()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--components", "--json"])
    data = json.loads(result.stdout)

    layers = data["layers"]
    assert len(layers) == len(manifest_components), f"Expected {len(manifest_components)} components, got {len(layers)}"

    names = {entry["name"] for entry in layers}
    for name in manifest_components:
        assert name in names, f"Expected component '{name}' in health output"

    for entry in layers:
        assert entry["layer"] == "components"
        if entry["name"] in EXPECTED_CRONJOBS:
            assert entry["status_category"] in ("healthy", "in-progress"), (
                f"CronJob '{entry['name']}' unexpected status_category: {entry['status_category']}"
            )
        else:
            assert entry["status_category"] == "healthy", (
                f"Component '{entry['name']}' not healthy: status_category={entry['status_category']}"
            )
        assert entry["status"] != ""


def test_health_load_balancer_layer(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --load-balancer reports active state."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--load-balancer", "--json"])
    data = json.loads(result.stdout)

    layers = data["layers"]
    assert len(layers) == 1
    assert layers[0]["layer"] == "load-balancer"
    assert layers[0]["status_category"] == "healthy"
    assert layers[0]["name"] != ""
    assert layers[0]["status"] == "Active"


def test_health_connection_flag(e2e_deployment: EndToEndDeployment) -> None:
    """Verify --connection confirms URL responds with expected status."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "health", "--connection", "--json"])
    data = json.loads(result.stdout)

    assert "connection" in data, f"Expected 'connection' key, got: {list(data.keys())}"
    assert data["layers"] == [], "Expected empty 'layers' with --connection only"
    conn = data["connection"]
    assert conn["status_category"] == "healthy"
    assert "status=" in conn["detail"]
