"""
Qdrant vektör veritabanı yönetimi.
Koleksiyon oluşturma, indeksleme, hibrit arama, silme.

Mimari:
- documents koleksiyonu: Child chunk'lar (Dense + Sparse vektörlerle)
- parents koleksiyonu: Parent chunk'lar (vektörsüz, sadece metin deposu)

PRD Referans: Bölüm 9 — Vektör Veritabanı
"""

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)


# =========================================================================
# DETERMINISTIC ID DÖNÜŞÜMÜ
# =========================================================================
# Qdrant point ID'leri integer veya UUID string olmalı.
# String chunk_id'lerimizi ("child-abc-0001-000" gibi) doğrudan kullanamıyoruz.
#
# NEDEN hash() DEĞİL:
# Python'un built-in hash() fonksiyonu process-specific — PYTHONHASHSEED
# environment variable set edilmediyse, farklı Python process'lerinde aynı
# string için FARKLI değerler üretir. Worker restart sonrası chunk ID'leri
# değişebilir, mevcut vektörlerle eşleşmez.
#
# ÇÖZÜM: uuid.uuid5() deterministic — aynı (namespace, name) her zaman aynı UUID.
# Qdrant UUID string'i doğrudan kabul eder, extra dönüşüm gerekmez.

# Projeye özel namespace. Değiştirirsen tüm point ID'leri değişir
# ve Qdrant koleksiyonlarını baştan reindex etmen gerekir.
_ID_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def _to_qdrant_id(chunk_id: str) -> str:
    """
    String chunk_id'yi Qdrant-uyumlu deterministic UUID'ye dönüştürür.

    Örnek:
        "child-abc123-0001-000" → "a1b2c3d4-e5f6-..." (her zaman aynı)

    Args:
        chunk_id: Chunker'dan gelen string ID

    Returns:
        UUID string — Qdrant point ID olarak doğrudan kullanılabilir
    """
    return str(uuid.uuid5(_ID_NAMESPACE, chunk_id))


class VectorStore:
    """
    Qdrant üzerinde vektör işlemleri.

    Kullanım:
        store = VectorStore(host="localhost", port=6333)
        store.setup()                    # Koleksiyonları oluştur (bir kez)
        store.index_child_chunks(...)    # Child chunk'ları indeksle
        store.store_parent_chunks(...)   # Parent chunk'ları depola
        results = store.hybrid_search(...)  # Hibrit arama yap
    """

    CHILD_COLLECTION = "documents"   # Child chunk koleksiyonu
    PARENT_COLLECTION = "parents"    # Parent chunk koleksiyonu
    DENSE_VECTOR_SIZE = 1024         # BGE-M3 çıktı boyutu

    def __init__(self, host: str = "qdrant", port: int = 6333):
        """
        Args:
            host: Qdrant sunucu adresi. Docker'da "qdrant", lokalde "localhost"
            port: Qdrant HTTP portu. Varsayılan: 6333
        """
        self.client = QdrantClient(host=host, port=port)

    def setup(self):
        """
        Koleksiyonları oluşturur. Zaten varsa dokunmaz (idempotent).

        BU FONKSİYONU uygulama başlatıldığında BİR KERE çağır.
        Backend'ci bunu FastAPI lifespan event'inde çağırmalı.
        """
        # ---- Child chunk koleksiyonu ----
        # Dense + Sparse vektörler burada saklanır
        self._create_collection_if_not_exists(
            self.CHILD_COLLECTION,
            vectors_config={
                "dense": VectorParams(
                    size=self.DENSE_VECTOR_SIZE,
                    distance=Distance.COSINE  # Cosine benzerliği kullanıyoruz
                )
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams()
            }
        )

        # Payload indeksleri oluştur — arama sırasında filtrelemeyi hızlandırır
        try:
            self.client.create_payload_index(
                collection_name=self.CHILD_COLLECTION,
                field_name="doc_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=self.CHILD_COLLECTION,
                field_name="session_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
        except Exception:
            pass  # İndeks zaten varsa hata vermesini engelle

        # ---- Parent chunk koleksiyonu ----
        # Vektör YOK — sadece metin deposu
        self._create_collection_if_not_exists(
            self.PARENT_COLLECTION,
            vectors_config={}
        )

        # Parent koleksiyonunda chunk_id, doc_id ve session_id ile filtreleme lazım
        try:
            self.client.create_payload_index(
                collection_name=self.PARENT_COLLECTION,
                field_name="chunk_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=self.PARENT_COLLECTION,
                field_name="doc_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
            self.client.create_payload_index(
                collection_name=self.PARENT_COLLECTION,
                field_name="session_id",
                field_schema=PayloadSchemaType.KEYWORD
            )
        except Exception:
            pass

    def _create_collection_if_not_exists(self, name: str, **kwargs):
        """Koleksiyon yoksa oluştur, varsa dokunma."""
        collections = [c.name for c in self.client.get_collections().collections]
        if name not in collections:
            self.client.create_collection(collection_name=name, **kwargs)

    # =======================================================================
    # İNDEKSLEME (Ingestion Pipeline'ın son adımı)
    # =======================================================================

    def index_child_chunks(
        self,
        child_chunks: list[dict],
        dense_embeddings: list[list[float]],
        sparse_embeddings: list[dict]
    ):
        """
        Child chunk'ları Qdrant'a ekler.

        Args:
            child_chunks: chunker'dan gelen child listesi
            dense_embeddings: embedder.encode() çıktısı — dense
            sparse_embeddings: embedder.encode() çıktısı — sparse

        BATCH EKLEME: 100'erli gruplar halinde eklenir.
        10.000 chunk'ı tek seferde göndermek network timeout verir.
        """
        points = []

        for i, chunk in enumerate(child_chunks):
            sparse_indices = list(sparse_embeddings[i].keys())
            sparse_values = list(sparse_embeddings[i].values())

            # String chunk_id → deterministic UUID
            # Detaylar için dosyanın üstündeki _to_qdrant_id docstring'ine bak
            point = PointStruct(
                id=_to_qdrant_id(chunk["id"]),
                vector={
                    "dense": dense_embeddings[i],
                    "sparse": SparseVector(
                        indices=sparse_indices,
                        values=sparse_values
                    )
                },
                payload={
                    "chunk_id": chunk["id"],
                    "text": chunk["text"],
                    **chunk["metadata"]
                }
            )
            points.append(point)

        # 100'erli batch'ler halinde ekle
        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.CHILD_COLLECTION,
                points=batch
            )

    def store_parent_chunks(self, parent_chunks: list[dict]):
        """
        Parent chunk'ları Qdrant'a kaydeder (vektör OLMADAN).
        Sadece metin ve metadata depolama.
        """
        points = []

        for chunk in parent_chunks:
            point = PointStruct(
                id=_to_qdrant_id(chunk["id"]),
                vector={},  # Vektör yok
                payload={
                    "chunk_id": chunk["id"],
                    "text": chunk["text"],
                    **chunk["metadata"]
                }
            )
            points.append(point)

        batch_size = 100
        for i in range(0, len(points), batch_size):
            batch = points[i:i + batch_size]
            self.client.upsert(
                collection_name=self.PARENT_COLLECTION,
                points=batch
            )

    # =======================================================================
    # HİBRİT ARAMA (Query Pipeline'ın retrieval adımı)
    # PRD Referans: Bölüm 9.5
    # =======================================================================

    def hybrid_search(
        self,
        query_dense: list[float],
        query_sparse: dict,
        session_id: str,
        doc_ids: list[str] = None,
        top_k: int = 20
    ) -> list[dict]:
        """
        Hibrit arama: Dense + Sparse sonuçları RRF ile birleştirilir.

        RRF (Reciprocal Rank Fusion) nasıl çalışır:
        - Dense arama → sıralı liste (anlamsal benzerlik)
        - Sparse arama → sıralı liste (kelime eşleşmesi)
        - RRF_score(doc) = Σ 1/(k + rank_i(doc))
        - Her iki listede de üst sıralarda olan dokümanlar kazanır

        Qdrant bunu Fusion.RRF ile otomatik yapıyor.

        Args:
            query_dense: Sorgunun dense vektörü (1024 boyutlu)
            query_sparse: Sorgunun sparse vektörü {token_id: weight}
            session_id: Kullanıcı oturum kimliği (izolasyon için ZORUNLU)
            doc_ids: Belirli dokümanlara kısıtlama (None = tüm dokümanlar)
            top_k: Kaç sonuç döndürmek istediğimiz

        Returns:
            list[dict]: [{"chunk_id": str, "text": str, "score": float, "metadata": dict}]
        """
        # Filtre oluştur — session_id ile kullanıcı izolasyonu
        must_conditions = [
            FieldCondition(key="session_id", match=MatchValue(value=session_id))
        ]

        # Belirli doküman filtreleme (opsiyonel)
        if doc_ids:
            must_conditions.append(
                FieldCondition(key="doc_id", match=MatchAny(any=doc_ids))
            )

        filter_condition = Filter(must=must_conditions)

        # Sparse vektörü Qdrant formatına dönüştür
        sparse_indices = list(query_sparse.keys())
        sparse_values = list(query_sparse.values())

        # Hibrit arama: Dense + Sparse → RRF birleşim
        results = self.client.query_points(
            collection_name=self.CHILD_COLLECTION,
            prefetch=[
                # Dense arama kolu — anlamsal benzerlik
                Prefetch(
                    query=query_dense,
                    using="dense",
                    limit=top_k,
                    filter=filter_condition
                ),
                # Sparse arama kolu — kelime bazlı eşleşme
                Prefetch(
                    query=SparseVector(
                        indices=sparse_indices,
                        values=sparse_values
                    ),
                    using="sparse",
                    limit=top_k,
                    filter=filter_condition
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=top_k
        )

        return [
            {
                "chunk_id": hit.payload.get("chunk_id"),
                "text": hit.payload.get("text"),
                "score": hit.score,
                "metadata": {
                    k: v for k, v in hit.payload.items()
                    if k not in ("text", "chunk_id")
                }
            }
            for hit in results.points
        ]

    def get_parent_by_id(self, parent_chunk_id: str) -> dict | None:
        """
        Parent koleksiyonundan parent chunk'ı ID ile getirir.
        Child chunk bulunduktan sonra bu fonksiyon ile parent metin çekilir.
        """
        results = self.client.scroll(
            collection_name=self.PARENT_COLLECTION,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="chunk_id",
                        match=MatchValue(value=parent_chunk_id)
                    )
                ]
            ),
            limit=1
        )

        points = results[0]
        if points:
            p = points[0]
            return {
                "chunk_id": p.payload.get("chunk_id"),
                "text": p.payload.get("text"),
                "metadata": {
                    k: v for k, v in p.payload.items()
                    if k not in ("text", "chunk_id")
                }
            }
        return None

    def delete_document(self, doc_id: str, session_id: str):
        """
        Bir dokümanın tüm chunk'larını siler (child + parent).
        Kullanıcı dokümanı sildiğinde çağrılır.
        """
        filter_condition = Filter(
            must=[
                FieldCondition(key="doc_id", match=MatchValue(value=doc_id)),
                FieldCondition(key="session_id", match=MatchValue(value=session_id))
            ]
        )

        self.client.delete(
            collection_name=self.CHILD_COLLECTION,
            points_selector=filter_condition
        )
        self.client.delete(
            collection_name=self.PARENT_COLLECTION,
            points_selector=filter_condition
        )
