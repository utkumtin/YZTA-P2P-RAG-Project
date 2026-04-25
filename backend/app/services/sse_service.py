import asyncio
import json
from typing import AsyncGenerator

async def sse_stream_mock() -> AsyncGenerator[str, None]:
    words = ["ML", " pipeline", " henüz", " bağlanmadı."]
    for word in words:
        yield f"data: {json.dumps({'type': 'token', 'content': word})}\n\n"
        await asyncio.sleep(0.05)
    yield f"data: {json.dumps({'type': 'done'})}\n\n"


async def sse_stream(token_generator) -> AsyncGenerator[str, None]:
    # rag ağlaninca burası kullanılacak
    async for chunk in token_generator:
        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
