"""
RAG Pipeline Orkestratörü.
Tüm bileşenleri birleştirir: arama, reranking, ebeveyn çözümleme, LLM.

İki ana akış:
1. Ingestion: Dosya yükle → metin çıkar → temizle → parçala → embed → indeksle
2. Query: Soru soruldu → cache kontrol → ara → rerank → parent chunk'ları getir → LLM
"""

from collections.abc import AsyncGenerator

from langfuse import Langfuse

from app.config import get_settings
from app.core.chunker import create_parent_child_chunks
from app.core.document_processor import DocumentProcessor
from app.core.embedder import Embedder
from app.core.llm_client import (
    SUMMARY_SYSTEM_PROMPT,
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

        settings = get_settings()
        self.langfuse = None
        if settings.LANGFUSE_PUBLIC_KEY and settings.LANGFUSE_SECRET_KEY:
            self.langfuse = Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST
            )

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
        trace = None
        if self.langfuse:
            trace = self.langfuse.trace(
                name="rag-query",
                session_id=session_id,
                input={"question": question, "doc_ids": doc_ids}
            )

        if self.cache:
            cached = await self.cache.get(question)
            if cached:
                if trace:
                    trace.update(tags=["cache-hit"])
                    trace.end(output=cached["answer"])
                return cached["answer"], cached["sources"]

        # 2-5. Retrieval + Reranking + Parent resolution
        context_chunks = await self._retrieve_and_resolve(question, session_id, doc_ids, trace)

        # Hiç alakalı chunk bulunamadıysa
        if not context_chunks:
            ans = "Yüklediğiniz dokümanlarda bu sorunun cevabını bulamadım."
            if trace:
                trace.end(output=ans)
            return (ans, [])

        # 6. LLM cevap üretimi
        prompt = build_rag_prompt(question, context_chunks)

        generation = None
        if trace:
            generation = trace.generation(
                name="llm-generation",
                model=getattr(self.llm_client, "model_name", "unknown"),
                prompt=prompt,
            )

        answer = await self.llm_client.generate(prompt, SYSTEM_PROMPT)

        if generation:
            generation.end(output=answer)

        # Kaynak bilgisini çıkar
        sources = self._extract_sources(context_chunks)

        # 7. Cache'e kaydet
        if self.cache:
            await self.cache.set(question, {"answer": answer, "sources": sources})

        if trace:
            trace.end(output=answer)

        return answer, sources

    # =======================================================================
    # QUERY PIPELINE (streaming — SSE için)
    # =======================================================================

    async def query_stream(
        self,
        question: str,
        session_id: str,
        doc_ids: list[str] | None = None,
    ) -> AsyncGenerator[str]:
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
        trace = None
        if self.langfuse:
            trace = self.langfuse.trace(
                name="rag-query-stream",
                session_id=session_id,
                input={"question": question, "doc_ids": doc_ids}
            )

        if self.cache:
            cached = await self.cache.get(question)
            if cached:
                # Cache hit — hazır cevabı tek parça yield et
                if trace:
                    trace.update(tags=["cache-hit"])
                    trace.end(output=cached["answer"])
                yield cached["answer"]
                return

        # Retrieval + parent resolution
        context_chunks = await self._retrieve_and_resolve(question, session_id, doc_ids, trace)

        if not context_chunks:
            ans = "Yüklediğiniz dokümanlarda bu sorunun cevabını bulamadım."
            if trace:
                trace.end(output=ans)
            yield ans
            return

        prompt = build_rag_prompt(question, context_chunks)

        generation = None
        if trace:
            generation = trace.generation(
                name="llm-generation-stream",
                model=getattr(self.llm_client, "model_name", "unknown"),
                prompt=prompt,
            )

        # Streaming LLM cevabı
        full_answer = ""
        async for token in self.llm_client.stream(prompt, SYSTEM_PROMPT):
            full_answer += token
            yield token

        if generation:
            generation.end(output=full_answer)

        # Stream bittikten sonra cache'e kaydet
        sources = self._extract_sources(context_chunks)
        if self.cache:
            await self.cache.set(
                question,
                {"answer": full_answer, "sources": sources},
            )

        if trace:
            trace.end(output=full_answer)

    # =======================================================================
    # İÇ YARDIMCILAR
    # =======================================================================

    async def _retrieve_and_resolve(
        self,
        question: str,
        session_id: str,
        doc_ids: list[str] | None = None,
        trace = None,
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
        retrieval_span = None
        if trace:
            retrieval_span = trace.span(
                name="vector-search",
                input={"question": question, "doc_ids": doc_ids}
            )

        child_results = self.vector_store.hybrid_search(
            query_dense=q_embedding["dense"],
            query_sparse=q_embedding["sparse"],
            session_id=session_id,
            doc_ids=doc_ids,
            top_k=self.search_top_k,
        )

        if retrieval_span:
            retrieval_span.end(output={"retrieved_count": len(child_results)})

        if not child_results:
            return []

        # 3. Reranking
        rerank_span = None
        if trace:
            rerank_span = trace.span(
                name="reranking",
                input={"documents_count": len(child_results)}
            )

        reranked = self.reranker.rerank(
            query=question,
            documents=child_results,
            top_k=self.final_top_k,
        )

        if rerank_span:
            rerank_span.end(output={"reranked_count": len(reranked)})

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

    # =======================================================================
    # SUMMARIZATION PIPELINE (Map-Reduce)
    # =======================================================================

    async def summarize(
        self,
        doc_ids: list[str],
        session_id: str,
    ) -> tuple[str, list[dict]]:
        """
        Seçili dokümanların özetini çıkarır (Map-Reduce stratejisi).

        Map: Her parent chunk için mini-özet üret (ayrı LLM çağrısı).
        Reduce: Tüm mini-özetleri birleştirip nihai özet üret.

        Özel durum: Tek parent chunk varsa Reduce aşaması atlanır;
        mini-özetin kendisi nihai özet olarak döndürülür.

        Args:
            doc_ids: Özetlenecek doküman ID'leri
            session_id: Kullanıcı oturum kimliği

        Returns:
            (özet_metni, kaynak_listesi)
            kaynak_listesi: [{"filename": str, "page_number": int|None, "doc_id": str}, ...]
        """
        # Tüm dokümanlar için parent chunk'ları topla.
        # VectorStore encapsulation'ına uygun — client'a doğrudan erişmiyoruz.
        all_parents: list[dict] = []
        for doc_id in doc_ids:
            parents = self.vector_store.get_parents_by_doc_id(doc_id, session_id)
            all_parents.extend(parents)

        if not all_parents:
            return "Özetlenecek içerik bulunamadı.", []

        # MAP: Her parent chunk için ayrı mini-özet.
        # LLM çağrıları sıralı yapılıyor; paralel yapılsa hızlanır ama
        # Groq rate limit (6000 RPM / 280 TPS) aşılabilir.
        map_template = "Aşağıdaki metin parçasının kısa bir özetini çıkar:\n\n{text}"
        mini_summaries: list[str] = []
        for parent in all_parents:
            prompt = map_template.format(text=parent["text"])
            mini = await self.llm_client.generate(prompt, SUMMARY_SYSTEM_PROMPT)
            mini_summaries.append(mini)

        # Tek chunk varsa Reduce gereksiz — mini-özet zaten nihai özet.
        if len(mini_summaries) == 1:
            sources = self._extract_sources(all_parents)
            return mini_summaries[0], sources

        # REDUCE: Mini-özetleri birleştir, tutarlı bir nihai özet üret.
        combined = "\n\n---\n\n".join(mini_summaries)
        reduce_prompt = (
            "Aşağıda bir dokümanın farklı bölümlerinin özetleri verilmiştir.\n"
            "Bu özetleri birleştirerek kapsamlı, tutarlı ve akıcı bir nihai özet oluştur.\n\n"
            f"{combined}\n\nNİHAİ ÖZET:"
        )
        final_summary = await self.llm_client.generate(reduce_prompt, SUMMARY_SYSTEM_PROMPT)

        # İlk 5 kaynak frontend'e yeterli; tüm liste çok gürültülü olur.
        sources = self._extract_sources(all_parents[:5])
        return final_summary, sources
