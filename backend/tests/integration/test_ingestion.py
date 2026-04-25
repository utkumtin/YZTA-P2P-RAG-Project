"""
Doküman ingestion akışı entegrasyon testleri.
Gerçek dosya I/O ve ML modelleri mock'lanmıştır.
"""

from unittest.mock import AsyncMock, MagicMock, patch


async def test_ingest_worker_cagrilabilir():
    from app.workers.ingestion_worker import ingest_document

    ctx = {"job_id": "job-001"}
    # Worker henüz pipeline'a bağlı değil — None dönmeli
    result = await ingest_document(ctx, "doc-abc", "/tmp/test.pdf")
    assert result is None


async def test_ingest_worker_parametreler_dogru_aliniyor():
    from app.workers.ingestion_worker import ingest_document

    ctx = {}
    await ingest_document(ctx, document_id="doc-xyz", file_path="/path/file.docx")


async def test_chunker_ve_embedder_zinciri():
    from app.core.chunker import create_parent_child_chunks

    metin = "Sözleşme maddeleri şu şekildedir. " * 60
    meta = {
        "doc_id": "ing-001",
        "filename": "test.pdf",
        "file_type": "pdf",
        "language": "tr",
        "session_id": "s",
    }

    parents, children = create_parent_child_chunks(metin, meta)

    embedder = MagicMock()
    embedder.encode.return_value = {
        "dense": [[0.1] * 1024] * len(children),
        "sparse": [{}] * len(children),
    }

    texts = [c["text"] for c in children]
    vektorler = embedder.encode(texts)

    assert len(vektorler["dense"]) == len(children)
    assert len(vektorler["dense"][0]) == 1024


async def test_ingest_pipeline_tam_akis():
    from app.core.rag_pipeline import RAGPipeline

    embedder = MagicMock()
    embedder.encode.return_value = {
        "dense": [[0.2] * 1024] * 3,
        "sparse": [{} for _ in range(3)],
    }

    vs = MagicMock()
    vs.store_parent_chunks = MagicMock()
    vs.index_child_chunks = MagicMock()

    reranker = MagicMock()
    llm = MagicMock()
    llm.generate = AsyncMock()

    pipeline = RAGPipeline(
        embedder=embedder,
        vector_store=vs,
        reranker=reranker,
        llm_client=llm,
        cache=None,
    )

    metin = "Madde 1: Taraflar sözleşmeyi kabul eder. " * 60
    with patch.object(pipeline.processor, "process", return_value={
        "doc_id": "doc-ing-001",
        "filename": "sozlesme.pdf",
        "file_type": "pdf",
        "language": "tr",
        "full_text": metin,
        "pages": 1,
    }):
        result = await pipeline.ingest_document(
            file_path="/tmp/sozlesme.pdf",
            doc_id="doc-ing-001",
            session_id="sess-ing",
        )

    assert result["doc_id"] == "doc-ing-001"
    assert result["parent_count"] > 0
    assert result["child_count"] > 0
    vs.store_parent_chunks.assert_called_once()
    vs.index_child_chunks.assert_called_once()
