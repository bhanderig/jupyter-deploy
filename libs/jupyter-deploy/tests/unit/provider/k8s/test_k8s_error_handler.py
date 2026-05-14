import json
import unittest

from kubernetes.client.exceptions import ApiException

from jupyter_deploy.exceptions import (
    InvalidProviderCredentialsError,
    ProviderPermissionError,
    ResourceNotFoundError,
)
from jupyter_deploy.provider.k8s.k8s_error_handler import k8s_error_context_manager


def _api_exception(status: int, reason: str, body: dict | None = None) -> ApiException:
    e = ApiException(status=status, reason=reason)
    if body is not None:
        e.body = json.dumps(body)
    return e


def _not_found_body(kind: str, name: str) -> dict:
    return {
        "kind": "Status",
        "message": f'{kind} "{name}" not found',
        "reason": "NotFound",
        "details": {"name": name, "kind": kind},
        "code": 404,
    }


class TestK8sErrorContextManager(unittest.TestCase):
    def test_401_raises_invalid_provider_credentials(self) -> None:
        with self.assertRaises(InvalidProviderCredentialsError) as ctx, k8s_error_context_manager():
            raise _api_exception(401, "Unauthorized", {"message": "token expired"})

        self.assertEqual(ctx.exception.provider_name.value, "Kubernetes")

    def test_403_raises_provider_permission_error(self) -> None:
        with self.assertRaises(ProviderPermissionError) as ctx, k8s_error_context_manager():
            raise _api_exception(403, "Forbidden", {"message": "forbidden: User cannot get nodes"})

        self.assertEqual(ctx.exception.provider_name.value, "Kubernetes")
        self.assertIn("forbidden", ctx.exception.original_message)

    def test_404_raises_resource_not_found(self) -> None:
        body = _not_found_body("nodes", "i-do-not-exist")
        with self.assertRaises(ResourceNotFoundError) as ctx, k8s_error_context_manager():
            raise _api_exception(404, "Not Found", body)

        self.assertEqual(ctx.exception.resource_kind, "nodes")
        self.assertEqual(ctx.exception.resource_name, "i-do-not-exist")
        self.assertIn("i-do-not-exist", str(ctx.exception))

    def test_404_with_scope_includes_scope_in_message(self) -> None:
        body = _not_found_body("workspaces", "my-ws")
        with self.assertRaises(ResourceNotFoundError) as ctx, k8s_error_context_manager(scope="my-namespace"):
            raise _api_exception(404, "Not Found", body)

        self.assertEqual(ctx.exception.scope, "my-namespace")
        self.assertIn("in 'my-namespace'", str(ctx.exception))

    def test_404_without_scope_omits_scope_in_message(self) -> None:
        body = _not_found_body("nodes", "node-1")
        with self.assertRaises(ResourceNotFoundError) as ctx, k8s_error_context_manager():
            raise _api_exception(404, "Not Found", body)

        self.assertIsNone(ctx.exception.scope)
        self.assertNotIn("in '", str(ctx.exception))

    def test_404_with_no_body_uses_defaults(self) -> None:
        with self.assertRaises(ResourceNotFoundError) as ctx, k8s_error_context_manager():
            raise _api_exception(404, "Not Found")

        self.assertEqual(ctx.exception.resource_kind, "resource")
        self.assertEqual(ctx.exception.resource_name, "")

    def test_404_with_malformed_body(self) -> None:
        e = ApiException(status=404, reason="Not Found")
        e.body = "not json"
        with self.assertRaises(ResourceNotFoundError) as ctx, k8s_error_context_manager():
            raise e

        self.assertEqual(ctx.exception.resource_kind, "resource")

    def test_other_status_reraises(self) -> None:
        with self.assertRaises(ApiException), k8s_error_context_manager():
            raise _api_exception(409, "Conflict")

    def test_no_exception_passes_through(self) -> None:
        with k8s_error_context_manager():
            result = 1 + 1

        self.assertEqual(result, 2)

    def test_non_api_exception_passes_through(self) -> None:
        with self.assertRaises(ValueError), k8s_error_context_manager():
            raise ValueError("unrelated")
