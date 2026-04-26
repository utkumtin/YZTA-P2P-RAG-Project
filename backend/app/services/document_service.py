from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class DocumentUploadResponse(BaseModel):
    job_id: str
    document_id: str
    filename: str
    status: str
    message: str


class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    created_at: datetime
    chunk_count: Optional[int] = None
    status: str


class DocumentDeleteResponse(BaseModel):
    document_id: str
    deleted: bool