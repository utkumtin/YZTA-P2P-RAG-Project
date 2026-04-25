import json
import base64
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from app.core.semantic_cache import SemanticCache


def _make_vec(values: list[float]) -> np.ndarray:
    return np.array(values, dtype=np.float32)


def _encode_vec(vec: np.ndarray) -> str:
    return base64.b64encode(vec.tobytes()).decode()


@pytest.fixture
def embedder():
    mock = MagicMock()
    mock.embed.return_value = _make_vec([1.0, 0.0, 0.0])
    return mock


@pytest.fixture
def redis_client():
    mock = AsyncMock()
    mock.scan_iter.return_value = _async_iter([])
    mock.set = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock()
    return mock


async def _async_iter(items):
    for item in items:
        yield item


@pytest.fixture
def cache(redis_client, embedder):
    return SemanticCache(
        redis_client=redis_client,
        embedder=embedder,
        threshold=0.92,
        ttl=3600,
        max_size=3,
    )


@pytest.mark.asyncio
async def test_get_returns_none_when_index_empty(cache):
    result = await cache.get("herhangi bir soru")
    assert result is None


@pytest.mark.asyncio
async def test_set_stores_in_index_and_redis(cache, redis_client, embedder):
    response = {"answer": "test yanıt", "sources": [], "question": "soru"}
    await cache.set("soru", response)

    assert len(cache._index) == 1
    assert len(cache._meta) == 1
    redis_client.set.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_cached_response_on_high_similarity(cache, embedder):
    response = {"answer": "belge nedir", "sources": [], "question": "belge nedir"}
    embedder.embed.return_value = _make_vec([1.0, 0.0, 0.0])
    await cache.set("belge nedir", response)

    embedder.embed.return_value = _make_vec([1.0, 0.0, 0.0])
    result = await cache.get("belge nedir")

    assert result is not None
    assert result["answer"] == "belge nedir"


@pytest.mark.asyncio
async def test_get_returns_none_on_low_similarity(cache, embedder):
    response = {"answer": "belge nedir", "sources": [], "question": "belge nedir"}
    embedder.embed.return_value = _make_vec([1.0, 0.0, 0.0])
    await cache.set("belge nedir", response)

    embedder.embed.return_value = _make_vec([0.0, 1.0, 0.0])
    result = await cache.get("tamamen farklı bir soru")

    assert result is None


@pytest.mark.asyncio
async def test_clear_empties_index_and_calls_redis(cache, embedder, redis_client):
    embedder.embed.return_value = _make_vec([1.0, 0.0, 0.0])
    await cache.set("soru", {"answer": "a", "sources": [], "question": "soru"})

    await cache.clear()

    assert len(cache._index) == 0
    assert len(cache._meta) == 0
    redis_client.delete.assert_awaited()


@pytest.mark.asyncio
async def test_evicts_oldest_when_max_size_reached(cache, embedder):
    responses = [
        {"answer": f"cevap {i}", "sources": [], "question": f"soru {i}"}
        for i in range(4)
    ]
    for i, r in enumerate(responses):
        embedder.embed.return_value = _make_vec([float(i), 0.0, 0.0])
        await cache.set(f"soru {i}", r)

    assert len(cache._index) == 3


@pytest.mark.asyncio
async def test_load_from_redis_populates_index(redis_client, embedder):
    vec = _make_vec([1.0, 0.0, 0.0])
    entry = {
        "query": "yüklenen soru",
        "response": {"answer": "yüklenen yanıt", "sources": [], "question": "yüklenen soru"},
        "embedding_b64": _encode_vec(vec),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async def _scan_iter(pattern):
        yield b"sc:abc123"

    redis_client.scan_iter = _scan_iter
    redis_client.get.return_value = json.dumps(entry).encode()

    sc = SemanticCache(
        redis_client=redis_client,
        embedder=embedder,
        threshold=0.92,
        ttl=3600,
        max_size=1000,
    )
    await sc.load_from_redis()

    assert len(sc._index) == 1
    assert "sc:abc123" in sc._meta


@pytest.mark.asyncio
async def test_redis_error_does_not_raise(embedder):
    broken_redis = AsyncMock()
    broken_redis.set.side_effect = ConnectionError("redis bağlantısı yok")
    broken_redis.scan_iter.side_effect = ConnectionError("redis bağlantısı yok")

    sc = SemanticCache(
        redis_client=broken_redis,
        embedder=embedder,
        threshold=0.92,
        ttl=3600,
        max_size=1000,
    )

    await sc.load_from_redis()
    await sc.set("soru", {"answer": "a", "sources": [], "question": "soru"})
    result = await sc.get("soru")

    assert result is None
