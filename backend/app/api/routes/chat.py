from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
import asyncio
import json

from app.services.chat_service import ChatRequest, ChatResponse

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    sc = getattr(req.app.state, "semantic_cache", None)
    if sc is not None:
        cached = await sc.get(request.question)
        if cached is not None:
            return ChatResponse(**cached)

    # rag akisi baglanacak
    # response = await rag_service.query(request.question, request.document_ids)

    response = ChatResponse(
        question=request.question,
        answer="ML pipeline henüz bağlanmadı.",
        sources=[],
    )

    if sc is not None:
        await sc.set(request.question, response.model_dump())

    return response


@router.post("/stream")
async def chat_stream(request: ChatRequest, req: Request):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    sc = getattr(req.app.state, "semantic_cache", None)
    cached_answer = None
    if sc is not None:
        cached = await sc.get(request.question)
        if cached is not None:
            cached_answer = cached.get("answer", "")

    async def event_generator():
        if cached_answer is not None:
            words = cached_answer.split(" ")
            for word in words:
                yield f"data: {json.dumps({'type': 'token', 'content': word + ' '})}\n\n"
                await asyncio.sleep(0.02)
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # streaming rag buraya baglanacak
        # async for chunk in rag_service.stream(request.question):
        #     yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        words = ["ML", " pipeline", " henüz", " bağlanmadı."]
        full_answer = "".join(words)
        for word in words:
            yield f"data: {json.dumps({'type': 'token', 'content': word})}\n\n"
            await asyncio.sleep(0.05)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

        if sc is not None:
            response_data = ChatResponse(
                question=request.question,
                answer=full_answer,
                sources=[],
            ).model_dump()
            await sc.set(request.question, response_data)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
