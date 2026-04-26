from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    document_ids: list[str]
    session_id: str = "default"
    max_length: int = 500


class SourceInfo(BaseModel):
    filename: str
    page_number: int | None = None
    doc_id: str


class SummarizeResponse(BaseModel):
    summary: str
    document_ids: list[str]
    sources: list[SourceInfo] = Field(default_factory=list)
