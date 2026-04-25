from pydantic import BaseModel
from typing import Optional, List

from app.services.chat_service import SourceInfo

class SummarizeRequest(BaseModel):
    document_ids: List[str]
    max_length: Optional[int] = 500


class SummarizeResponse(BaseModel):
    summary: str
    document_ids: List[str]
    sources: List[SourceInfo]
