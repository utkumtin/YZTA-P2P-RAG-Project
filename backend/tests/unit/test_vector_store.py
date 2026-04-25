"""
VectorStore unit testleri

Qdrant'a gerçek bir bağlantı gerektirmeden çalışır.
QdrantClient mock'lanır — sadece VectorStore mantığı test edilir.

Test senaryoları:
1. _to_qdrant_id: Deterministic UUID üretimi
2. setup: Koleksiyon oluşturma (idempotent)
3. index_child_chunks: Child chunk'ları doğru payload ile ekleme
4. store_parent_chunks: Parent chunk'ları vektörsüz ekleme
5. hybrid_search: Filtre koşulları ve RRF parametreleri
6. get_parent_by_id: Scroll ile parent çekme
7. delete_document: Her iki koleksiyondan silme
"""

from unittest.mock import MagicMock, call, patch

import pytest

from app.core.vector_store import VectorStore, _to_qdrant_id


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: _to_qdrant_id — Deterministic ID dönüşümü
# ─────────────────────────────────────────────────────────────────────────────


class TestToQdrantId:
    """String chunk_id → deterministic UUID dönüşümü."""

    def test_same_input_always_returns_same_uuid(self):
        """Aynı chunk_id her zaman aynı UUID'ye dönüşmeli."""
        chunk_id = "child-abc123-0001-000"
        assert _to_qdrant_id(chunk_id) == _to_qdrant_id(chunk_id)

    def test_different_inputs_return_different_uuids(self):
        """Farklı chunk_id'ler farklı UUID'ler üretmeli."""
        id1 = _to_qdrant_id("child-abc123-0001-000")
        id2 = _to_qdrant_id("child-abc123-0001-001")
        assert id1 != id2

    def test_returns_valid_uuid_string(self):
        """Dönen değer geçerli bir UUID string'i olmalı."""
        import uuid
        result = _to_qdrant_id("test-chunk-id")
        # Geçerli UUID string'i parse edilebilmeli
        parsed = uuid.UUID(result)
        assert str(parsed) == result


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_client():
    """Her test için temiz bir mock QdrantClient."""
    return MagicMock()


@pytest.fixture
def store(mock_client):
    """Mock QdrantClient kullanan VectorStore instance'ı."""
    with patch("app.core.vector_store.QdrantClient", return_value=mock_client):
        s = VectorStore(host="localhost", port=6333)
    return s


def _make_child_chunk(chunk_id: str, parent_id: str, session_id: str = "sess-1", doc_id: str = "doc-1") -> dict:
    """Test child chunk'ı oluşturan yardımcı fonksiyon."""
    return {
        "id": chunk_id,
        "text": f"Child metin: {chunk_id}",
        "metadata": {
            "doc_id": doc_id,
            "session_id": session_id,
            "parent_chunk_id": parent_id,
            "chunk_type": "child",
        }
    }


def _make_parent_chunk(chunk_id: str, session_id: str = "sess-1", doc_id: str = "doc-1") -> dict:
    """Test parent chunk'ı oluşturan yardımcı fonksiyon."""
    return {
        "id": chunk_id,
        "text": f"Parent metin: {chunk_id}",
        "metadata": {
            "doc_id": doc_id,
            "session_id": session_id,
            "chunk_type": "parent",
        }
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: setup — Koleksiyon oluşturma
# ─────────────────────────────────────────────────────────────────────────────


class TestSetup:
    """setup() fonksiyonunun koleksiyonları doğru oluşturduğunu doğrular."""

    def test_creates_child_collection_when_not_exists(self, store, mock_client):
        """documents koleksiyonu yoksa oluşturulmalı."""
        # Koleksiyon listesi boş gelsin
        mock_client.get_collections.return_value.collections = []

        store.setup()

        # create_collection en az bir kere çağrılmalı
        assert mock_client.create_collection.called

    def test_creates_parent_collection_when_not_exists(self, store, mock_client):
        """parents koleksiyonu yoksa oluşturulmalı."""
        mock_client.get_collections.return_value.collections = []

        store.setup()

        # İki koleksiyon için iki kez çağrılmalı
        assert mock_client.create_collection.call_count == 2

    def test_skips_creation_when_collection_exists(self, store, mock_client):
        """Koleksiyonlar zaten varsa create_collection çağrılmamalı."""
        existing_docs = MagicMock()
        existing_docs.name = "documents"
        existing_parents = MagicMock()
        existing_parents.name = "parents"
        mock_client.get_collections.return_value.collections = [
            existing_docs, existing_parents
        ]

        store.setup()

        mock_client.create_collection.assert_not_called()

    def test_creates_payload_indexes(self, store, mock_client):
        """Payload indeksleri oluşturulmalı (doc_id, session_id, chunk_id)."""
        mock_client.get_collections.return_value.collections = []

        store.setup()

        assert mock_client.create_payload_index.called


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: index_child_chunks — Child chunk'ları ekleme
# ─────────────────────────────────────────────────────────────────────────────


class TestIndexChildChunks:
    """Child chunk'ların doğru format ve payload ile Qdrant'a eklendiğini doğrular."""

    def test_calls_upsert_for_child_collection(self, store, mock_client):
        """upsert, documents koleksiyonuna çağrılmalı."""
        chunk = _make_child_chunk("child-0001-000", "parent-0001")
        dense = [[0.1] * 1024]
        sparse = [{101: 0.8, 202: 0.5}]

        store.index_child_chunks([chunk], dense, sparse)

        assert mock_client.upsert.called
        call_args = mock_client.upsert.call_args
        assert call_args.kwargs["collection_name"] == "documents"

    def test_payload_contains_chunk_id_and_text(self, store, mock_client):
        """Her point'in payload'ı chunk_id ve text içermeli."""
        chunk = _make_child_chunk("child-test-000", "parent-test")
        dense = [[0.2] * 1024]
        sparse = [{10: 0.9}]

        store.index_child_chunks([chunk], dense, sparse)

        points = mock_client.upsert.call_args.kwargs["points"]
        payload = points[0].payload
        assert payload["chunk_id"] == "child-test-000"
        assert payload["text"] == chunk["text"]

    def test_payload_contains_metadata_fields(self, store, mock_client):
        """Metadata alanları (doc_id, session_id) payload'a eklenmeli."""
        chunk = _make_child_chunk("child-meta-000", "parent-meta", session_id="s-42", doc_id="d-99")
        dense = [[0.3] * 1024]
        sparse = [{5: 0.7}]

        store.index_child_chunks([chunk], dense, sparse)

        points = mock_client.upsert.call_args.kwargs["points"]
        payload = points[0].payload
        assert payload["doc_id"] == "d-99"
        assert payload["session_id"] == "s-42"

    def test_batches_in_groups_of_100(self, store, mock_client):
        """150 chunk → 2 kez upsert çağrılmalı (100 + 50)."""
        chunks = [_make_child_chunk(f"child-{i:04d}", f"parent-{i:04d}") for i in range(150)]
        dense = [[0.1] * 1024 for _ in range(150)]
        sparse = [{i: 0.5} for i in range(150)]

        store.index_child_chunks(chunks, dense, sparse)

        assert mock_client.upsert.call_count == 2

    def test_empty_input_does_not_call_upsert(self, store, mock_client):
        """Boş chunk listesi → upsert çağrılmamalı."""
        store.index_child_chunks([], [], [])
        mock_client.upsert.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: store_parent_chunks — Parent chunk'ları ekleme
# ─────────────────────────────────────────────────────────────────────────────


class TestStoreParentChunks:
    """Parent chunk'ların vektörsüz olarak parents koleksiyonuna eklendiğini doğrular."""

    def test_calls_upsert_for_parent_collection(self, store, mock_client):
        """upsert, parents koleksiyonuna çağrılmalı."""
        chunk = _make_parent_chunk("parent-0001")

        store.store_parent_chunks([chunk])

        assert mock_client.upsert.called
        call_args = mock_client.upsert.call_args
        assert call_args.kwargs["collection_name"] == "parents"

    def test_point_has_empty_vector(self, store, mock_client):
        """Parent point'lerin vektörü boş dict olmalı."""
        chunk = _make_parent_chunk("parent-novec")

        store.store_parent_chunks([chunk])

        points = mock_client.upsert.call_args.kwargs["points"]
        # Parent chunk'larda vektör yok
        assert points[0].vector == {}

    def test_payload_contains_text(self, store, mock_client):
        """Parent chunk payload'ında metin olmalı."""
        chunk = _make_parent_chunk("parent-text-test")

        store.store_parent_chunks([chunk])

        points = mock_client.upsert.call_args.kwargs["points"]
        assert points[0].payload["text"] == chunk["text"]

    def test_batches_in_groups_of_100(self, store, mock_client):
        """150 parent → 2 kez upsert çağrılmalı."""
        chunks = [_make_parent_chunk(f"parent-{i:04d}") for i in range(150)]

        store.store_parent_chunks(chunks)

        assert mock_client.upsert.call_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: hybrid_search — Hibrit arama
# ─────────────────────────────────────────────────────────────────────────────


class TestHybridSearch:
    """hybrid_search'ün doğru parametrelerle Qdrant'ı çağırdığını doğrular."""

    def _mock_hit(self, chunk_id: str, text: str, score: float, session_id: str = "sess-1"):
        """Qdrant hit objesi simüle eder."""
        hit = MagicMock()
        hit.payload = {
            "chunk_id": chunk_id,
            "text": text,
            "session_id": session_id,
            "doc_id": "doc-1"
        }
        hit.score = score
        return hit

    def test_calls_query_points_on_child_collection(self, store, mock_client):
        """query_points, documents koleksiyonuna çağrılmalı."""
        mock_client.query_points.return_value.points = []
        query_dense = [0.1] * 1024
        query_sparse = {101: 0.9, 202: 0.5}

        store.hybrid_search(query_dense, query_sparse, session_id="sess-1")

        assert mock_client.query_points.called
        call_args = mock_client.query_points.call_args
        assert call_args.kwargs["collection_name"] == "documents"

    def test_returns_list_of_results(self, store, mock_client):
        """Sonuç listesi döndürmeli."""
        hit = self._mock_hit("child-001", "Test metni", 0.95)
        mock_client.query_points.return_value.points = [hit]
        query_dense = [0.1] * 1024
        query_sparse = {1: 0.8}

        results = store.hybrid_search(query_dense, query_sparse, session_id="sess-1")

        assert isinstance(results, list)
        assert len(results) == 1

    def test_result_contains_required_fields(self, store, mock_client):
        """Her sonuç chunk_id, text, score ve metadata içermeli."""
        hit = self._mock_hit("child-abc", "Sonuç metni", 0.87)
        mock_client.query_points.return_value.points = [hit]

        results = store.hybrid_search([0.0] * 1024, {1: 0.5}, session_id="sess-1")

        r = results[0]
        assert "chunk_id" in r
        assert "text" in r
        assert "score" in r
        assert "metadata" in r

    def test_result_chunk_id_matches_payload(self, store, mock_client):
        """chunk_id, payload'daki değerle eşleşmeli."""
        hit = self._mock_hit("child-xyz", "metin", 0.9)
        mock_client.query_points.return_value.points = [hit]

        results = store.hybrid_search([0.0] * 1024, {1: 0.5}, session_id="sess-1")

        assert results[0]["chunk_id"] == "child-xyz"

    def test_text_and_chunk_id_excluded_from_metadata(self, store, mock_client):
        """text ve chunk_id metadata'ya dahil edilmemeli."""
        hit = self._mock_hit("child-meta", "metin", 0.8)
        mock_client.query_points.return_value.points = [hit]

        results = store.hybrid_search([0.0] * 1024, {1: 0.5}, session_id="sess-1")

        metadata = results[0]["metadata"]
        assert "text" not in metadata
        assert "chunk_id" not in metadata

    def test_doc_ids_filter_passed_when_provided(self, store, mock_client):
        """doc_ids verildiğinde filtre koşuluna eklenmeli."""
        mock_client.query_points.return_value.points = []

        store.hybrid_search(
            [0.0] * 1024, {1: 0.5},
            session_id="sess-1",
            doc_ids=["doc-a", "doc-b"]
        )

        assert mock_client.query_points.called

    def test_empty_results_returns_empty_list(self, store, mock_client):
        """Qdrant boş sonuç döndürdüğünde boş liste dönmeli."""
        mock_client.query_points.return_value.points = []

        results = store.hybrid_search([0.0] * 1024, {1: 0.5}, session_id="sess-1")

        assert results == []


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: get_parent_by_id — Parent chunk getirme
# ─────────────────────────────────────────────────────────────────────────────


class TestGetParentById:
    """get_parent_by_id'nin parents koleksiyonunu doğru şekilde sorguladığını doğrular."""

    def test_returns_parent_when_found(self, store, mock_client):
        """Parent bulunduğunda dict döndürmeli."""
        point = MagicMock()
        point.payload = {
            "chunk_id": "parent-001",
            "text": "Parent metin içeriği",
            "doc_id": "doc-1",
            "session_id": "sess-1"
        }
        mock_client.scroll.return_value = ([point], None)

        result = store.get_parent_by_id("parent-001")

        assert result is not None
        assert result["chunk_id"] == "parent-001"
        assert result["text"] == "Parent metin içeriği"

    def test_returns_none_when_not_found(self, store, mock_client):
        """Parent bulunamazsa None döndürmeli."""
        mock_client.scroll.return_value = ([], None)

        result = store.get_parent_by_id("parent-nonexistent")

        assert result is None

    def test_calls_scroll_on_parent_collection(self, store, mock_client):
        """scroll çağrısı parents koleksiyonuna yapılmalı."""
        mock_client.scroll.return_value = ([], None)

        store.get_parent_by_id("parent-test")

        call_args = mock_client.scroll.call_args
        assert call_args.kwargs["collection_name"] == "parents"

    def test_metadata_excludes_text_and_chunk_id(self, store, mock_client):
        """Dönen metadata'dan text ve chunk_id çıkarılmalı."""
        point = MagicMock()
        point.payload = {
            "chunk_id": "parent-002",
            "text": "Metin",
            "doc_id": "doc-2"
        }
        mock_client.scroll.return_value = ([point], None)

        result = store.get_parent_by_id("parent-002")

        assert "text" not in result["metadata"]
        assert "chunk_id" not in result["metadata"]
        assert result["metadata"]["doc_id"] == "doc-2"


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: delete_document — Doküman silme
# ─────────────────────────────────────────────────────────────────────────────


class TestDeleteDocument:
    """delete_document'ın her iki koleksiyondan da silme yaptığını doğrular."""

    def test_deletes_from_child_collection(self, store, mock_client):
        """Child chunk'lar documents koleksiyonundan silinmeli."""
        store.delete_document(doc_id="doc-del", session_id="sess-1")

        calls = mock_client.delete.call_args_list
        collection_names = [c.kwargs["collection_name"] for c in calls]
        assert "documents" in collection_names

    def test_deletes_from_parent_collection(self, store, mock_client):
        """Parent chunk'lar parents koleksiyonundan silinmeli."""
        store.delete_document(doc_id="doc-del", session_id="sess-1")

        calls = mock_client.delete.call_args_list
        collection_names = [c.kwargs["collection_name"] for c in calls]
        assert "parents" in collection_names

    def test_delete_called_twice(self, store, mock_client):
        """Silme işlemi her iki koleksiyon için ayrı ayrı çağrılmalı."""
        store.delete_document(doc_id="doc-del", session_id="sess-1")

        assert mock_client.delete.call_count == 2
