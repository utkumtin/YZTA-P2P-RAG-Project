from fastapi import APIRouter, HTTPException, Request

from app.services.summarize_service import SourceInfo, SummarizeRequest, SummarizeResponse

router = APIRouter()


@router.post("", response_model=SummarizeResponse)
async def summarize(payload: SummarizeRequest, request: Request):
    if not payload.document_ids:
        raise HTTPException(status_code=400, detail="En az bir document_id gerekli.")

    pipeline = getattr(request.app.state, "rag_pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline hazır değil.")

    summary, sources = await pipeline.summarize(
        payload.document_ids,
        payload.session_id,
        payload.max_length,
    )

    if not sources:
        raise HTTPException(status_code=404, detail="Özetlenecek içerik bulunamadı.")

    return SummarizeResponse(
        summary=summary,
        document_ids=payload.document_ids,
        sources=[SourceInfo(**s) for s in sources],
    )
