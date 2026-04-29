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

    try:
        summary, sources = await pipeline.summarize(
            payload.document_ids,
            payload.session_id,
            payload.max_length,
        )
    except Exception as e:
        err = str(e)
        if "429" in err or "rate limit" in err.lower() or "RateLimitError" in type(e).__name__:
            raise HTTPException(
                status_code=429,
                detail="API günlük token limiti doldu. Birkaç dakika bekleyip tekrar deneyin.",
            )
        raise HTTPException(status_code=500, detail="Özet oluşturulamadı.")

    if not sources:
        raise HTTPException(status_code=404, detail="Özetlenecek içerik bulunamadı.")

    return SummarizeResponse(
        summary=summary,
        document_ids=payload.document_ids,
        sources=[SourceInfo(**s) for s in sources],
    )
