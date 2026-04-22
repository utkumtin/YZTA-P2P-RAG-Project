from fastapi import APIRouter
from app.api.v1 import health, documents, chat, summarize

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(summarize.router, prefix="/summarize", tags=["summarize"])

