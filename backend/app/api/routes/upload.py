from fastapi import APIRouter, HTTPException , UploadFile, File,Request,Depends
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
MAX_FILE_SIZE_BYTES = settings.MAX_FILE_SIZE_MB * 1024 * 1024
CHUNK_SIZE = 1024 * 1024  # 1 MB'lık parçalar (Streaming için)

async def get_redis_pool(request: Request): #dependency injection
    return request.app.state.redis_pool

def validate_file(file: UploadFile):
    ext = file.filename.split(".")[-1].lower()
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen format: .{ext}. İzin verilenler: {ALLOWED}"
        )

    if file.size and file.size > MAX_FILE_SIZE_BYTES: #boyut kontrolü
        raise HTTPException(
            status_code=413,  # 413: Payload Too Large
            detail=f"Dosya boyutu çok büyük. Maksimum {settings.MAX_FILE_SIZE_MB}MB yüklenebilir."
        )
    return ext


@router.post("", response_model=List[DocumentUploadResponse])
async def upload_documents( files: List[UploadFile] = File(...),
    session_id: str = "default",
    redis_pool = Depends(get_redis_pool)):
    responses = []


    for file in files:
        ext = validate_file(file)
        document_id = str(uuid.uuid4())
        save_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.{ext}")

        try:
            async with aiofiles.open(save_path, "wb") as f:
                while chunk := await file.read(CHUNK_SIZE):
                    await f.write(chunk)


            await redis_pool.enqueue_job('ingest_document', document_id, save_path, session_id)

        except Exception as e:
            #orphan file cleanup
            if os.path.exists(save_path):
                os.remove(save_path)

            raise HTTPException(
                status_code=500,
                detail=f"Dosya işlenirken hata oluştu ve temizlendi: {str(e)}"
            )

        responses.append(DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="queued",
            message="Dosya alındı, işleme kuyruğa alındı.",
        ))

    return responses
