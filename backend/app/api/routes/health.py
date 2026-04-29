import asyncio
import time

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from qdrant_client import AsyncQdrantClient

from app.config import get_settings
from app.models.health import HealthDetailedResponse, ServiceStatus

router = APIRouter()
settings = get_settings()


@router.get("")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/live")
async def liveness():
    return {"status": "ok"}


async def _check_redis(timeout: float = 2.0) -> ServiceStatus:
    url = f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    client = aioredis.from_url(url, socket_connect_timeout=timeout)
    t0 = time.perf_counter()
    try:
        async with asyncio.timeout(timeout):
            await client.ping()
        latency = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceStatus(status="ok", latency_ms=latency)
    except Exception as exc:
        return ServiceStatus(status="unreachable", detail=str(exc))
    finally:
        await client.aclose()


async def _check_qdrant(timeout: float = 2.0) -> ServiceStatus:
    client = AsyncQdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        timeout=timeout,
    )
    t0 = time.perf_counter()
    try:
        async with asyncio.timeout(timeout):
            await client.get_collections()
        latency = round((time.perf_counter() - t0) * 1000, 2)
        return ServiceStatus(status="ok", latency_ms=latency)
    except Exception as exc:
        return ServiceStatus(status="unreachable", detail=str(exc))
    finally:
        await client.close()


@router.get("/ready")
async def readiness():
    redis_status, qdrant_status = await asyncio.gather(
        _check_redis(), _check_qdrant()
    )
    all_ok = redis_status.status == "ok" and qdrant_status.status == "ok"
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ok" if all_ok else "unavailable",
            "services": {
                "redis": redis_status.model_dump(exclude_none=True),
                "qdrant": qdrant_status.model_dump(exclude_none=True),
            },
        },
    )


@router.get("/detailed", response_model=HealthDetailedResponse)
async def health_detailed():
    redis_status, qdrant_status = await asyncio.gather(
        _check_redis(), _check_qdrant()
    )
    overall = (
        "ok"
        if redis_status.status == "ok" and qdrant_status.status == "ok"
        else "degraded"
    )
    return HealthDetailedResponse(
        status=overall,
        app=settings.APP_NAME,
        version=settings.APP_VERSION,
        services={"redis": redis_status, "qdrant": qdrant_status},
    )
