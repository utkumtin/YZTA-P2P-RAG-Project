from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

import pytest

from arq.jobs import JobStatus

from app.api.routes.tasks import get_task_status
from app.models.task import TaskStatus


def _make_request(arq_redis):
    state = MagicMock()
    state.arq_redis = arq_redis
    req = MagicMock()
    req.app.state = state
    return req


def _make_arq_redis():
    arq_mock = AsyncMock()
    arq_mock.get = AsyncMock(return_value=None)
    return arq_mock


def _make_job(status: JobStatus, result=None, error=None):
    info_mock = MagicMock()
    info_mock.enqueue_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    job_mock = AsyncMock()
    job_mock.status = AsyncMock(return_value=status)
    job_mock.info = AsyncMock(return_value=info_mock)

    if error:
        job_mock.result = AsyncMock(side_effect=Exception(error))
    else:
        job_mock.result = AsyncMock(return_value=result)

    return job_mock


@pytest.mark.asyncio
async def test_task_status_pending():
    arq = _make_arq_redis()
    req = _make_request(arq)

    with patch("app.api.routes.tasks.Job", return_value=_make_job(JobStatus.queued)):
        result = await get_task_status("test-job-id", req)

    assert result.job_id == "test-job-id"
    assert result.status == TaskStatus.pending


@pytest.mark.asyncio
async def test_task_status_running():
    arq = _make_arq_redis()
    req = _make_request(arq)

    with patch("app.api.routes.tasks.Job", return_value=_make_job(JobStatus.in_progress)):
        result = await get_task_status("test-job-id", req)

    assert result.status == TaskStatus.running


@pytest.mark.asyncio
async def test_task_status_completed():
    arq = _make_arq_redis()
    req = _make_request(arq)

    with patch("app.api.routes.tasks.Job", return_value=_make_job(JobStatus.complete, result={"doc_id": "abc"})):
        result = await get_task_status("test-job-id", req)

    assert result.status == TaskStatus.completed
    assert result.result == {"doc_id": "abc"}


@pytest.mark.asyncio
async def test_task_status_not_found():
    from fastapi import HTTPException
    arq = _make_arq_redis()
    req = _make_request(arq)

    with patch("app.api.routes.tasks.Job", return_value=_make_job(JobStatus.not_found)):
        with pytest.raises(HTTPException) as exc_info:
            await get_task_status("nonexistent-job", req)

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_task_status_failed():
    arq = _make_arq_redis()
    req = _make_request(arq)

    with patch("app.api.routes.tasks.Job", return_value=_make_job(JobStatus.complete, error="Pipeline error")):
        result = await get_task_status("failed-job", req)

    assert result.status == TaskStatus.failed
    assert "Pipeline error" in result.error


@pytest.mark.asyncio
async def test_task_status_no_queue():
    from fastapi import HTTPException
    req = _make_request(None)

    with pytest.raises(HTTPException) as exc_info:
        await get_task_status("any-job", req)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_task_status_deferred_returns_pending():
    """Ertelenmiş (deferred) job → 'pending' status döndürmeli."""
    arq = _make_arq_redis()
    req = _make_request(arq)

    with patch("app.api.routes.tasks.Job", return_value=_make_job(JobStatus.deferred)):
        result = await get_task_status("deferred-job", req)

    assert result.status == TaskStatus.pending


@pytest.mark.asyncio
async def test_task_status_response_echoes_job_id():
    """Response her zaman gönderilen job_id değerini içermeli."""
    arq = _make_arq_redis()
    req = _make_request(arq)
    test_job_id = "unique-job-xyz-789"

    with patch("app.api.routes.tasks.Job", return_value=_make_job(JobStatus.queued)):
        result = await get_task_status(test_job_id, req)

    assert result.job_id == test_job_id


@pytest.mark.asyncio
async def test_upload_response_includes_job_id(mock_arq_redis):
    """Upload sonrası her dosya için job_id alanı döndürülmeli."""
    from app.api.routes.upload import upload_documents

    def _dosya(ad="test.pdf"):
        f = MagicMock()
        f.filename = ad
        f.read = AsyncMock(return_value=b"%PDF-1.4 test")
        return f

    def _aiofiles_mock():
        m = AsyncMock()
        m.write = AsyncMock()
        cm = AsyncMock()
        cm.__aenter__ = AsyncMock(return_value=m)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    req = MagicMock()
    req.app.state.arq_redis = mock_arq_redis

    with patch("aiofiles.open", return_value=_aiofiles_mock()):
        result = await upload_documents(req, files=[_dosya()], session_id="sess-001")

    assert len(result) == 1
    assert hasattr(result[0], "job_id")
    assert result[0].job_id == "job-enqueue-001"
    assert result[0].status == "queued"
