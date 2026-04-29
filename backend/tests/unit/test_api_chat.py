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


def _http_req(pipeline=None):
    r = MagicMock()
    r.app.state.rag_pipeline = pipeline
    return r


def _mock_pipeline(answer="Test cevabı", sources=None):
    p = MagicMock()
    p.query = AsyncMock(return_value=(answer, sources or []))
    return p


@pytest.mark.asyncio
async def test_bos_soru_400_dondurur():
    with pytest.raises(HTTPException) as exc:
        await chat(_req(question="   "), _http_req())
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_pipeline_yok_placeholder_doner():
    result = await chat(_req(), _http_req(pipeline=None))
    assert result.question == "Belgedeki madde 5 nedir?"
    assert "hazır değil" in result.answer
    assert isinstance(result.sources, list)


@pytest.mark.asyncio
async def test_pipeline_cevap_doner():
    pipeline = _mock_pipeline(answer="Madde 5 şunu der...")
    result = await chat(_req(), _http_req(pipeline=pipeline))
    assert result.answer == "Madde 5 şunu der..."
    pipeline.query.assert_awaited_once()


@pytest.mark.asyncio
async def test_pipeline_kaynak_doner():
    sources = [{"doc_id": "abc", "filename": "test.pdf"}]
    pipeline = _mock_pipeline(sources=sources)
    result = await chat(_req(), _http_req(pipeline=pipeline))
    assert len(result.sources) == 1
    assert result.sources[0].filename == "test.pdf"
