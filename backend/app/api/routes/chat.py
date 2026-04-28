import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

from app.services.chat_service import ChatRequest, ChatResponse, SourceInfo

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, req: Request):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    pipeline = getattr(req.app.state, "rag_pipeline", None)
    if pipeline is None:
        return ChatResponse(
            question=request.question,
            answer="RAG pipeline hazır değil.",
            sources=[],
        )

    answer, raw_sources = await pipeline.query(
        request.question,
        request.session_id,
        request.document_ids,
    )

    sources = [
        SourceInfo(
            document_id=s.get("doc_id", ""),
            filename=s.get("filename", ""),
            chunk_text="",
        )
        for s in raw_sources
    ]

    return ChatResponse(question=request.question, answer=answer, sources=sources)


@router.post("/stream")
async def chat_stream(request: ChatRequest, req: Request):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Soru boş olamaz.")

    pipeline = getattr(req.app.state, "rag_pipeline", None)

    async def event_generator():
        if pipeline is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'RAG pipeline hazır değil.'})}\n\n"
            return

        try:
            async for item in pipeline.query_stream(
                request.question,
                request.session_id,
                request.document_ids,
            ):
                if isinstance(item, dict):
                    if "__sources__" in item:
                        yield f"data: {json.dumps({'type': 'sources', 'documents': item['__sources__']})}\n\n"
                    elif "__cache_hit__" in item:
                        yield f"data: {json.dumps({'type': 'cache_hit', 'content': item['answer']})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'token', 'content': item})}\n\n"

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            logger.error(f"Streaming chat hatası: {e}", exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
