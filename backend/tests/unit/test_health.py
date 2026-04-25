import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.routes import health as health_module
from app.models.health import ServiceStatus


# ── _check_redis ──────────────────────────────────────────────────────────────

async def test_check_redis_ok():
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.aclose = AsyncMock()

    with patch("app.api.routes.health.aioredis.from_url", return_value=mock_client):
        result = await health_module._check_redis()

    assert result.status == "ok"
    assert result.latency_ms is not None
    assert result.latency_ms >= 0
    assert result.detail is None


async def test_check_redis_connection_error():
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(side_effect=ConnectionError("connection refused"))
    mock_client.aclose = AsyncMock()

    with patch("app.api.routes.health.aioredis.from_url", return_value=mock_client):
        result = await health_module._check_redis()

    assert result.status == "unreachable"
    assert result.latency_ms is None
    assert "connection refused" in result.detail


async def test_check_redis_timeout():
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock(side_effect=asyncio.TimeoutError())
    mock_client.aclose = AsyncMock()

    with patch("app.api.routes.health.aioredis.from_url", return_value=mock_client):
        result = await health_module._check_redis()

    assert result.status == "unreachable"
    assert result.latency_ms is None


# ── _check_qdrant ─────────────────────────────────────────────────────────────

async def test_check_qdrant_ok():
    mock_client = AsyncMock()
    mock_client.get_collections = AsyncMock(return_value=MagicMock())
    mock_client.close = AsyncMock()

    with patch("app.api.routes.health.AsyncQdrantClient", return_value=mock_client):
        result = await health_module._check_qdrant()

    assert result.status == "ok"
    assert result.latency_ms >= 0
    assert result.detail is None


async def test_check_qdrant_error():
    mock_client = AsyncMock()
    mock_client.get_collections = AsyncMock(side_effect=Exception("connection refused"))
    mock_client.close = AsyncMock()

    with patch("app.api.routes.health.AsyncQdrantClient", return_value=mock_client):
        result = await health_module._check_qdrant()

    assert result.status == "unreachable"
    assert result.detail is not None


# ── /live ─────────────────────────────────────────────────────────────────────

async def test_liveness_always_ok():
    result = await health_module.liveness()
    assert result == {"status": "ok"}


# ── /ready ────────────────────────────────────────────────────────────────────

async def test_readiness_200_when_all_ok():
    ok = ServiceStatus(status="ok", latency_ms=1.5)

    with patch.object(health_module, "_check_redis", AsyncMock(return_value=ok)), \
         patch.object(health_module, "_check_qdrant", AsyncMock(return_value=ok)):
        response = await health_module.readiness()

    assert response.status_code == 200


async def test_readiness_503_when_redis_down():
    ok = ServiceStatus(status="ok", latency_ms=1.5)
    down = ServiceStatus(status="unreachable", detail="refused")

    with patch.object(health_module, "_check_redis", AsyncMock(return_value=down)), \
         patch.object(health_module, "_check_qdrant", AsyncMock(return_value=ok)):
        response = await health_module.readiness()

    assert response.status_code == 503


async def test_readiness_503_when_qdrant_down():
    ok = ServiceStatus(status="ok", latency_ms=2.0)
    down = ServiceStatus(status="unreachable", detail="timeout")

    with patch.object(health_module, "_check_redis", AsyncMock(return_value=ok)), \
         patch.object(health_module, "_check_qdrant", AsyncMock(return_value=down)):
        response = await health_module.readiness()

    assert response.status_code == 503


# ── /detailed ─────────────────────────────────────────────────────────────────

async def test_detailed_always_200_even_when_degraded():
    ok = ServiceStatus(status="ok", latency_ms=1.0)
    down = ServiceStatus(status="unreachable", detail="timeout")

    with patch.object(health_module, "_check_redis", AsyncMock(return_value=down)), \
         patch.object(health_module, "_check_qdrant", AsyncMock(return_value=ok)):
        result = await health_module.health_detailed()

    assert result.status == "degraded"
    assert result.services["redis"].status == "unreachable"
    assert result.services["qdrant"].status == "ok"


async def test_detailed_ok_when_all_services_up():
    ok = ServiceStatus(status="ok", latency_ms=1.0)

    with patch.object(health_module, "_check_redis", AsyncMock(return_value=ok)), \
         patch.object(health_module, "_check_qdrant", AsyncMock(return_value=ok)):
        result = await health_module.health_detailed()

    assert result.status == "ok"
    assert result.app is not None
    assert result.version is not None
