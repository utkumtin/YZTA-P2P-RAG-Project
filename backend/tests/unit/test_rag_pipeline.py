"""
RAGPipeline.summarize() unit testleri.

Testler gerçek LLM, Qdrant veya Redis bağlantısı gerektirmez — tüm
harici bağımlılıklar mock'lanmıştır.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.rag_pipeline import RAGPipeline


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


def _make_parent(text: str, filename: str = "test.pdf", doc_id: str = "doc-1") -> dict:
    return {
        "chunk_id": f"parent-{doc_id}-0",
        "text": text,
        "metadata": {
            "doc_id": doc_id,
            "filename": filename,
            "session_id": "sess-1",
            "page_number": 1,
        },
    }


@pytest.fixture
def llm_client():
    mock = MagicMock()
    mock.generate = AsyncMock(return_value="özet metni")
    mock.stream = AsyncMock()
    return mock


@pytest.fixture
def vector_store():
    mock = MagicMock()
    mock.get_parents_by_doc_id.return_value = []
    return mock


@pytest.fixture
def pipeline(llm_client, vector_store):
    embedder = MagicMock()
    reranker = MagicMock()
    return RAGPipeline(
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        llm_client=llm_client,
        cache=None,
    )


# ---------------------------------------------------------------------------
# summarize() testleri
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_empty_returns_not_found_message(pipeline, vector_store):
    """Hiç parent chunk bulunamazsa anlamlı bir mesaj dönmeli."""
    vector_store.get_parents_by_doc_id.return_value = []

    summary, sources = await pipeline.summarize(["doc-1"], "sess-1")

    assert "bulunamadı" in summary
    assert sources == []


@pytest.mark.asyncio
async def test_summarize_single_chunk_skips_reduce(pipeline, vector_store, llm_client):
    """Tek parent chunk için Reduce aşaması atlanmalı — LLM yalnızca bir kez çağrılmalı."""
    parent = _make_parent("Tek bir paragraf.")
    vector_store.get_parents_by_doc_id.return_value = [parent]
    llm_client.generate.return_value = "tek paragraf özeti"

    summary, sources = await pipeline.summarize(["doc-1"], "sess-1")

    # Yalnızca Map adımı için bir generate() çağrısı
    assert llm_client.generate.await_count == 1
    assert summary == "tek paragraf özeti"
    assert len(sources) == 1
    assert sources[0]["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_summarize_multiple_chunks_runs_map_reduce(pipeline, vector_store, llm_client):
    """Birden fazla chunk olduğunda Map + Reduce çalışmalı."""
    parents = [
        _make_parent("Birinci bölüm.", filename="doc.pdf"),
        _make_parent("İkinci bölüm.", filename="doc.pdf"),
    ]
    vector_store.get_parents_by_doc_id.return_value = parents

    # Map için 2 çağrı + Reduce için 1 çağrı = 3 toplam
    llm_client.generate.side_effect = ["mini-özet 1", "mini-özet 2", "nihai özet"]

    summary, sources = await pipeline.summarize(["doc-1"], "sess-1")

    assert llm_client.generate.await_count == 3
    assert summary == "nihai özet"


@pytest.mark.asyncio
async def test_summarize_reduce_prompt_contains_mini_summaries(
    pipeline, vector_store, llm_client
):
    """Reduce adımında üretilen prompt, mini-özetlerin tamamını içermeli."""
    parents = [
        _make_parent("A bölümü."),
        _make_parent("B bölümü."),
    ]
    vector_store.get_parents_by_doc_id.return_value = parents

    calls = []

    async def _capture_generate(prompt, system_prompt):
        calls.append(prompt)
        return f"özet-{len(calls)}"

    llm_client.generate = _capture_generate

    await pipeline.summarize(["doc-1"], "sess-1")

    # İlk iki çağrı Map, üçüncüsü Reduce
    reduce_prompt = calls[2]
    assert "özet-1" in reduce_prompt
    assert "özet-2" in reduce_prompt


@pytest.mark.asyncio
async def test_summarize_multiple_doc_ids_aggregates_parents(
    pipeline, vector_store, llm_client
):
    """Birden fazla doc_id verildiğinde tüm dokümanların parent'ları birleştirilmeli."""
    vector_store.get_parents_by_doc_id.side_effect = [
        [_make_parent("Doc A içeriği.", doc_id="doc-a")],
        [_make_parent("Doc B içeriği.", doc_id="doc-b")],
    ]
    # 2 Map + 1 Reduce
    llm_client.generate.side_effect = ["a özeti", "b özeti", "nihai özet"]

    summary, sources = await pipeline.summarize(["doc-a", "doc-b"], "sess-1")

    # Her iki doküman için get_parents_by_doc_id çağrılmalı
    assert vector_store.get_parents_by_doc_id.call_count == 2
    assert summary == "nihai özet"


@pytest.mark.asyncio
async def test_summarize_sources_capped_at_five(pipeline, vector_store, llm_client):
    """6+ parent chunk olduğunda kaynak listesi en fazla 5 elemanlı olmalı."""
    parents = [_make_parent(f"Paragraf {i}.", filename=f"f{i}.pdf") for i in range(7)]
    vector_store.get_parents_by_doc_id.return_value = parents

    # 7 Map çağrısı + 1 Reduce
    llm_client.generate.side_effect = [f"mini-{i}" for i in range(7)] + ["nihai"]

    _, sources = await pipeline.summarize(["doc-1"], "sess-1")

    assert len(sources) == 5


@pytest.mark.asyncio
async def test_summarize_source_format(pipeline, vector_store, llm_client):
    """Dönen kaynak listesi beklenen alanları içermeli."""
    parent = _make_parent("İçerik.", filename="rapor.pdf", doc_id="abc-123")
    parent["metadata"]["page_number"] = 3
    vector_store.get_parents_by_doc_id.return_value = [parent]
    llm_client.generate.return_value = "özet"

    _, sources = await pipeline.summarize(["abc-123"], "sess-1")

    assert sources[0] == {
        "filename": "rapor.pdf",
        "page_number": 3,
        "doc_id": "abc-123",
    }
