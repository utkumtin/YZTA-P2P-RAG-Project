from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.api.routes import  documents, chat, summarize ,health , upload

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

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
        except Exception:
            pass

    yield

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