from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os

import logging

from arq.connections import create_pool, RedisSettings

from app.config import get_settings
from app.api.routes import documents, chat, summarize, health, upload, tasks
from app.core.embedder import get_embedder
from app.core.llm_client import create_llm_client
from app.core.rag_pipeline import RAGPipeline
from app.core.reranker import Reranker
from app.core.vector_store import VectorStore

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.environ.setdefault("HF_HOME", settings.HF_HOME)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    os.makedirs(settings.HF_HOME, exist_ok=True)

    arq_redis = await create_pool(
        RedisSettings(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            database=settings.REDIS_DB,
        )
    )
    app.state.arq_redis = arq_redis

    app.state.semantic_cache = None
    if settings.SEMANTIC_CACHE_ENABLED:
        try:
            import redis.asyncio as aioredis
            from app.core.embedder import get_embedder
            from app.core.semantic_cache import SemanticCache

            redis_client = aioredis.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
            )
            embedder = get_embedder()
            sc = SemanticCache(
                redis_client=redis_client,
                embedder=embedder,
                threshold=settings.SEMANTIC_CACHE_THRESHOLD,
                ttl=settings.SEMANTIC_CACHE_TTL,
                max_size=settings.SEMANTIC_CACHE_MAX_SIZE,
            )
            await sc.load_from_redis()
            app.state.semantic_cache = sc
            app.state.redis_client = redis_client
        except Exception as cache_err:
            logging.getLogger(__name__).warning(f"Semantic cache başlatılamadı: {cache_err}")

    app.state.rag_pipeline = None
    try:
        embedder = get_embedder()
        vector_store = VectorStore(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )
        vector_store.setup()
        reranker = Reranker(model_name=settings.RERANKER_MODEL)
        api_key = (
            settings.GROQ_API_KEY
            if settings.LLM_PROVIDER == "groq"
            else settings.GOOGLE_API_KEY
        )
        llm_client = create_llm_client(settings.LLM_PROVIDER, api_key)
        app.state.rag_pipeline = RAGPipeline(
            embedder=embedder,
            vector_store=vector_store,
            reranker=reranker,
            llm_client=llm_client,
            cache=app.state.semantic_cache,
            search_top_k=settings.HYBRID_SEARCH_TOP_K,
            final_top_k=settings.FINAL_TOP_K,
        )
    except Exception as e:
        logging.getLogger(__name__).warning(f"RAG pipeline başlatılamadı: {e}")

    yield

    if hasattr(app.state, "arq_redis") and app.state.arq_redis is not None:
        try:
            await app.state.arq_redis.aclose()
        except Exception:
            pass

    if hasattr(app.state, "redis_client") and app.state.redis_client is not None:
        try:
            await app.state.redis_client.aclose()
        except Exception:
            pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

_MAX_BODY_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024 * 10  # 10x max file size as request ceiling


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > _MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "İstek gövdesi çok büyük."})
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router,    prefix="/api/routes/health",    tags=["health"])
app.include_router(documents.router, prefix="/api/routes/documents", tags=["documents"])
app.include_router(upload.router,    prefix="/api/routes/upload",    tags=["upload"])
app.include_router(chat.router,      prefix="/api/routes/chat",      tags=["chat"])
app.include_router(summarize.router, prefix="/api/routes/summarize", tags=["summarize"])
app.include_router(tasks.router,     prefix="/api/routes/tasks",     tags=["tasks"])
