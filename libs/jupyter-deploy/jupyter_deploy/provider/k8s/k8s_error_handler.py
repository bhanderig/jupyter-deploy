import json
from collections.abc import Generator
from contextlib import contextmanager

from kubernetes.client.exceptions import ApiException

from jupyter_deploy.enum import ProviderType
from jupyter_deploy.exceptions import (
    InvalidInstructionArgumentError,
    InvalidProviderCredentialsError,
    ProviderPermissionError,
    ResourceNotFoundError,
)


def _parse_api_exception_body(e: ApiException) -> tuple[str, str]:
    """Extract message and resource kind from K8s API error body."""
    message = ""
    kind = ""
    if e.body:
        try:
            body = json.loads(e.body)
            message = body.get("message", "")
            details = body.get("details", {})
            kind = details.get("kind", "")
        except (json.JSONDecodeError, AttributeError):
            pass
    return message, kind


def _parse_resource_name_from_message(message: str) -> str:
    """Extract the resource name from K8s error message like 'nodes "foo" not found'."""
    start = message.find('"')
    end = message.find('"', start + 1) if start >= 0 else -1
    if start >= 0 and end > start:
        return message[start + 1 : end]
    return ""


@contextmanager
def k8s_error_context_manager(scope: str | None = None) -> Generator[None, None, None]:
    """Catch kubernetes exceptions and re-raise as jupyter-deploy provider errors."""
    try:
        yield
    except ApiException as e:
        message, kind = _parse_api_exception_body(e)

        if e.status == 401:
            raise InvalidProviderCredentialsError(
                provider_name=ProviderType.K8S,
                original_message=message or str(e),
            ) from e

        if e.status == 400:
            raise InvalidInstructionArgumentError(message or str(e)) from e

        if e.status == 403:
            raise ProviderPermissionError(
                provider_name=ProviderType.K8S,
                operation=None,
                original_message=message or str(e),
            ) from e

        if e.status == 404:
            resource_name = _parse_resource_name_from_message(message)
            raise ResourceNotFoundError(
                resource_kind=kind or "resource",
                resource_name=resource_name,
                original_message=message or str(e),
                scope=scope,
            ) from e

        raise
