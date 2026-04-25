from arq.connections import RedisSettings

from app.config import get_settings

settings = get_settings()


async def ingest_document(ctx, document_id: str, file_path: str):
    # RAG pipeline buraya bağlanacak
    # await rag_pipeline.process(document_id, file_path)
    pass


async def startup(ctx):
    pass


async def shutdown(ctx):
    pass


class WorkerSettings:
    functions = [ingest_document]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        database=settings.REDIS_DB,
    )
