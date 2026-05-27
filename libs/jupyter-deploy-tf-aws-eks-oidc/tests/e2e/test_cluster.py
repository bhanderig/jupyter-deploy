"""E2E tests for cluster commands on the EKS OIDC template."""

import json
import subprocess
from pathlib import Path

from pytest_jupyter_deploy.deployment import EndToEndDeployment

KUBECONFIG_PATH = Path.home() / ".kube" / "config"

# ── cluster status ──────────────────────────────────────────────────────────


def test_cluster_status_returns_active(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that cluster status returns Active for a running cluster."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "status"])
    assert "Active" in result.stdout, f"Expected 'Active' in output:\n{result.stdout}"


# ── cluster show ────────────────────────────────────────────────────────────


def test_cluster_show_returns_metadata(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that cluster show returns cluster metadata as pretty-printed JSON."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "show"])
    assert result.stdout.strip(), "Expected non-empty output from cluster show"
    assert "endpoint" in result.stdout.lower(), f"Expected 'endpoint' in output:\n{result.stdout}"


def test_cluster_show_json(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that cluster show --json returns valid JSON with expected fields."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "show", "--json"])
    data = json.loads(result.stdout)
    assert "name" in data, f"Expected 'name' key in JSON, got: {list(data.keys())}"
    assert "status" in data, f"Expected 'status' key in JSON, got: {list(data.keys())}"
    assert "endpoint" in data, f"Expected 'endpoint' key in JSON, got: {list(data.keys())}"
    assert "version" in data, f"Expected 'version' key in JSON, got: {list(data.keys())}"
    assert data["status"] == "ACTIVE", f"Expected status 'ACTIVE', got: {data['status']}"
    assert data["endpoint"].startswith("https://"), f"Expected endpoint to start with https://, got: {data['endpoint']}"


# ── cluster login ───────────────────────────────────────────────────────────


def test_cluster_login_configures_kubeconfig(e2e_deployment: EndToEndDeployment) -> None:
    """Verify that cluster login creates a kubeconfig from scratch."""
    e2e_deployment.ensure_deployed()

    backup = KUBECONFIG_PATH.read_bytes() if KUBECONFIG_PATH.exists() else None
    try:
        KUBECONFIG_PATH.unlink(missing_ok=True)

        result = e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "login"])
        output = result.stdout.lower()
        assert "context" in output or "updated" in output or "added" in output, (
            f"Expected kubeconfig update confirmation in output:\n{result.stdout}"
        )
        assert KUBECONFIG_PATH.exists(), "Expected kubeconfig to be created after login"

        config_content = KUBECONFIG_PATH.read_text()
        assert "clusters:" in config_content, "Expected 'clusters:' section in kubeconfig"
        assert "contexts:" in config_content, "Expected 'contexts:' section in kubeconfig"
        show_result = e2e_deployment.cli.run_command(["jupyter-deploy", "cluster", "show", "--json"])
        show_data = json.loads(show_result.stdout)

        kubectl_output = subprocess.run(["kubectl", "cluster-info"], capture_output=True, text=True, check=True)
        assert show_data["endpoint"] in kubectl_output.stdout, (
            f"Expected endpoint {show_data['endpoint']} in kubectl cluster-info output:\n{kubectl_output.stdout}"
        )
    finally:
        if backup is not None:
            KUBECONFIG_PATH.write_bytes(backup)
        elif KUBECONFIG_PATH.exists():
            KUBECONFIG_PATH.unlink()
