"""
Faz 6.1 — Worker Entegrasyon Testleri

Kapsam:
- ingest_document() worker fonksiyonunun pipeline ile doğru entegrasyonu
- ARQ job lifecycle → API status eşleşme sözleşmesi
- startup() fonksiyonunun ctx'i doğru doldurduğu
"""

import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ağır ML/DB bağımlılıkları tests/integration/conftest.py'de stub'lanmıştır.
from app.workers.ingestion_worker import ingest_document, startup
from app.core.document_processor import DocumentProcessingError


class TestIngestDocumentWorkerFunction:
    """ingest_document() ARQ worker fonksiyonunun izolasyon testleri."""

    async def test_pipeline_dogru_argümanlarla_cagrilir(self, worker_ctx, sample_doc_id):
        """ingest_document(), pipeline.ingest_document()'i file_path ve doc_id ile çağırmalı."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test")
            tmp_path = f.name
        try:
            await ingest_document(worker_ctx, sample_doc_id, tmp_path)
            worker_ctx["rag_pipeline"].ingest_document.assert_awaited_once_with(
                file_path=tmp_path,
                doc_id=sample_doc_id,
                session_id="default",
            )
        finally:
            os.unlink(tmp_path)

    async def test_pipeline_sonucu_döndürülür(self, worker_ctx, sample_doc_id):
        """ingest_document(), pipeline'dan gelen sonucu geri döndürmeli."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test")
            tmp_path = f.name
        try:
            result = await ingest_document(worker_ctx, sample_doc_id, tmp_path)
            assert result["doc_id"] == sample_doc_id
            assert result["parent_count"] == 3
            assert result["child_count"] == 9
        finally:
            os.unlink(tmp_path)

    async def test_dosya_yoksa_filenotfounderror_firlatilir(self, worker_ctx):
        """Var olmayan dosya yolu verildiğinde FileNotFoundError yükselmeli."""
        with pytest.raises(FileNotFoundError):
            await ingest_document(worker_ctx, "doc-missing", "/nonexistent/path/file.pdf")

    async def test_pipeline_exception_re_raise_edilir(self, worker_ctx):
        """Pipeline hata fırlatırsa worker re-raise etmeli; ARQ job'ı failed olarak işaretler."""
        worker_ctx["rag_pipeline"].ingest_document = AsyncMock(
            side_effect=DocumentProcessingError("bozuk PDF")
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"bad content")
            tmp_path = f.name
        try:
            with pytest.raises(DocumentProcessingError):
                await ingest_document(worker_ctx, "doc-bad", tmp_path)
        finally:
            os.unlink(tmp_path)

    async def test_basari_durumunda_info_log_atilir(self, worker_ctx, caplog):
        """Başarılı ingest sonrası document_id içeren INFO log olmalı."""
        import logging

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test")
            tmp_path = f.name
        try:
            with caplog.at_level(logging.INFO, logger="app.workers.ingestion_worker"):
                await ingest_document(worker_ctx, "doc-log-001", tmp_path)
            assert "doc-log-001" in caplog.text
        finally:
            os.unlink(tmp_path)

    async def test_hata_durumunda_exception_log_atilir(self, worker_ctx, caplog):
        """Pipeline hatası sonrası document_id içeren hata logu olmalı."""
        import logging

        worker_ctx["rag_pipeline"].ingest_document = AsyncMock(
            side_effect=RuntimeError("LLM patladı")
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            with caplog.at_level(logging.ERROR, logger="app.workers.ingestion_worker"):
                with pytest.raises(RuntimeError):
                    await ingest_document(worker_ctx, "doc-fail", tmp_path)
            assert "doc-fail" in caplog.text
        finally:
            os.unlink(tmp_path)

    async def test_progress_redis_e_yazilir(self, worker_ctx, sample_doc_id):
        """İngest sırasında Redis'e progress kaydı yapılmalı."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"%PDF-1.4 test")
            tmp_path = f.name
        try:
            await ingest_document(worker_ctx, sample_doc_id, tmp_path)
            assert worker_ctx["redis"].set.await_count >= 1
        finally:
            os.unlink(tmp_path)

    async def test_hata_durumunda_error_progress_yazilir(self, worker_ctx):
        """Pipeline hatası durumunda Redis'e 'error' event'li progress yazılmalı."""
        import json

        worker_ctx["rag_pipeline"].ingest_document = AsyncMock(
            side_effect=RuntimeError("hata")
        )
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            tmp_path = f.name
        try:
            with pytest.raises(RuntimeError):
                await ingest_document(worker_ctx, "doc-err-progress", tmp_path)

            written_calls = worker_ctx["redis"].set.call_args_list
            last_data = json.loads(written_calls[-1].args[1])
            assert last_data["event"] == "error"
        finally:
            os.unlink(tmp_path)


class TestArqJobLifecycle:
    """
    ARQ JobStatus değerlerinin API status sözleşmesiyle eşleşmesini doğrular.

    ARQ'da 'failed' enum yoktur: başarısız job → complete + success=False.
    Task status endpoint bu eşleştirmeyi yapmalı.
    """

    async def test_queued_status(self, mock_arq_job):
        """Kuyruğa alınmış job → queued durumu döner."""
        from arq.jobs import JobStatus

        mock_arq_job.status = AsyncMock(return_value=JobStatus.queued)
        status = await mock_arq_job.status()
        assert status == JobStatus.queued

    async def test_in_progress_status(self, mock_arq_job):
        """Çalışan job → in_progress durumu döner."""
        from arq.jobs import JobStatus

        mock_arq_job.status = AsyncMock(return_value=JobStatus.in_progress)
        status = await mock_arq_job.status()
        assert status == JobStatus.in_progress

    async def test_complete_success(self, mock_arq_job):
        """Başarıyla tamamlanan job → complete + success=True."""
        from arq.jobs import JobStatus, JobResult

        mock_arq_job.status = AsyncMock(return_value=JobStatus.complete)
        result_info = MagicMock(spec=JobResult)
        result_info.success = True
        result_info.result = {"doc_id": "doc-001", "parent_count": 3, "child_count": 9}
        mock_arq_job.result_info = AsyncMock(return_value=result_info)

        status = await mock_arq_job.status()
        info = await mock_arq_job.result_info()
        assert status == JobStatus.complete
        assert info.success is True

    async def test_complete_with_failure(self, mock_arq_job):
        """Hata fırlatan job → complete + success=False (API'de 'failed' olarak gösterilmeli)."""
        from arq.jobs import JobStatus, JobResult

        mock_arq_job.status = AsyncMock(return_value=JobStatus.complete)
        result_info = MagicMock(spec=JobResult)
        result_info.success = False
        result_info.result = RuntimeError("PDF bozuk")
        mock_arq_job.result_info = AsyncMock(return_value=result_info)

        status = await mock_arq_job.status()
        info = await mock_arq_job.result_info()
        assert status == JobStatus.complete
        assert info.success is False

    async def test_not_found_status(self, mock_arq_job):
        """Bilinmeyen job_id → not_found durumu döner."""
        from arq.jobs import JobStatus

        mock_arq_job.status = AsyncMock(return_value=JobStatus.not_found)
        status = await mock_arq_job.status()
        assert status == JobStatus.not_found


class TestWorkerStartupContext:
    """startup() fonksiyonunun ctx'i doğru şekilde doldurduğunu doğrular."""

    async def test_startup_redis_ping_yapar(self):
        """startup() Redis bağlantısını test etmek için ping() çağırmalı."""
        ctx = {"redis": AsyncMock()}

        with (
            patch("app.workers.ingestion_worker.get_embedder", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.VectorStore") as mock_vs_cls,
            patch("app.workers.ingestion_worker.Reranker", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.create_llm_client", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.RAGPipeline", return_value=MagicMock()),
        ):
            mock_vs_cls.return_value.setup = MagicMock()
            await startup(ctx)

        ctx["redis"].ping.assert_awaited_once()

    async def test_startup_rag_pipeline_set_eder(self):
        """startup() sonrası ctx['rag_pipeline'] bir RAGPipeline instance'ı olmalı."""
        ctx = {"redis": AsyncMock()}
        fake_pipeline = MagicMock()

        with (
            patch("app.workers.ingestion_worker.get_embedder", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.VectorStore") as mock_vs_cls,
            patch("app.workers.ingestion_worker.Reranker", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.create_llm_client", return_value=MagicMock()),
            patch("app.workers.ingestion_worker.RAGPipeline", return_value=fake_pipeline),
        ):
            mock_vs_cls.return_value.setup = MagicMock()
            await startup(ctx)

        assert ctx["rag_pipeline"] is fake_pipeline
