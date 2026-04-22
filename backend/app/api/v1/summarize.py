from fastapi import APIRouter, HTTPException

from app.schemas.summarize import SummarizeRequest, SummarizeResponse

router = APIRouter()


@router.post("", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest):
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="En az bir document_id gerekli.")

    # özetleme kismi buraya baglanacak
    # summary = await summarize_service.summarize(request.document_ids, request.max_length)

    return SummarizeResponse(
        summary="ML pipeline henüz bağlanmadı.", #summary
        document_ids=request.document_ids,
    )

