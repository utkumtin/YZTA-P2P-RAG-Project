from fastapi import APIRouter, HTTPException , UploadFile, File
from typing import List
import uuid
import os
import aiofiles

from arq import create_pool
from arq.connections import RedisSettings

from app.config import get_settings
from app.services.document_service import DocumentUploadResponse

router = APIRouter()
settings = get_settings()

ALLOWED = set(settings.ALLOWED_EXTENSIONS)


def validate_file(file: UploadFile):
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen format: .{ext}. İzin verilenler: {ALLOWED}"
        )
    return ext


@router.post("", response_model=List[DocumentUploadResponse])
async def upload_documents( files: List[UploadFile] = File(...),
    session_id: str = "default"):
    responses = []

    #redis baglanti havuzu
    redis_pool = await create_pool(
        RedisSettings(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            database=settings.REDIS_DB
        )
    )

    for file in files:
        ext = validate_file(file)
        document_id = str(uuid.uuid4())
        save_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.{ext}")

        try:
            contents = await file.read()
            async with aiofiles.open(save_path, "wb") as f:
                await f.write(contents)

            #arq workera görev gönderildi
            await redis_pool.enqueue_job('ingest_document', document_id, save_path, session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Sistem Hatası: {str(e)}")

        responses.append(DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="queued",
            message="Dosya alındı, işleme kuyruğa alındı.",
        ))

    return responses
