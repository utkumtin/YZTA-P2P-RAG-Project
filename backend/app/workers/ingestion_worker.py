import logging
from arq.connections import RedisSettings
from app.config import get_settings

#loglama ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


async def process_document_task(ctx, document_id: str, file_path: str):
    logger.info(f" ----- GÖREV BAŞLADI: {document_id} -----")

    # Burada dosya yolunu (file_path) kullanarak ML pipeline tetiklenecek
    # await document_service.process_and_vectorize(file_path)

    logger.info(f"Döküman işleniyor: {file_path}")

    logger.info(f"----- GÖREV TAMAMLANDI: {document_id} -----")
    return True

class WorkerSettings:
    functions = [process_document_task]
    redis_settings = RedisSettings(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT
    )
