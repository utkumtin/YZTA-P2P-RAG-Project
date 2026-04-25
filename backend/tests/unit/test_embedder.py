"""
Embedding üretimi testleri

Test senaryoları:
1. Temel fonksiyonellik: dense + sparse vektörler üretildi mi?
2. Vektör boyutu: dense 1024 boyutlu mu?
3. Boş liste: crash etmeden boş dönmeli
4. encode_query: single-item kısayolu doğru çalışıyor mu?
5. Anlamsal benzerlik: ilişkili metinler ilişkisizlerden daha yakın mı?
6. Sparse vektör tipi: dict mi?
"""

import numpy as np
import pytest

from app.core.embedder import Embedder


# Model yükleme maliyetli — tüm testler aynı instance'ı kullanır.
@pytest.fixture(scope="module")
def embedder() -> Embedder:
    return Embedder()


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Temel fonksiyonellik
# ─────────────────────────────────────────────────────────────────────────────


class TestBasicEncoding:
    """Dense + sparse vektörlerin üretildiğini doğrular."""

    def test_single_text_returns_one_vector(self, embedder):
        """Tek metin için 1 dense ve 1 sparse vektör üretilmeli."""
        result = embedder.encode(["Merhaba dünya"])

        assert len(result["dense"]) == 1, "1 metin için 1 dense vektör olmalı"
        assert len(result["sparse"]) == 1, "1 metin için 1 sparse vektör olmalı"

    def test_multiple_texts_return_same_count(self, embedder):
        """N metin için N dense ve N sparse vektör üretilmeli."""
        texts = ["birinci metin", "ikinci metin", "üçüncü metin"]
        result = embedder.encode(texts)

        assert len(result["dense"]) == 3, "3 metin için 3 dense vektör olmalı"
        assert len(result["sparse"]) == 3, "3 metin için 3 sparse vektör olmalı"

    def test_result_has_dense_and_sparse_keys(self, embedder):
        """Dönen dict 'dense' ve 'sparse' anahtarlarını içermeli."""
        result = embedder.encode(["test"])

        assert "dense" in result
        assert "sparse" in result


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: Dense vektör boyutu
# ─────────────────────────────────────────────────────────────────────────────


class TestDenseVectorDimension:
    """BGE-M3 her zaman 1024 boyutlu dense vektör üretir."""

    def test_dense_dimension_is_1024(self, embedder):
        """Dense vektör boyutu 1024 olmalı."""
        result = embedder.encode(["boyut testi"])
        dim = len(result["dense"][0])

        assert dim == 1024, f"Dense boyut 1024 olmalı, gelen: {dim}"

    def test_dense_vector_is_list_of_floats(self, embedder):
        """Dense vektör float'lardan oluşan bir liste olmalı."""
        result = embedder.encode(["tip testi"])
        vec = result["dense"][0]

        assert isinstance(vec, list), "Dense vektör list olmalı"
        assert all(isinstance(v, float) for v in vec), "Dense vektör elemanları float olmalı"


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Sparse vektör tipi
# ─────────────────────────────────────────────────────────────────────────────


class TestSparseVector:
    """Sparse vektörün beklenen formatını doğrular."""

    def test_sparse_vector_is_dict(self, embedder):
        """Sparse vektör {token_id: weight} formatında dict olmalı."""
        result = embedder.encode(["sparse test metni"])
        sparse = result["sparse"][0]

        assert isinstance(sparse, dict), "Sparse vektör dict olmalı"

    def test_sparse_vector_is_not_empty(self, embedder):
        """Normal bir metin için sparse vektör en az bir token içermeli."""
        result = embedder.encode(["sparse dolu olmalı"])
        sparse = result["sparse"][0]

        assert len(sparse) > 0, "Sparse vektör boş olmamalı"


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: Boş liste güvenliği
# ─────────────────────────────────────────────────────────────────────────────


class TestEmptyListHandling:
    """FlagEmbedding boş listede crash ettiğinden erken dönüş zorunlu."""

    def test_empty_list_returns_empty_dense(self, embedder):
        """Boş liste boş dense listesi döndürmeli."""
        result = embedder.encode([])
        assert result["dense"] == []

    def test_empty_list_returns_empty_sparse(self, embedder):
        """Boş liste boş sparse listesi döndürmeli."""
        result = embedder.encode([])
        assert result["sparse"] == []

    def test_empty_list_does_not_raise(self, embedder):
        """Boş liste exception fırlatmamalı."""
        try:
            embedder.encode([])
        except Exception as e:
            pytest.fail(f"Boş liste exception fırlattı: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: encode_query kısayolu
# ─────────────────────────────────────────────────────────────────────────────


class TestEncodeQuery:
    """encode_query single-item encode'un kısayoludur."""

    def test_query_dense_dimension_is_1024(self, embedder):
        """Query dense vektörü 1024 boyutlu olmalı."""
        q = embedder.encode_query("sözleşmenin fesih cezası nedir?")

        assert len(q["dense"]) == 1024, "Query dense 1024 boyutlu olmalı"

    def test_query_sparse_is_dict(self, embedder):
        """Query sparse vektörü dict olmalı."""
        q = embedder.encode_query("test sorusu")

        assert isinstance(q["sparse"], dict), "Query sparse dict olmalı"

    def test_query_dense_is_flat_list(self, embedder):
        """encode_query tek vektör döndürmeli, liste-içinde-liste değil."""
        q = embedder.encode_query("düz liste testi")
        dense = q["dense"]

        assert isinstance(dense, list), "Dense list olmalı"
        # İlk eleman float olmalı, iç içe liste olmamalı
        assert isinstance(dense[0], float), "Dense'in ilk elemanı float olmalı (iç içe liste değil)"


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Anlamsal benzerlik
# ─────────────────────────────────────────────────────────────────────────────


def _cosine_sim(a: list[float], b: list[float]) -> float:
    """İki vektörün cosine benzerliğini hesaplar."""
    a_arr, b_arr = np.array(a), np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


class TestSemanticSimilarity:
    """BGE-M3'ün anlamsal benzerlik ürettiğini doğrular."""

    def test_related_texts_are_more_similar_than_unrelated(self, embedder):
        """
        'kira artışı' ve 'kiralama bedeli yükselmesi' anlamsal olarak yakın olmalı.
        'futbol maçı sonuçları' ile aralarındaki benzerlik daha düşük olmalı.
        """
        r1 = embedder.encode(["kira artışı"])["dense"][0]
        r2 = embedder.encode(["kiralama bedeli yükselmesi"])["dense"][0]
        r3 = embedder.encode(["futbol maçı sonuçları"])["dense"][0]

        sim_related = _cosine_sim(r1, r2)
        sim_unrelated = _cosine_sim(r1, r3)

        assert sim_related > sim_unrelated, (
            f"İlişkili metinler daha yüksek benzerlik almalı. "
            f"İlişkili: {sim_related:.3f}, İlişkisiz: {sim_unrelated:.3f}"
        )

    def test_identical_texts_have_max_similarity(self, embedder):
        """Aynı metnin cosine benzerliği ~1.0 olmalı."""
        text = "Bu bir test cümlesidir."
        v1 = embedder.encode([text])["dense"][0]
        v2 = embedder.encode([text])["dense"][0]

        sim = _cosine_sim(v1, v2)
        assert sim > 0.99, f"Aynı metin için benzerlik ~1.0 olmalı, gelen: {sim:.4f}"
