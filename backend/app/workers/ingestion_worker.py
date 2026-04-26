import json
import logging
import os

from arq.connections import RedisSettings

from app.config import get_settings
from app.core.embedder import get_embedder
from app.core.llm_client import create_llm_client
from app.core.rag_pipeline import RAGPipeline
from app.core.reranker import Reranker
from app.core.vector_store import VectorStore

settings = get_settings()
logger = logging.getLogger(__name__)


async def ingest_document(ctx: dict, document_id: str, file_path: str) -> dict:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    job_id: str = ctx["job_id"]
    redis = ctx["redis"]
    pipeline: RAGPipeline = ctx["rag_pipeline"]

    async def _write_progress(stage: str, pct: int, event: str = "progress") -> None:
        await redis.set(
            f"progress:{job_id}",
            json.dumps({"stage": stage, "pct": pct, "event": event}),
            ex=3600,
        )

    try:
        await _write_progress("parsing", 10)
        await _write_progress("embedding", 40)
        result = await pipeline.ingest_document(
            file_path=file_path,
            doc_id=document_id,
            session_id="default",
        )
        await _write_progress("indexing", 80)
        await _write_progress("done", 100, event="done")
        logger.info("Document %s ingested: %s", document_id, result)
        return result
    except Exception:
        logger.exception("Failed to ingest document %s", document_id)
        await redis.set(
            f"progress:{job_id}",
            json.dumps({"stage": "failed", "pct": 0, "event": "error", "message": "Ingestion failed"}),
            ex=3600,
        )
        raise


async def startup(ctx: dict) -> None:
    await ctx["redis"].ping()
    logger.info("Redis connection OK")

    embedder = get_embedder()
    vector_store = VectorStore(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    vector_store.setup()
    reranker = Reranker(model_name=settings.RERANKER_MODEL)

    api_key = settings.GROQ_API_KEY if settings.LLM_PROVIDER == "groq" else settings.GOOGLE_API_KEY
    llm_client = create_llm_client(provider=settings.LLM_PROVIDER, api_key=api_key)

    pipeline = RAGPipeline(
        embedder=embedder,
        vector_store=vector_store,
        reranker=reranker,
        llm_client=llm_client,
        search_top_k=settings.HYBRID_SEARCH_TOP_K,
        final_top_k=settings.FINAL_TOP_K,
    )
    ctx["rag_pipeline"] = pipeline
    logger.info("RAG pipeline initialized")


async def shutdown(ctx: dict) -> None:
    logger.info("Worker shutting down")


class WorkerSettings:
    functions = [ingest_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )
    job_timeout = 300
    max_tries = 3
