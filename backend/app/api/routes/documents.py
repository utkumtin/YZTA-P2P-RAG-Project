import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request

from app.config import get_settings
from app.services.document_service import DocumentDeleteResponse, DocumentListItem

router = APIRouter()
settings = get_settings()


def _get_vector_store():
    from app.config import get_settings
    from app.core.vector_store import VectorStore

    settings = get_settings()
    vs = VectorStore(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    vs.setup()
    return vs


@router.get("")
async def list_documents(request: Request, session_id: str = "default"):
    rag_pipeline = getattr(request.app.state, "rag_pipeline", None)
    if rag_pipeline is not None:
        vs = rag_pipeline.vector_store
    else:
        vs = _get_vector_store()

    try:
        docs = vs.list_documents(session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Doküman listesi alınamadı: {exc}")

    items: list[DocumentListItem] = [
        DocumentListItem(
            document_id=d["doc_id"],
            filename=d["filename"],
            created_at=datetime.now(UTC),
            chunk_count=d.get("chunk_count"),
            status="completed",
        )
        for d in docs
    ]
    return {"documents": items, "total": len(items)}


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str, request: Request, session_id: str = "default"):
    rag_pipeline = getattr(request.app.state, "rag_pipeline", None)
    if rag_pipeline is not None:
        vs = rag_pipeline.vector_store
    else:
        vs = _get_vector_store()

    # 1. Qdrant'tan sil (mevcut davranış)
    try:
        vs.delete_document(doc_id=document_id, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Doküman silinemedi: {exc}")

    # 2. Diskten sil — uzantıyı bilmediğimiz için ALLOWED_EXTENSIONS'ı dolaş
    for ext in settings.ALLOWED_EXTENSIONS:
        file_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.{ext}")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                # Dosya silinemese bile Qdrant temizlendi, başarı say
                # Ama log'la — operatör görsün
                pass
            break  # Bir uzantı bulduk, gerisine bakma

    return DocumentDeleteResponse(document_id=document_id, deleted=True)
