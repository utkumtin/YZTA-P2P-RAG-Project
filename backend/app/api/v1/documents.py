from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
import uuid
import os
import shutil

from app.config import get_settings
from app.schemas.document import DocumentUploadResponse, DocumentDeleteResponse

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

@router.post("/upload", response_model=List[DocumentUploadResponse])
async def upload_documents(files: List[UploadFile] = File(...)):
    responses = []

    for file in files:
        ext = validate_file(file)
        document_id = str(uuid.uuid4())
        save_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.{ext}")

        try:
            with open(save_path, "wb") as f:
                shutil.copyfileobj(file.file, f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Dosya kaydedilemedi: {str(e)}")

        #pipeline buraya baglanacak
        # await rag_pipeline.process(document_id, save_path)

        responses.append(DocumentUploadResponse(
            document_id=document_id,
            filename=file.filename,
            status="queued",
            message="Dosya alındı, işleme kuyruğa alındı.",
        ))

    return responses

@router.get("")
async def list_documents():
    #qdrant bağlanınca burası yazilacak
    return {"documents": [], "total": 0}

@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str):
    # qdrant bağlanınca burası yazilacak
    return DocumentDeleteResponse(document_id=document_id, deleted=True)


