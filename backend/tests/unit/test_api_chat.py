from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes.chat import chat
from app.services.chat_service import ChatRequest


def _req(question="Belgedeki madde 5 nedir?", doc_ids=None):
    return ChatRequest(
        question=question,
        session_id="sess-abc",
        document_ids=doc_ids or [],
    )


def _http_req(cache=None):
    r = MagicMock()
    r.app.state.semantic_cache = cache
    return r


async def test_bos_soru_400_dondurur():
    with pytest.raises(HTTPException) as exc:
        await chat(_req(question="   "), _http_req())
    assert exc.value.status_code == 400


async def test_cache_yok_placeholder_doner():
    result = await chat(_req(), _http_req(cache=None))
    assert result.question == "Belgedeki madde 5 nedir?"
    assert isinstance(result.sources, list)


async def test_cache_hit_dogrudan_doner():
    cached = {
        "question": "önbellekli soru",
        "answer": "önbellekten gelen cevap",
        "sources": [],
    }
    mock_cache = AsyncMock()
    mock_cache.get = AsyncMock(return_value=cached)

    result = await chat(_req(question="önbellekli soru"), _http_req(cache=mock_cache))
    assert result.answer == "önbellekten gelen cevap"
    mock_cache.set.assert_not_called()


async def test_cache_miss_kaydedilir(mock_cache):
    result = await chat(_req(), _http_req(cache=mock_cache))
    mock_cache.set.assert_called_once()
    assert result is not None
