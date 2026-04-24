from fastapi import APIRouter, HTTPException

from app.services.summarize_service import SummarizeRequest, SummarizeResponse

router = APIRouter()


@router.post("", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="En az bir document_id gerekli.")

    #ozetleme kismi buraya baglanacak
    # summary = await summarize_service.summarize(request.document_ids, request.max_length)

    return SummarizeResponse(
        summary="ML pipeline henüz bağlanmadı.", #summary
        document_ids=request.document_ids,
    )