"""
RAG pipeline uçtan uca entegrasyon testleri.
Tüm dış bağımlılıklar (Qdrant, Redis, LLM, embedder) mock'lanmıştır.
"""

from unittest.mock import AsyncMock, MagicMock

from app.core.rag_pipeline import RAGPipeline


def _pipeline_kur(llm_yanit="cevap metni"):
    embedder = MagicMock()
    embedder.encode_query.return_value = {
        "dense": [[0.1] * 1024],
        "sparse": [{}],
    }

    vs = MagicMock()
    vs.hybrid_search.return_value = [
        {
            "text": "Sözleşme 30 gün bildirim gerektirir.",
            "metadata": {
                "doc_id": "d1",
                "filename": "sozlesme.pdf",
                "parent_chunk_id": "parent-d1-0001",
            },
        }
    ]
    vs.get_parent_by_id.return_value = {
        "text": "Tam sözleşme metni burada. Fesih durumunda 30 gün önceden haber verilmesi gerekir.",
        "metadata": {"doc_id": "d1", "filename": "sozlesme.pdf", "page_number": 2},
    }
    vs.get_parents_by_doc_id.return_value = []

    reranker = MagicMock()
    reranker.rerank.return_value = [
        {
            "text": "Sözleşme 30 gün bildirim gerektirir.",
            "metadata": {
                "doc_id": "d1",
                "filename": "sozlesme.pdf",
                "parent_chunk_id": "parent-d1-0001",
            },
            "score": 0.9,
        }
    ]

    llm = MagicMock()
    llm.generate = AsyncMock(return_value=llm_yanit)

    return RAGPipeline(
        embedder=embedder,
        vector_store=vs,
        reranker=reranker,
        llm_client=llm,
        cache=None,
    )


async def test_query_cevap_dondurur():
    pipeline = _pipeline_kur("30 gün bildirim süresi geçerlidir.")
    cevap, _ = await pipeline.query("Fesih süresi ne kadar?", "sess-test", ["d1"])
    assert len(cevap) > 0


async def test_query_kaynak_listesi_dolu():
    pipeline = _pipeline_kur()
    _, kaynaklar = await pipeline.query("Soru?", "sess-test", ["d1"])
    assert isinstance(kaynaklar, list)
    assert len(kaynaklar) > 0
    assert "filename" in kaynaklar[0]
    assert "doc_id" in kaynaklar[0]


async def test_query_hic_chunk_bulunamaz():
    pipeline = _pipeline_kur()
    pipeline.vector_store.hybrid_search.return_value = []
    pipeline.reranker.rerank.return_value = []
    cevap, kaynaklar = await pipeline.query("Bilinmeyen soru?", "sess-test", [])
    assert kaynaklar == []
    assert len(cevap) > 0


async def test_query_llm_bir_kez_cagrilir():
    pipeline = _pipeline_kur("test cevabı")
    await pipeline.query("Soru?", "sess-test", ["d1"])
    pipeline.llm_client.generate.assert_awaited_once()


async def test_query_cache_hit_llm_atlanir():
    pipeline = _pipeline_kur()
    pipeline.cache = AsyncMock()
    pipeline.cache.get = AsyncMock(
        return_value={"answer": "önbellekten", "sources": []}
    )

    cevap, kaynaklar = await pipeline.query("Önbellekli soru?", "sess-test")
    assert cevap == "önbellekten"
    pipeline.llm_client.generate.assert_not_awaited()
