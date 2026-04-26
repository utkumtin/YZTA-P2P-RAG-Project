from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Request

from app.services.document_service import DocumentDeleteResponse, DocumentListItem

router = APIRouter()


def _get_vector_store():
    from app.core.vector_store import VectorStore
    from app.config import get_settings
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

    items: List[DocumentListItem] = [
        DocumentListItem(
            document_id=d["doc_id"],
            filename=d["filename"],
            created_at=datetime.now(timezone.utc),
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

    try:
        vs.delete_document(doc_id=document_id, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Doküman silinemedi: {exc}")

    return DocumentDeleteResponse(document_id=document_id, deleted=True)
