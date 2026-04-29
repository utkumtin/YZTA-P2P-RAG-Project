from enum import Enum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    not_found = "not_found"


class TaskResponse(BaseModel):
    job_id: str
    status: TaskStatus
    filename: Optional[str] = None
    created_at: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None


class TaskProgressEvent(BaseModel):
    job_id: str
    event: str
    stage: Optional[str] = None
    message: Optional[str] = None
