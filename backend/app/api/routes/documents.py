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


def _find_disk_path(document_id: str) -> str | None:
    for ext in settings.ALLOWED_EXTENSIONS:
        candidate = os.path.join(settings.UPLOAD_DIR, f"{document_id}.{ext}")
        if os.path.exists(candidate):
            return candidate
    return None


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
    vs = rag_pipeline.vector_store if rag_pipeline is not None else _get_vector_store()
    arq_redis = getattr(request.app.state, "arq_redis", None)

    # Disk path'i silmeden önce belirle (rollback için referans)
    disk_path = _find_disk_path(document_id)

    # 1. Qdrant'tan sil — başarısız olursa hiçbir şeye dokunma
    try:
        vs.delete_document(doc_id=document_id, session_id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Vektör silme başarısız: {exc}")

    # Qdrant temizlendi. Kalan cleanup'lar best-effort; hataları topla.
    cleanup_errors: list[str] = []

    # 2. Diskten sil
    if disk_path:
        try:
            os.remove(disk_path)
        except OSError as exc:
            cleanup_errors.append(f"disk ({disk_path}): {exc}")

    # 3. Redis cleanup: progress key + doc→job mapping
    if arq_redis:
        try:
            job_id_raw = await arq_redis.get(f"doc:{document_id}:job_id")
            if job_id_raw:
                job_id = job_id_raw.decode() if isinstance(job_id_raw, bytes) else job_id_raw
                await arq_redis.delete(f"progress:{job_id}")
            await arq_redis.delete(f"doc:{document_id}:job_id")
        except Exception as exc:
            cleanup_errors.append(f"redis: {exc}")

    if cleanup_errors:
        # Vektörler silindi ama ikincil kaynaklar temizlenemedi — 207 yerine 500 ile bildir
        raise HTTPException(
            status_code=500,
            detail=(
                f"Doküman vektörleri silindi ancak tam temizlik başarısız: "
                + "; ".join(cleanup_errors)
            ),
        )

    return DocumentDeleteResponse(document_id=document_id, deleted=True)
