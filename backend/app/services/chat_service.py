from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    question: str
    session_id: str
    document_ids: Optional[List[str]] = None


class SourceInfo(BaseModel):
    document_id: str
    filename: str
    chunk_text: str


class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    question: str