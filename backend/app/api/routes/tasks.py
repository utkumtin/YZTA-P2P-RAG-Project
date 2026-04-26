import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from arq.jobs import Job, JobStatus

from app.models.task import TaskResponse, TaskStatus

router = APIRouter()

_ARQ_TO_TASK_STATUS = {
    JobStatus.queued: TaskStatus.pending,
    JobStatus.in_progress: TaskStatus.running,
    JobStatus.complete: TaskStatus.completed,
    JobStatus.not_found: TaskStatus.not_found,
    JobStatus.deferred: TaskStatus.pending,
}


@router.get("/{job_id}", response_model=TaskResponse)
async def get_task_status(job_id: str, request: Request):
    arq_redis = getattr(request.app.state, "arq_redis", None)
    if arq_redis is None:
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    job = Job(job_id, redis=arq_redis)
    arq_status = await job.status()

    if arq_status == JobStatus.not_found:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    task_status = _ARQ_TO_TASK_STATUS.get(arq_status, TaskStatus.pending)
    result = None
    error = None
    created_at = None

    info = await job.info()
    if info:
        created_at = info.enqueue_time

    if arq_status == JobStatus.complete:
        try:
            result = await job.result(timeout=0)
        except Exception as exc:
            task_status = TaskStatus.failed
            error = str(exc)

    return TaskResponse(
        job_id=job_id,
        status=task_status,
        created_at=created_at,
        result=result,
        error=error,
    )


@router.get("/{job_id}/progress")
async def get_task_progress(job_id: str, request: Request):
    arq_redis = getattr(request.app.state, "arq_redis", None)
    if arq_redis is None:
        raise HTTPException(status_code=503, detail="Task queue unavailable")

    async def event_stream():
        while True:
            raw = await arq_redis.get(f"progress:{job_id}")
            if raw:
                data = json.loads(raw)
                event_type = data.get("event", "progress")

                if event_type == "done":
                    yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
                    return
                elif event_type == "error":
                    yield f"event: error\ndata: {json.dumps({'message': data.get('message', '')})}\n\n"
                    return
                else:
                    stage = data.get("stage", "")
                    pct = data.get("pct", 0)
                    yield f"event: progress\ndata: {json.dumps({'stage': stage, 'pct': pct})}\n\n"

            job = Job(job_id, redis=arq_redis)
            arq_status = await job.status()
            if arq_status == JobStatus.complete:
                yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"
                return
            if arq_status == JobStatus.not_found:
                yield f"event: error\ndata: {json.dumps({'message': 'Job not found'})}\n\n"
                return

            await asyncio.sleep(1)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
