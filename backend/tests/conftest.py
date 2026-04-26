import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_cache():
    cache = AsyncMock()
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def sample_doc_id():
    return "doc-test-001"


# ── Faz 6 fixture'ları ────────────────────────────────────────────────────────

@pytest.fixture
def mock_pipeline():
    """Tüm async metodları AsyncMock olan sahte RAGPipeline."""
    pipeline = MagicMock()
    pipeline.ingest_document = AsyncMock(return_value={
        "doc_id": "doc-test-001",
        "parent_count": 3,
        "child_count": 9,
    })
    pipeline.query = AsyncMock(return_value=(
        "Sözleşme 30 gün bildirim gerektirir.",
        [{"filename": "test.pdf", "page_number": 1, "doc_id": "doc-test-001"}],
    ))

    async def _token_stream(*args, **kwargs):
        for token in ["Bu ", "bir ", "test ", "cevabıdır."]:
            yield token

    pipeline.query_stream = _token_stream
    return pipeline


@pytest.fixture
def mock_arq_job():
    """ARQ Job lifecycle'ını simüle eder: queued → in_progress → complete."""
    from arq.jobs import JobStatus

    job = MagicMock()
    job.job_id = "job-test-001"
    job.status = AsyncMock(return_value=JobStatus.queued)
    job.result_info = AsyncMock(return_value=None)
    job.result = AsyncMock(return_value={
        "doc_id": "doc-test-001",
        "parent_count": 3,
        "child_count": 9,
    })
    return job


@pytest.fixture
def mock_arq_redis():
    """enqueue_job() döndüren ARQ pool mock'u."""
    pool = AsyncMock()
    job = MagicMock()
    job.job_id = "job-enqueue-001"
    pool.enqueue_job = AsyncMock(return_value=job)
    return pool


@pytest.fixture
def worker_ctx(mock_pipeline):
    """ingest_document(ctx, ...) için {job_id, rag_pipeline, redis} dict'i."""
    return {
        "job_id": "job-ctx-001",
        "rag_pipeline": mock_pipeline,
        "redis": AsyncMock(),
    }


@pytest.fixture
def sample_pdf_bytes():
    """PyMuPDF'in parse edebileceği minimal geçerli PDF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
    )


@pytest.fixture
def corrupted_pdf_bytes():
    """PDF header'ına benzeyip parse edilemeyen bozuk içerik."""
    return b"%PDF-1.4\nGARBAGE INVALID CONTENT \x00\x01\x02\x03"
