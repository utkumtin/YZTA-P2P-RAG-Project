"""
Yeniden sıralama (Reranking) modülü testleri.

Test senaryoları:
1. Temel fonksiyonellik: Doğru dokümanları sıraya sokuyor mu?
2. Boş liste: Boş doküman listesi girildiğinde crash etmeden boş dönmeli.
3. Skorlama: Dönen dokümanlarda 'rerank_score' alanı var mı ve sıralı mı?
4. Limit: top_k parametresi doğru çalışıyor mu?
"""

import pytest

from app.core.reranker import Reranker


# Model yükleme maliyetli — tüm testler aynı instance'ı kullanır.
@pytest.fixture(scope="module")
def reranker() -> Reranker:
    return Reranker()


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Temel sıralama
# ─────────────────────────────────────────────────────────────────────────────


class TestRerankerFunctionality:
    """Reranker'ın doğru sıralama yaptığını doğrular."""

    def test_reranker_sorts_correctly(self, reranker):
        """Daha alakalı olan doküman en üstte (en yüksek skorla) olmalı."""
        query = "Python'da listeler nasıl sıralanır?"
        documents = [
            {"text": "Elmalar çok sağlıklıdır."},
            {"text": "Python'da sorted() fonksiyonu ile listeleri sıralayabilirsiniz."},
            {"text": "Hava bugün çok güzel olacak."}
        ]
        
        result = reranker.rerank(query, documents, top_k=3)
        
        assert len(result) == 3, "3 doküman girmeli 3 doküman dönmeli"
        assert "sorted() fonksiyonu" in result[0]["text"], "En alakalı doküman ilk sırada olmalı"

    def test_reranker_adds_score_field(self, reranker):
        """Her dokümana 'rerank_score' alanı eklenmeli ve skor float olmalı."""
        query = "test"
        documents = [{"text": "bu bir deneme metnidir"}]
        
        result = reranker.rerank(query, documents, top_k=1)
        
        assert len(result) == 1
        assert "rerank_score" in result[0]
        assert isinstance(result[0]["rerank_score"], float), "rerank_score float olmalı"

    def test_scores_are_sorted_descending(self, reranker):
        """Sonuçlar rerank_score'a göre büyükten küçüğe sıralı olmalı."""
        query = "Makine öğrenmesi"
        documents = [
            {"text": "Yapay zeka ve makine öğrenmesi algoritmaları gelişiyor."},
            {"text": "Akşam yemeğinde ne var?"},
            {"text": "Python veri bilimi için harika bir dildir."}
        ]
        
        result = reranker.rerank(query, documents, top_k=3)
        
        scores = [doc["rerank_score"] for doc in result]
        assert scores == sorted(scores, reverse=True), "Skorlar azalan sırada olmalı"


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Kenar durumlar
# ─────────────────────────────────────────────────────────────────────────────


class TestRerankerEdgeCases:
    """Reranker'ın kenar durumlarda (boş liste vs.) doğru çalıştığını doğrular."""

    def test_empty_documents_returns_empty_list(self, reranker):
        """Boş liste verilirse boş liste dönmeli, hata vermemeli."""
        query = "test"
        documents = []
        
        result = reranker.rerank(query, documents, top_k=5)
        
        assert result == [], "Boş liste boş dönmeli"

    def test_top_k_limits_results(self, reranker):
        """top_k parametresi dönen eleman sayısını sınırlamalı."""
        query = "test"
        documents = [
            {"text": "metin 1"},
            {"text": "metin 2"},
            {"text": "metin 3"}
        ]
        
        result = reranker.rerank(query, documents, top_k=2)
        
        assert len(result) == 2, "top_k=2 verildiğinde en fazla 2 eleman dönmeli"

    def test_single_document_handling(self, reranker):
        """Tek doküman verildiğinde crash etmemeli (float dönme sorunu çözülmüş mü)."""
        query = "tekli test"
        documents = [{"text": "sadece bir tane var"}]
        
        try:
            result = reranker.rerank(query, documents, top_k=1)
            assert len(result) == 1
            assert "rerank_score" in result[0]
        except Exception as e:
            pytest.fail(f"Tek doküman exception fırlattı: {e}")
