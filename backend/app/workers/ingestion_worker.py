import logging
from arq.connections import RedisSettings
from app.config import get_settings

from app.core.rag_pipeline import RAGPipeline
from app.core.embedder import Embedder
from app.core.vector_store import VectorStore
from app.core.reranker import Reranker

from app.core.llm_client import create_llm_client
from app.core.semantic_cache import SemanticCache

settings = get_settings()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")

# Sağlayıcıya göre uygun API anahtarını seçiyoruz
api_key = settings.GROQ_API_KEY if settings.LLM_PROVIDER.lower() == "groq" else settings.GOOGLE_API_KEY

pipeline = RAGPipeline(
    embedder=Embedder(),
    vector_store=VectorStore(),
    reranker=Reranker(),
    llm_client=create_llm_client(
        provider=settings.LLM_PROVIDER,
        api_key=api_key
    ),
    cache=SemanticCache()
)

async def ingest_document(ctx, document_id: str, file_path: str , session_id: str = "default"):
    """Dosyayı RAG pipeline'ı üzerinden işleyen worker görevi."""
    logger.info(f"[BAŞLADI] Doküman işleniyor: ID={document_id}, Yol={file_path}")
    try:
        # rag_pipeline.py içindeki ana fonksiyonu çağırıyoruz
        result = await pipeline.ingest_document(
            file_path=file_path,
            doc_id=document_id,
            session_id=session_id
        )

        logger.info(f"[TAMAMLANDI] Doküman başarıyla indekslendi: {result}")
        return result
    except Exception as e:
        logger.error(f"[HATA] Pipeline işleme sırasında hata: {str(e)}")
        raise e


async def startup(ctx):
    logger.info("Worker görevleri dinlemeye başladı.")


async def shutdown(ctx):
    logger.info("Worker kapatılıyor.")


class WorkerSettings:
    functions = [ingest_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )
