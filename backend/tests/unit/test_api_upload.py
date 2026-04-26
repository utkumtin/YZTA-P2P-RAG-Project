from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.upload import upload_documents, validate_file


def _dosya(ad="sozlesme.pdf", icerik=b"%PDF-1.4 test"):
    f = MagicMock()
    f.filename = ad
    f.read = AsyncMock(return_value=icerik)
    return f


def _aiofiles_mock():
    dosya_mock = AsyncMock()
    dosya_mock.write = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=dosya_mock)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _http_req():
    job_mock = MagicMock()
    job_mock.job_id = "test-job-id"

    arq_mock = AsyncMock()
    arq_mock.enqueue_job = AsyncMock(return_value=job_mock)

    r = MagicMock()
    r.app.state.arq_redis = arq_mock
    return r


def test_gecersiz_uzanti_reddedilir():
    with pytest.raises(HTTPException) as exc:
        validate_file(_dosya("kotu.exe"))
    assert exc.value.status_code == 400


def test_pdf_uzantisi_kabul_edilir():
    ext = validate_file(_dosya("test.pdf"))
    assert ext == "pdf"


def test_txt_uzantisi_kabul_edilir():
    ext = validate_file(_dosya("aciklama.txt"))
    assert ext == "txt"


def test_docx_uzantisi_kabul_edilir():
    ext = validate_file(_dosya("rapor.docx"))
    assert ext == "docx"


@pytest.mark.asyncio
async def test_pdf_yukleme_queued_doner():
    with patch("aiofiles.open", return_value=_aiofiles_mock()):
        result = await upload_documents(
            request=_http_req(), files=[_dosya()], session_id="sess-001"
        )
    assert len(result) == 1
    assert result[0].status == "queued"
    assert result[0].filename == "sozlesme.pdf"
    assert result[0].job_id == "test-job-id"


@pytest.mark.asyncio
async def test_coklu_dosya_yukleme():
    dosyalar = [_dosya("a.pdf"), _dosya("b.docx"), _dosya("c.txt")]
    with patch("aiofiles.open", return_value=_aiofiles_mock()):
        result = await upload_documents(
            request=_http_req(), files=dosyalar, session_id="sess-002"
        )
    assert len(result) == 3


@pytest.mark.asyncio
async def test_her_dosyaya_benzersiz_id_atanir():
    dosyalar = [_dosya("x.pdf"), _dosya("y.pdf")]
    with patch("aiofiles.open", return_value=_aiofiles_mock()):
        result = await upload_documents(
            request=_http_req(), files=dosyalar, session_id="s"
        )
    assert result[0].document_id != result[1].document_id


@pytest.mark.asyncio
async def test_gecersiz_uzanti_http_exception_firlatir():
    with pytest.raises(HTTPException):
        await upload_documents(
            request=_http_req(), files=[_dosya("virus.sh")], session_id="s"
        )
