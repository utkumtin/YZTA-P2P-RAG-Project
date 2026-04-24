from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json

from app.services.chat_service import ChatRequest, ChatResponse

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

    async def event_generator():
        # streaming rag buraya baglanacak
        # async for chunk in rag_service.stream(request.question):
        #     yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        words = ["ML", " pipeline", " henüz", " bağlanmadı."]
        for word in words:
            yield f"data: {json.dumps({'type': 'token', 'content': word})}\n\n"
            await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
