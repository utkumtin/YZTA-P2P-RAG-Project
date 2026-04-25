from typing import Literal

from pydantic import BaseModel


class ServiceStatus(BaseModel):
    status: Literal["ok", "degraded", "unreachable"]
    latency_ms: float | None = None
    detail: str | None = None


class HealthDetailedResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    services: dict[str, ServiceStatus]
