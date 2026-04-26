from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse, Response

from .api_deprecations import ApiDeprecation, find_api_deprecation
from .persistence.telemetry import PersistenceTelemetry

CURRENT_API_MAJOR = 1
SUPPORTED_API_MAJORS = frozenset({CURRENT_API_MAJOR})
API_PREFIX = f"/api/v{CURRENT_API_MAJOR}"

PUBLIC_UNVERSIONED_PREFIXES = (
    "/admin",
    "/auth",
    "/metering",
    "/runtime",
    "/runs",
    "/streams",
    "/webhooks",
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ApiVersioningConfig:
    current_major: int = CURRENT_API_MAJOR
    supported_majors: frozenset[int] = SUPPORTED_API_MAJORS
    redirect_unversioned_paths: bool = True
    deprecations: tuple[ApiDeprecation, ...] = ()
    telemetry: PersistenceTelemetry | None = None


def install_api_versioning(app: FastAPI, config: ApiVersioningConfig | None = None) -> None:
    resolved = config or ApiVersioningConfig()
    app.state.api_versioning = resolved
    _record_deprecation_sunset_gauges(resolved)

    @app.middleware("http")
    async def api_version_middleware(request: Request, call_next) -> Response:
        redirect = _redirect_unversioned_request(request, resolved)
        if redirect is not None:
            return redirect

        negotiated = _negotiate_accept_version(request, resolved)
        if isinstance(negotiated, JSONResponse):
            return negotiated

        request.state.api_major = negotiated
        response = await call_next(request)
        if request.url.path.startswith("/api/"):
            response.headers.setdefault("X-API-Version", f"v{negotiated}")
            _apply_deprecation_headers(request, response, resolved, negotiated)
        return response

    @app.get(f"/api/v{resolved.current_major}/openapi.json", include_in_schema=False)
    def versioned_openapi() -> dict[str, Any]:
        return build_versioned_openapi(app, resolved.current_major)


def build_versioned_openapi(app: FastAPI, major: int) -> dict[str, Any]:
    version_prefix = f"/api/v{major}"
    schema = get_openapi(
        title=f"{app.title} API v{major}",
        version=f"v{major}",
        routes=app.routes,
        description=app.description,
    )
    schema["paths"] = {
        path: path_schema for path, path_schema in schema.get("paths", {}).items() if path.startswith(version_prefix)
    }
    return schema


def _redirect_unversioned_request(request: Request, config: ApiVersioningConfig) -> RedirectResponse | None:
    path = request.url.path
    if path.startswith("/api/"):
        return None
    if not any(path == prefix or path.startswith(f"{prefix}/") for prefix in PUBLIC_UNVERSIONED_PREFIXES):
        return None
    if not config.redirect_unversioned_paths:
        return None
    return RedirectResponse(
        url=str(request.url.replace(path=f"/api/v{config.current_major}{path}")),
        status_code=307,
    )


def _negotiate_accept_version(request: Request, config: ApiVersioningConfig) -> int | JSONResponse:
    value = request.headers.get("Accept-Version")
    if not value:
        return config.current_major

    parsed = _parse_major(value)
    if parsed in config.supported_majors:
        return parsed

    supported = ", ".join(f"v{major}" for major in sorted(config.supported_majors))
    return JSONResponse(
        status_code=406,
        content={
            "detail": "unsupported_api_version",
            "supported_versions": supported,
        },
    )


def _parse_major(value: str) -> int | None:
    token = value.strip().lower()
    if token.startswith("v"):
        token = token[1:]
    if not token.isdigit():
        return None
    return int(token)


def _apply_deprecation_headers(
    request: Request,
    response: Response,
    config: ApiVersioningConfig,
    negotiated_major: int,
) -> None:
    route = request.scope.get("route")
    route_path = getattr(route, "path", request.url.path)
    deprecation = find_api_deprecation(
        config.deprecations,
        route=route_path,
        method=request.method,
        version=f"v{negotiated_major}",
    )
    if deprecation is None:
        return

    response.headers["Deprecation"] = "true"
    response.headers["Sunset"] = deprecation.sunset_at.date().isoformat()
    response.headers["Link"] = f'<{deprecation.replacement_route or route_path}>; rel="successor-version"'
    tenant_id = request.headers.get("X-Tenant-ID", "unknown")
    client_id = request.headers.get("X-Client-ID", "unknown")
    if config.telemetry is not None:
        config.telemetry.increment(
            "devsquad_api_deprecation_hits_total",
            route=route_path,
            version=deprecation.version,
            tenant_id=tenant_id,
        )
    logger.info(
        "api_deprecation_hit",
        extra={
            "tenant_id": tenant_id,
            "route": route_path,
            "version": deprecation.version,
            "method": request.method,
            "client_id": client_id,
        },
    )


def _record_deprecation_sunset_gauges(config: ApiVersioningConfig) -> None:
    if config.telemetry is None:
        return
    now = datetime.now(tz=UTC)
    for deprecation in config.deprecations:
        if not deprecation.active:
            continue
        days_until_sunset = max((deprecation.sunset_at - now).days, 0)
        config.telemetry.set_gauge(
            "devsquad_api_deprecation_sunset_days",
            float(days_until_sunset),
            route=deprecation.route,
            version=deprecation.version,
        )
