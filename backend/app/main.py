from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.config import get_settings
from app.api.routes import  documents, chat, summarize  #,health

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#app.include_router(health.router, prefix="/api/v1/health", tags=["health"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(chat.router, prefix="/api/v1/chat", tags=["chat"])
app.include_router(summarize.router, prefix="/api/v1/summarize", tags=["summarize"])