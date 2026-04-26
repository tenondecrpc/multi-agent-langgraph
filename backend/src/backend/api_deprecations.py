from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ApiDeprecation(BaseModel):
    deprecation_id: str
    route: str
    method: str
    version: str
    deprecated_at: datetime
    sunset_at: datetime
    rationale: str
    replacement_route: str | None = None
    active: bool = True

    @property
    def method_normalized(self) -> str:
        return self.method.upper()


def find_api_deprecation(
    deprecations: tuple[ApiDeprecation, ...],
    *,
    route: str,
    method: str,
    version: str,
) -> ApiDeprecation | None:
    normalized_method = method.upper()
    for deprecation in deprecations:
        if not deprecation.active:
            continue
        if deprecation.route != route:
            continue
        if deprecation.method_normalized != normalized_method:
            continue
        if deprecation.version != version:
            continue
        return deprecation
    return None
