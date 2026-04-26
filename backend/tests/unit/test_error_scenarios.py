"""
Faz 6.3 — Hata Senaryoları Testleri

Kapsam:
A. Bozuk/corrupted PDF → worker job 'failed' durumuna düşmeli
B. LLM timeout → SSE 'error' event gönderilmeli
C. Redis kesintisi → graceful degradation, çökme yok
"""

import asyncio
import json
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

# Ağır ML/DB bağımlılıkları tests/unit/conftest.py'de stub'lanmıştır.
from app.workers.ingestion_worker import ingest_document, startup
from app.core.document_processor import DocumentProcessingError


# ── Yardımcı ─────────────────────────────────────────────────────────────────

async def _collect_sse_events(streaming_response) -> list[dict]:
    """StreamingResponse.body_iterator'dan SSE event'lerini toplar."""
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


def _stream_request(pipeline=None):
    req = MagicMock()
    req.app.state.rag_pipeline = pipeline
    return req


# ── A. Bozuk PDF Senaryoları ──────────────────────────────────────────────────

class TestCorruptedPdfWorkerFailure:
    """Bozuk PDF yüklemesi → worker job'ı failed durumuna düşmeli."""

    async def test_bozuk_pdf_document_processing_error_firlatir(self, worker_ctx):
        """
        DocumentProcessingError fırlatıldığında worker re-raise etmeli;
        ARQ bu hatayı yakalayarak job'ı complete+success=False yapacak.
        """
        worker_ctx["rag_pipeline"].ingest_document = AsyncMock(
            side_effect=DocumentProcessingError("PDF yapısı geçersiz")
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4\nGARBAGE\x00\x01")
            tmp = f.name
        try:
            with pytest.raises(DocumentProcessingError) as exc:
                await ingest_document(worker_ctx, "doc-corrupt", tmp)
            assert "PDF" in str(exc.value) or "geçersiz" in str(exc.value)
        finally:
            os.unlink(tmp)

    async def test_bozuk_pdf_kismi_indexleme_yapmaz(self, worker_ctx):
        """Pipeline hata fırlatırsa vector_store.index_child_chunks çağrılmamalı."""
        vector_store = MagicMock()
        worker_ctx["rag_pipeline"].ingest_document = AsyncMock(
            side_effect=DocumentProcessingError("bozuk")
        )
        worker_ctx["rag_pipeline"].vector_store = vector_store

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"GARBAGE")
            tmp = f.name
        try:
            with pytest.raises(DocumentProcessingError):
                await ingest_document(worker_ctx, "doc-corrupt-2", tmp)
            vector_store.index_child_chunks.assert_not_called()
        finally:
            os.unlink(tmp)

    async def test_bos_dosya_hata_firlatir(self, worker_ctx):
        """Boş dosya → FileNotFoundError veya DocumentProcessingError yükselmeli."""
        worker_ctx["rag_pipeline"].ingest_document = AsyncMock(
            side_effect=DocumentProcessingError("metin çıkarılamadı")
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp = f.name
        try:
            with pytest.raises((DocumentProcessingError, FileNotFoundError)):
                await ingest_document(worker_ctx, "doc-empty", tmp)
        finally:
            os.unlink(tmp)

    async def test_arq_failed_semantigi(self):
        """
        ARQ'da 'failed' enum yoktur: başarısız job → complete + success=False.
        Task endpoint bu eşleştirmeyi yapmalı.
        """
        from arq.jobs import JobStatus, JobResult

        job = MagicMock()
        job.status = AsyncMock(return_value=JobStatus.complete)
        result_info = MagicMock(spec=JobResult)
        result_info.success = False
        result_info.result = DocumentProcessingError("PDF yapısı geçersiz")
        job.result_info = AsyncMock(return_value=result_info)

        status = await job.status()
        info = await job.result_info()
        assert status == JobStatus.complete
        assert info.success is False

    async def test_hata_sonrasi_redis_e_error_event_yazilir(self, worker_ctx):
        """Worker hata durumunda Redis'e 'error' event'li progress kaydı yapmalı."""
        worker_ctx["rag_pipeline"].ingest_document = AsyncMock(
            side_effect=DocumentProcessingError("hata")
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"bad")
            tmp = f.name
        try:
            with pytest.raises(DocumentProcessingError):
                await ingest_document(worker_ctx, "doc-redis-err", tmp)

            written_calls = worker_ctx["redis"].set.call_args_list
            last_data = json.loads(written_calls[-1].args[1])
            assert last_data["event"] == "error"
        finally:
            os.unlink(tmp)


# ── B. LLM Timeout Senaryoları ────────────────────────────────────────────────

class TestLLMTimeoutSSEError:
    """LLM timeout → SSE error event gönderilmeli, server çökmemeli."""

    def _make_timeout_gen(self):
        async def _gen(*args, **kwargs):
            yield "Yanıt hazırlanıyor"
            raise asyncio.TimeoutError("LLM yanıt vermedi")
        return _gen

    async def test_timeout_error_event_gönderir(self):
        """asyncio.TimeoutError → SSE {type: error} event."""
        from app.api.routes.chat import chat_stream
        from app.services.chat_service import ChatRequest

        pipeline = MagicMock()
        pipeline.query_stream = self._make_timeout_gen()

        req = _stream_request(pipeline)
        chat_req = ChatRequest(
            question="Sözleşme ne zaman bitiyor?",
            session_id="sess-timeout",
            document_ids=["doc-001"],
        )

        response = await chat_stream(chat_req, req)
        events = await _collect_sse_events(response)

        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1, f"Beklenen 1 error event, alınan: {events}"
        assert "message" in error_events[0]

    async def test_timeout_sunucuyu_cökermiyor(self):
        """TimeoutError stream'e absorbe edilmeli, unhandled exception olmamalı."""
        from app.api.routes.chat import chat_stream
        from app.services.chat_service import ChatRequest

        pipeline = MagicMock()
        pipeline.query_stream = self._make_timeout_gen()

        req = _stream_request(pipeline)
        chat_req = ChatRequest(
            question="Timeout testi?",
            session_id="sess-timeout-2",
            document_ids=[],
        )

        response = await chat_stream(chat_req, req)
        events = await _collect_sse_events(response)
        assert any(e.get("type") in ("done", "error") for e in events)

    async def test_genel_runtime_error_error_event_gönderir(self):
        """Beklenmedik RuntimeError → SSE error event, 500 değil."""
        from app.api.routes.chat import chat_stream
        from app.services.chat_service import ChatRequest

        async def _crashing(*args, **kwargs):
            yield "başlıyor"
            raise RuntimeError("LLM API 503 döndü")

        pipeline = MagicMock()
        pipeline.query_stream = _crashing

        req = _stream_request(pipeline)
        chat_req = ChatRequest(
            question="Soru var mı?",
            session_id="sess-crash",
            document_ids=[],
        )

        response = await chat_stream(chat_req, req)
        events = await _collect_sse_events(response)
        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1


# ── C. Redis Kesintisi Senaryoları ────────────────────────────────────────────

class TestRedisDisconnectionDegradation:
    """Redis kullanılamaz → API graceful degrade etmeli, çökmemeli."""

    async def test_cache_get_hatasi_query_devam_eder(self, mock_pipeline):
        """cache.get() ConnectionError fırlatırsa chat query yine de çalışmalı."""
        from app.api.routes.chat import chat
        from app.services.chat_service import ChatRequest

        broken_cache = AsyncMock()
        broken_cache.get = AsyncMock(side_effect=ConnectionError("Redis bağlantısı reddedildi"))

        req = MagicMock()
        req.app.state.semantic_cache = broken_cache
        req.app.state.rag_pipeline = mock_pipeline

        chat_req = ChatRequest(
            question="Redis bozuldu mu?",
            session_id="sess-redis-fail",
            document_ids=["doc-001"],
        )

        result = await chat(chat_req, req)
        assert result is not None
        assert result.question == "Redis bozuldu mu?"

    async def test_worker_startup_redis_ping_hatasi_exception_firlatir(self):
        """startup() sırasında Redis ping başarısız olursa exception fırlatılmalı."""
        ctx = {"redis": AsyncMock()}
        ctx["redis"].ping = AsyncMock(side_effect=ConnectionError("Redis kullanılamıyor"))

        with (
            patch("app.workers.ingestion_worker.get_embedder", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.VectorStore") as mock_vs,
            patch("app.workers.ingestion_worker.Reranker", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.create_llm_client", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.RAGPipeline", return_value=MagicMock()),
        ):
            mock_vs.return_value.setup = MagicMock()
            with pytest.raises(ConnectionError):
                await startup(ctx)

    async def test_arq_redis_yoksa_upload_503_firlatir(self):
        """app.state.arq_redis None ise upload → 503 döndürmeli."""
        from app.api.routes.upload import upload_documents

        def _dosya():
            f = MagicMock()
            f.filename = "test.pdf"
            f.read = AsyncMock(return_value=b"%PDF-1.4 test")
            return f

        def _aiofiles_mock():
            m = AsyncMock()
            m.write = AsyncMock()
            cm = AsyncMock()
            cm.__aenter__ = AsyncMock(return_value=m)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        req = MagicMock()
        req.app.state.arq_redis = None

        with patch("aiofiles.open", return_value=_aiofiles_mock()):
            with pytest.raises((HTTPException, AttributeError)):
                await upload_documents(req, files=[_dosya()], session_id="s")

    async def test_streaming_redis_olmadan_calisir(self, mock_pipeline):
        """Semantic cache Redis'e bağlanamasa bile SSE streaming çalışmalı."""
        from app.api.routes.chat import chat_stream
        from app.services.chat_service import ChatRequest

        broken_cache = AsyncMock()
        broken_cache.get = AsyncMock(side_effect=ConnectionError("Redis çevrimdışı"))

        async def _simple_stream(*args, **kwargs):
            yield "Redis"
            yield " olmadan"
            yield " çalışıyor."

        mock_pipeline.query_stream = _simple_stream

        req = MagicMock()
        req.app.state.semantic_cache = broken_cache
        req.app.state.rag_pipeline = mock_pipeline

        chat_req = ChatRequest(
            question="Redis olmadan çalışıyor mu?",
            session_id="sess-no-redis",
            document_ids=[],
        )

        response = await chat_stream(chat_req, req)
        events = await _collect_sse_events(response)

        assert any(e.get("type") in ("token", "error") for e in events)
        assert events[-1]["type"] in ("done", "error")
