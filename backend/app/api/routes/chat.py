from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.services.chat_service import ChatRequest, ChatResponse
from app.services.sse_service import sse_stream_mock

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    # rag akisi baglanacak
    # response = await rag_service.query(request.question, request.document_ids, request.top_k)

    return ChatResponse(
        question=request.question,
        answer="ML pipeline henüz bağlanmadı.",
        sources=[],
    )


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    return StreamingResponse(
        sse_stream_mock(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
