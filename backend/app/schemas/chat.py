from pydantic import BaseModel
from typing import Optional , List

class ChatRequest(BaseModel):
    question: str
    document_ids: Optional[List[str]] = None
    top_k: int = 4

class SourceNode(BaseModel):
    document_id: str
    filename: str
    chunk_text: str
    score: float

class ChatResponse(BaseModel):
    answer: str
    sources: List[SourceNode]
    question: str