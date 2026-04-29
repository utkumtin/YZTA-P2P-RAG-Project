"""
Yeniden sıralama (Reranking) modülü unit testleri.

FlagReranker gerçek bir model indirip yükler ve mevcut transformers
sürümüyle tokenizer uyumsuzluğu yaşanabileceğinden, compute_score()
burada mock'lanmıştır. Böylece testler:
  - Hızlı çalışır (model yükleme yok)
  - CI/CD ortamında GPU / kütüphane bağımlılığı gerektirmez
  - Sadece Reranker sınıfının kendi mantığını (sıralama, float normalize,
    top_k kesme, tek-eleman guard) doğrular
"""

import pytest
from unittest.mock import MagicMock, patch

from app.core.reranker import Reranker


# ---------------------------------------------------------------------------
# Fixture: FlagReranker'ı mock'la, gerçek modeli yükleme.
# ---------------------------------------------------------------------------

@pytest.fixture
def reranker():
    with patch("app.core.reranker.FlagReranker") as MockFlagReranker:
        mock_model = MagicMock()
        MockFlagReranker.return_value = mock_model
        r = Reranker()
        # Testten önce compute_score dönüş değeri ayarlanabilsin diye
        # mock_model'i reranker üzerinden erişilebilir bırakıyoruz.
        r._mock_model = mock_model
        yield r


# ---------------------------------------------------------------------------
# TestRerankerFunctionality
# ---------------------------------------------------------------------------


class TestRerankerFunctionality:
    """Reranker'ın doğru sıralama yaptığını doğrular."""

    def test_reranker_sorts_correctly(self, reranker):
        """Daha alakalı olan doküman en üstte (en yüksek skorla) olmalı."""
        query = "Python'da listeler nasıl sıralanır?"
        documents = [
            {"text": "Elmalar çok sağlıklıdır."},
            {"text": "Python'da sorted() fonksiyonu ile listeleri sıralayabilirsiniz."},
            {"text": "Hava bugün çok güzel olacak."},
        ]
        # İkinci doküman en yüksek skoru alıyor (alakalı olan)
        reranker._mock_model.compute_score.return_value = [-5.0, 3.0, -4.0]

        result = reranker.rerank(query, documents, top_k=3)

        assert len(result) == 3, "3 doküman girmeli 3 doküman dönmeli"
        assert "sorted() fonksiyonu" in result[0]["text"], \
            "En alakalı doküman ilk sırada olmalı"

    def test_reranker_adds_score_field(self, reranker):
        """Her dokümana 'rerank_score' alanı eklenmeli ve skor float olmalı."""
        reranker._mock_model.compute_score.return_value = [1.23]

        result = reranker.rerank("test", [{"text": "bu bir deneme metnidir"}], top_k=1)

        assert len(result) == 1
        assert "rerank_score" in result[0]
        assert isinstance(result[0]["rerank_score"], float), "rerank_score float olmalı"

    def test_scores_are_sorted_descending(self, reranker):
        """Sonuçlar rerank_score'a göre büyükten küçüğe sıralı olmalı."""
        reranker._mock_model.compute_score.return_value = [2.0, -1.0, 0.5]

        result = reranker.rerank(
            "Makine öğrenmesi",
            [
                {"text": "Yapay zeka ve makine öğrenmesi algoritmaları gelişiyor."},
                {"text": "Akşam yemeğinde ne var?"},
                {"text": "Python veri bilimi için harika bir dildir."},
            ],
            top_k=3,
        )

        scores = [doc["rerank_score"] for doc in result]
        assert scores == sorted(scores, reverse=True), "Skorlar azalan sırada olmalı"


# ---------------------------------------------------------------------------
# TestRerankerEdgeCases
# ---------------------------------------------------------------------------


class TestRerankerEdgeCases:
    """Reranker'ın kenar durumlarda doğru çalıştığını doğrular."""

    def test_empty_documents_returns_empty_list(self, reranker):
        """Boş liste verilirse boş liste dönmeli, hata vermemeli."""
        result = reranker.rerank("test", [], top_k=5)
        assert result == [], "Boş liste boş dönmeli"

    def test_top_k_limits_results(self, reranker):
        """top_k parametresi dönen eleman sayısını sınırlamalı."""
        reranker._mock_model.compute_score.return_value = [1.0, 2.0, 3.0]

        result = reranker.rerank(
            "test",
            [{"text": "metin 1"}, {"text": "metin 2"}, {"text": "metin 3"}],
            top_k=2,
        )

        assert len(result) == 2, "top_k=2 verildiğinde en fazla 2 eleman dönmeli"

    def test_single_document_handling(self, reranker):
        """Tek doküman verildiğinde crash etmemeli (float dönme sorunu çözülmüş mü)."""
        # FlagReranker gerçekte tek elemanda float döner — bu guard'ı test ediyoruz.
        reranker._mock_model.compute_score.return_value = 0.85  # float, liste değil

        try:
            result = reranker.rerank("tekli test", [{"text": "sadece bir tane var"}], top_k=1)
            assert len(result) == 1
            assert "rerank_score" in result[0]
            assert result[0]["rerank_score"] == pytest.approx(0.85)
        except Exception as e:
            pytest.fail(f"Tek doküman exception fırlattı: {e}")
