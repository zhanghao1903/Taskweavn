"""HTTP helpers for local Settings routes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from taskweavn.server.settings_config import (
    SettingsConfigStorageError,
    SettingsConfigValidationError,
)
from taskweavn.server.transport import HttpApiRequest, HttpApiResponse
from taskweavn.server.ui_contract import ApiError
from taskweavn.server.ui_http_responses import (
    _error_response,
    _json_response,
    _request_id_hint,
)


class SettingsReadinessGateway(Protocol):
    """Read-only Settings / first-run readiness source."""

    def get_readiness(self) -> dict[str, Any]: ...


class SettingsConfigGateway(Protocol):
    """Product 1.0 local Settings config source and write gateway."""

    def get_config(self) -> dict[str, Any]: ...

    def update_config(self, payload: Mapping[str, Any]) -> dict[str, Any]: ...

    def get_readiness(self) -> dict[str, Any]: ...

    def recheck_readiness(self) -> dict[str, Any]: ...


def _settings_readiness_response(
    request: HttpApiRequest,
    gateway: SettingsReadinessGateway | None,
) -> HttpApiResponse:
    if gateway is None:
        return _missing_gateway_response(request, route="settings_readiness")
    return _json_response(
        {
            "ok": True,
            "data": gateway.get_readiness(),
            "error": None,
        }
    )


def _settings_readiness_recheck_response(
    request: HttpApiRequest,
    gateway: SettingsReadinessGateway | SettingsConfigGateway | None,
) -> HttpApiResponse:
    if gateway is None:
        return _missing_gateway_response(request, route="settings_readiness_recheck")
    recheck = getattr(gateway, "recheck_readiness", None)
    data = (
        recheck()
        if callable(recheck)
        else gateway.get_readiness()
    )
    return _json_response(
        {
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _settings_config_response(
    request: HttpApiRequest,
    gateway: SettingsConfigGateway | None,
) -> HttpApiResponse:
    if gateway is None:
        return _missing_gateway_response(request, route="settings_config")

    method = request.method.upper()
    try:
        if method == "GET":
            data = gateway.get_config()
        elif method == "PATCH":
            if request.body is None:
                return _error_response(
                    400,
                    ApiError(
                        code="bad_request",
                        message="request body must be a JSON object",
                    ),
                    request_id=_request_id_hint(request),
                )
            data = gateway.update_config(request.body)
        else:
            return _error_response(
                405,
                ApiError(
                    code="bad_request",
                    message="settings config requires GET or PATCH",
                    details={"allowed_methods": ["GET", "PATCH"]},
                ),
                request_id=_request_id_hint(request),
                headers={"allow": "GET, PATCH"},
            )
    except SettingsConfigValidationError as exc:
        return _error_response(
            400,
            exc.to_api_error(),
            request_id=_request_id_hint(request),
        )
    except SettingsConfigStorageError:
        return _error_response(
            500,
            ApiError(
                code="internal_error",
                message="settings config storage failed",
                retryable=True,
                details={"route": "settings_config"},
            ),
            request_id=_request_id_hint(request),
        )

    return _json_response(
        {
            "ok": True,
            "data": data,
            "error": None,
        }
    )


def _missing_gateway_response(
    request: HttpApiRequest,
    *,
    route: str,
) -> HttpApiResponse:
    return _error_response(
        503,
        ApiError(
            code="internal_error",
            message=f"{route.replace('_', ' ')} gateway is not configured",
            details={"route": route},
        ),
        request_id=_request_id_hint(request),
    )


__all__ = [
    "SettingsConfigGateway",
    "SettingsReadinessGateway",
    "_settings_config_response",
    "_settings_readiness_recheck_response",
    "_settings_readiness_response",
]
