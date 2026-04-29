"""
Faz 6.2 — Chat Streaming Uçtan Uca Testleri

Strateji: chat_stream() fonksiyonu doğrudan çağrılır, StreamingResponse.body_iterator
async for ile iterate edilir, SSE satırları parse edilir, event sözleşmesi doğrulanır.

SSE Sözleşmesi:
    data: {"type": "token", "content": "..."}
    data: {"type": "sources", "documents": [...]}
    data: {"type": "done"}
    data: {"type": "error", "message": "..."}
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from app.api.routes.chat import chat, chat_stream
from app.services.chat_service import ChatRequest


# ── Yardımcı fonksiyonlar ─────────────────────────────────────────────────────

def _chat_request(
    question="Sözleşmenin fesih maddesi nedir?",
    session_id="sess-stream-001",
    doc_ids=None,
):
    return ChatRequest(
        question=question,
        session_id=session_id,
        document_ids=doc_ids or ["doc-test-001"],
    )


def _mock_request(pipeline=None):
    req = MagicMock()
    req.app.state.rag_pipeline = pipeline
    return req


async def _collect_sse_events(streaming_response) -> list[dict]:
    """StreamingResponse.body_iterator'ı iterate edip SSE event'leri parse eder."""
    events = []
    async for chunk in streaming_response.body_iterator:
        if isinstance(chunk, bytes):
            chunk = chunk.decode("utf-8")
        for line in chunk.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                if payload:
                    events.append(json.loads(payload))
    return events


def _make_token_gen(*tokens):
    """Belirtilen token'ları yield eden async generator factory'si döndürür."""
    async def _gen(*args, **kwargs):
        for token in tokens:
            yield token
    return _gen


# ── SSE Sözleşme Testleri ─────────────────────────────────────────────────────

class TestChatStreamSSEContract:
    """chat_stream() endpoint'inin SSE event formatını ve sırasını doğrular."""

    async def test_token_event_formatı_doğru(self, mock_pipeline):
        """Her token {type: token, content: str} formatında iletilmeli."""
        mock_pipeline.query_stream = _make_token_gen("Sözleşme", " 30", " gün.")
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        events = await _collect_sse_events(response)

        token_events = [e for e in events if e.get("type") == "token"]
        assert len(token_events) >= 1
        for evt in token_events:
            assert "content" in evt
            assert isinstance(evt["content"], str)

    async def test_done_event_son_gelir(self, mock_pipeline):
        """Son event her zaman {type: done} olmalı."""
        mock_pipeline.query_stream = _make_token_gen("merhaba")
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        events = await _collect_sse_events(response)

        assert events, "Hiç SSE event toplanamadı."
        assert events[-1]["type"] == "done"

    async def test_token_sirasi_korunur(self, mock_pipeline):
        """Token'lar generator'ın ürettiği sırayla iletilmeli."""
        tokens = ["Birinci", " ikinci", " üçüncü."]
        mock_pipeline.query_stream = _make_token_gen(*tokens)
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        events = await _collect_sse_events(response)

        token_events = [e for e in events if e.get("type") == "token"]
        contents = [e["content"] for e in token_events]
        assert contents == tokens

    async def test_bos_soru_400_firlatir(self):
        """Boş veya whitespace-only soru → 400 HTTPException yükselmeli."""
        with pytest.raises(HTTPException) as exc:
            await chat_stream(_chat_request(question="   "), _mock_request())
        assert exc.value.status_code == 400

    async def test_media_type_event_stream(self, mock_pipeline):
        """StreamingResponse media_type = 'text/event-stream' olmalı."""
        mock_pipeline.query_stream = _make_token_gen("tok")
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        assert response.media_type == "text/event-stream"

    async def test_cache_control_no_cache_header(self, mock_pipeline):
        """SSE response Cache-Control: no-cache header'ı içermeli."""
        mock_pipeline.query_stream = _make_token_gen("tok")
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        assert response.headers.get("Cache-Control") == "no-cache"

    async def test_pipeline_none_ise_error_event_gönderilir(self):
        """Pipeline None ise {type: error} event'i gönderilmeli, exception fırlatılmamalı."""
        req = _mock_request(pipeline=None)

        response = await chat_stream(_chat_request(), req)
        events = await _collect_sse_events(response)

        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1

    async def test_sources_dict_event_iletilir(self, mock_pipeline):
        """
        Generator __sources__ anahtarlı dict yield ederse,
        {type: sources, documents: [...]} event'i gönderilmeli.
        """
        async def _gen_with_sources(*args, **kwargs):
            yield "Cevap metni."
            yield {"__sources__": [{"filename": "test.pdf", "doc_id": "doc-001"}]}

        mock_pipeline.query_stream = _gen_with_sources
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        events = await _collect_sse_events(response)

        sources_events = [e for e in events if e.get("type") == "sources"]
        assert len(sources_events) == 1
        assert "documents" in sources_events[0]
        assert isinstance(sources_events[0]["documents"], list)

    async def test_exception_sirasinda_error_event_gönderilir(self, mock_pipeline):
        """Generator exception fırlatırsa SSE error event gönderilmeli, stream kapanmalı."""
        async def _crashing_gen(*args, **kwargs):
            yield "başlıyor"
            raise RuntimeError("LLM API 503 döndü")

        mock_pipeline.query_stream = _crashing_gen
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        events = await _collect_sse_events(response)

        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1
        assert "message" in error_events[0]

    async def test_timeout_error_event_gönderilir(self, mock_pipeline):
        """asyncio.TimeoutError → SSE error event, server çökmemeli."""
        async def _timeout_gen(*args, **kwargs):
            yield "hazırlanıyor"
            raise asyncio.TimeoutError("LLM yanıt vermedi")

        mock_pipeline.query_stream = _timeout_gen
        req = _mock_request(mock_pipeline)

        response = await chat_stream(_chat_request(), req)
        events = await _collect_sse_events(response)

        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1


# ── Chat (non-streaming) Endpoint Testleri ────────────────────────────────────

class TestChatNonStreaming:
    """chat() (non-streaming) endpoint'inin temel davranışını doğrular."""

    async def test_pipeline_sonucu_döndürür(self, mock_pipeline):
        """Pipeline query çağrısı yanıtı ChatResponse olarak dönmeli."""
        req = _mock_request(mock_pipeline)

        result = await chat(_chat_request(), req)

        assert result.question == "Sözleşmenin fesih maddesi nedir?"
        assert result.answer == "Sözleşme 30 gün bildirim gerektirir."

    async def test_pipeline_none_fallback_yanit(self):
        """Pipeline None ise fallback mesajlı ChatResponse dönmeli."""
        req = _mock_request(pipeline=None)

        result = await chat(_chat_request(), req)

        assert result is not None
        assert result.question == "Sözleşmenin fesih maddesi nedir?"

    async def test_bos_soru_400_firlatir(self):
        """Boş soru → 400 HTTPException."""
        with pytest.raises(HTTPException) as exc:
            await chat(_chat_request(question=""), _mock_request())
        assert exc.value.status_code == 400
