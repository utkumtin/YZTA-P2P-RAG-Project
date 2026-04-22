from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import asyncio
import json

from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    # rag akışı buraya baglanacak
    # response = await rag_service.query(request.question, request.document_ids, request.top_k)

    return ChatResponse(
        question=request.question,
        answer="ML pipeline henüz bağlanmadı.", #response.answer,
        sources=[], #response.sources,
    )

@router.post("/stream")
async def chat_stream(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    async def event_generator():
        # streaming rag buraya baglanacak
        # async for chunk in rag_service.stream(request.question):
        #     yield f"data: {json.dumps({'chunk': chunk})}\n\n"

        words = ["ML", " pipeline", " henüz", " bağlanmadı."]
        for word in words: #buralar silinecek
            yield f"data: {json.dumps({'chunk': word})}\n\n"
            await asyncio.sleep(0.05)
        yield "data: [DONE]\n\n"  #bu kalacak

    return StreamingResponse(event_generator(), media_type="text/event-stream")

