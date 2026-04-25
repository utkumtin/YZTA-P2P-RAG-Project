"""
RAG Pipeline Orkestratörü.
Tüm bileşenleri birleştirir: arama, reranking, ebeveyn çözümleme, LLM.

İki ana akış:
1. Ingestion: Dosya yükle → metin çıkar → temizle → parçala → embed → indeksle
2. Query: Soru soruldu → cache kontrol → ara → rerank → parent chunk'ları getir → LLM
"""

from collections.abc import AsyncGenerator

from app.core.chunker import create_parent_child_chunks
from app.core.document_processor import DocumentProcessor
from app.core.embedder import Embedder
from app.core.llm_client import (
    SYSTEM_PROMPT,
    BaseLLMClient,
    build_rag_prompt,
)
from app.core.reranker import Reranker
from app.core.semantic_cache import SemanticCache
from app.core.vector_store import VectorStore


class RAGPipeline:
    """
    Ana RAG orkestratörü. Backend API endpoint'leri bu sınıfı kullanır.

    Kullanım:
        pipeline = RAGPipeline(
            embedder, vector_store, reranker, llm_client, cache
        )

        # Ingestion (arka plan worker'da çağrılır)
        result = await pipeline.ingest_document(file_path, doc_id, session_id)

        # Query (API endpoint'inde çağrılır)
        answer, sources = await pipeline.query("sorum nedir?", session_id)

        # Streaming query (SSE endpoint'inde)
        async for token in pipeline.query_stream("sorum?", session_id):
            print(token, end="")
    """

    def __init__(
        self,
        embedder: Embedder,
        vector_store: VectorStore,
        reranker: Reranker,
        llm_client: BaseLLMClient,
        cache: SemanticCache | None = None,
        search_top_k: int = 20,
        final_top_k: int = 5,
    ):
        """
        Args:
            embedder: BGE-M3 embedder (singleton)
            vector_store: Qdrant wrapper
            reranker: Cross-encoder reranker
            llm_client: Groq veya Gemini client
            cache: Semantic cache (opsiyonel)
            search_top_k: Hibrit aramadan kaç aday gelsin (varsayılan: 20)
            final_top_k: Reranking sonrası kaç chunk LLM'e gitsin
                (varsayılan: 5)
        """
        self.embedder = embedder
        self.vector_store = vector_store
        self.reranker = reranker
        self.llm_client = llm_client
        self.cache = cache
        self.processor = DocumentProcessor()
        self.search_top_k = search_top_k
        self.final_top_k = final_top_k

    # =======================================================================
    # INGESTION PIPELINE
    # Dosya yüklendiğinde çağrılır (ARQ worker içinden)
    # =======================================================================

    async def ingest_document(
        self,
        file_path: str,
        doc_id: str,
        session_id: str,
        progress_callback=None,
    ) -> dict:
        """
        Dosyayı işleyip vektör veritabanına indeksler.

        Adımlar:
        1. Metin çıkarma (format'a göre)
        2. Metadata hazırlama
        3. Ebeveyn-Çocuk chunking
        4. Embedding üretimi (SADECE çocuk chunk'lar)
        5. Qdrant'a indeksleme (çocuk + ebeveyn ayrı koleksiyonlara)

        Args:
            file_path: Diskteki dosya yolu
            doc_id: UUID (backend'ci tarafından üretilir)
            session_id: Kullanıcı oturum kimliği
            progress_callback: İlerleme bildirimi fonksiyonu (opsiyonel)
                async def callback(step: str, progress: float) -> None

        Returns:
            {"doc_id": str, "parent_count": int, "child_count": int}
        """
        # 1. Metin çıkarma
        if progress_callback:
            await progress_callback("Metin çıkarlıyor...", 0.1)

        result = self.processor.process(file_path, doc_id=doc_id)

        # 2. Metadata hazırlama
        metadata = {
            "doc_id": doc_id,
            "filename": result["filename"],
            "file_type": result["file_type"],
            "language": result["language"],
            "session_id": session_id,
        }

        # 3. Parçalama
        if progress_callback:
            await progress_callback("Parçalanıyor...", 0.3)

        parents, children = create_parent_child_chunks(
            result["full_text"],
            metadata,
        )

        # 4. Embedding üretimi (SADECE çocuk chunk'lar)
        # Ebeveynler vektörsüz saklanır (arama çocukta yapılıyor)
        if progress_callback:
            await progress_callback("Embedding üretiliyor...", 0.5)

        child_texts = [c["text"] for c in children]
        embeddings = self.embedder.encode(child_texts)

        # 5. Qdrant'a indeksleme
        if progress_callback:
            await progress_callback("İndeksleniyor...", 0.8)

        # Ebeveynler önce — çocuklar aranırken ebeveyn çözümleme çalışsın diye
        self.vector_store.store_parent_chunks(parents)
        self.vector_store.index_child_chunks(
            children,
            embeddings["dense"],
            embeddings["sparse"],
        )

        # Yeni doküman eklendi → ilgili cache'leri invalidate et
        # (opsiyonel iyileştirme)

        if progress_callback:
            await progress_callback("Tamamlandı", 1.0)

        return {
            "doc_id": doc_id,
            "parent_count": len(parents),
            "child_count": len(children),
        }

    # =======================================================================
    # QUERY PIPELINE (non-streaming)
    # =======================================================================

    async def query(
        self,
        question: str,
        session_id: str,
        doc_ids: list[str] | None = None,
    ) -> tuple[str, list[dict]]:
        """
        Soru-cevap pipeline'ı (streaming olmadan).

        Akış:
        1. Semantik cache kontrolü
        2. Soru embedding
        3. Hibrit arama → Top-20 çocuk chunk
        4. Reranking → Top-5 çocuk chunk
        5. Ebeveyn çözümleme → 5 ebeveyn chunk
        6. LLM cevap üretimi
        7. Cache'e kaydet

        Args:
            question: Kullanıcının sorusu
            session_id: Kullanıcı oturum kimliği (izolasyon)
            doc_ids: Belirli dokümanlara kısıtlama (None = hepsi)

        Returns:
            (cevap_metni, kaynak_listesi)
            kaynak_listesi: [
                {"filename": str, "page_number": int|None, "doc_id": str}, ...
            ]
        """
        # 1. Cache kontrolü
        if self.cache:
            cached = await self.cache.get(question)
            if cached:
                return cached["answer"], cached["sources"]

        # 2-5. Retrieval + Reranking + Parent resolution
        context_chunks = await self._retrieve_and_resolve(question, session_id, doc_ids)

        # Hiç alakalı chunk bulunamadıysa
        if not context_chunks:
            return (
                "Yüklediğiniz dokümanlarda bu sorunun cevabını bulamadım.",
                [],
            )

        # 6. LLM cevap üretimi
        prompt = build_rag_prompt(question, context_chunks)
        answer = await self.llm_client.generate(prompt, SYSTEM_PROMPT)

        # Kaynak bilgisini çıkar
        sources = self._extract_sources(context_chunks)

        # 7. Cache'e kaydet
        if self.cache:
            await self.cache.set(question, {"answer": answer, "sources": sources})

        return answer, sources

    # =======================================================================
    # QUERY PIPELINE (streaming — SSE için)
    # =======================================================================

    async def query_stream(
        self,
        question: str,
        session_id: str,
        doc_ids: list[str] | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Streaming soru-cevap pipeline'ı.

        Retrieval + Reranking normal çalışır (streaming olmaz).
        Sadece LLM cevap üretimi token token akar.

        NOT: Bu generator'ın son token'ı bittikten sonra kaynak bilgisi
        için extract_sources() çağrılmalı — bunu route handler yapacak.
        Alternatif olarak son event'te [SOURCES]{json} formatında
        kaynak bilgisi yield edilebilir.
        """
        # Cache kontrolü
        if self.cache:
            cached = await self.cache.get(question)
            if cached:
                # Cache hit — hazır cevabı tek parça yield et
                yield cached["answer"]
                return

        # Retrieval + parent resolution
        context_chunks = await self._retrieve_and_resolve(question, session_id, doc_ids)

        if not context_chunks:
            yield "Yüklediğiniz dokümanlarda bu sorunun cevabını bulamadım."
            return

        prompt = build_rag_prompt(question, context_chunks)

        # Streaming LLM cevabı
        full_answer = ""
        async for token in self.llm_client.stream(prompt, SYSTEM_PROMPT):
            full_answer += token
            yield token

        # Stream bittikten sonra cache'e kaydet
        sources = self._extract_sources(context_chunks)
        if self.cache:
            await self.cache.set(
                question,
                {"answer": full_answer, "sources": sources},
            )

    # =======================================================================
    # İÇ YARDIMCILAR
    # =======================================================================

    async def _retrieve_and_resolve(
        self,
        question: str,
        session_id: str,
        doc_ids: list[str] | None = None,
    ) -> list[dict]:
        """
        Soru için en alakalı EBEVEYN chunk'ları getirir.

        Adımlar:
        1. Soruyu embed et
        2. Hibrit arama → çocuk chunk'lar
        3. Reranking → en iyi çocuk chunk'lar
        4. Her çocuğun ebeveynini getir
        5. Tekrar eden ebeveynleri kaldır
           (aynı ebeveynin birden fazla çocuğu bulunmuş olabilir)
        """
        # 1. Soru embedding
        q_embedding = self.embedder.encode_query(question)

        # 2. Hibrit arama
        child_results = self.vector_store.hybrid_search(
            query_dense=q_embedding["dense"],
            query_sparse=q_embedding["sparse"],
            session_id=session_id,
            doc_ids=doc_ids,
            top_k=self.search_top_k,
        )

        if not child_results:
            return []

        # 3. Reranking
        reranked = self.reranker.rerank(
            query=question,
            documents=child_results,
            top_k=self.final_top_k,
        )

        # 4-5. Ebeveyn çözümleme + tekrarları kaldır
        parent_ids_seen = set()
        parent_chunks = []

        for child in reranked:
            parent_id = child["metadata"].get("parent_chunk_id")
            if parent_id and parent_id not in parent_ids_seen:
                parent = self.vector_store.get_parent_by_id(parent_id)
                if parent:
                    parent_chunks.append(parent)
                    parent_ids_seen.add(parent_id)

        return parent_chunks

    def _extract_sources(self, chunks: list[dict]) -> list[dict]:
        """
        Chunk listesinden kaynak bilgisi çıkarır.
        Frontend'e gönderilecek format.
        """
        sources = []
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            sources.append(
                {
                    "filename": meta.get("filename", "Bilinmeyen"),
                    "page_number": meta.get("page_number"),
                    "doc_id": meta.get("doc_id", ""),
                }
            )
        return sources
