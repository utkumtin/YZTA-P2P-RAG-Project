from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.routes.upload import upload_documents, validate_file, sanitize_filename


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


# Sanitize Filename Tests
def test_sanitize_filename_basic():
    assert sanitize_filename("test.pdf") == "test.pdf"

def test_sanitize_filename_path_segment():
    assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("C:\\Windows\\system32\\cmd.exe.pdf") == "cmd.exe.pdf"

def test_sanitize_filename_unicode():
    assert sanitize_filename("📊_Türkçe_Dosya_Adı ğüşiöç.pdf") == "📊_Türkçe_Dosya_Adı ğüşiöç.pdf"

def test_sanitize_filename_control_chars():
    assert sanitize_filename("file\x00name\n\r.pdf") == "filename.pdf"

def test_sanitize_filename_truncate():
    long_name = "a" * 300 + ".pdf"
    sanitized = sanitize_filename(long_name)
    assert len(sanitized) == 255
    assert sanitized.endswith(".pdf")
    assert sanitized.startswith("a" * 251)

def test_sanitize_filename_invalid():
    with pytest.raises(HTTPException) as exc:
        sanitize_filename("")
    assert exc.value.status_code == 400
    
    with pytest.raises(HTTPException):
        sanitize_filename(None)
        
    with pytest.raises(HTTPException):
        sanitize_filename(".pdf")
        
    with pytest.raises(HTTPException):
        sanitize_filename("   .pdf")
        
    with pytest.raises(HTTPException):
        sanitize_filename("file.")

def test_sanitize_filename_dotfile():
    assert sanitize_filename(".hidden.pdf") == ".hidden.pdf"


def test_gecersiz_uzanti_reddedilir():
    with pytest.raises(HTTPException) as exc:
        validate_file("kotu.exe")
    assert exc.value.status_code == 400


def test_pdf_uzantisi_kabul_edilir():
    ext = validate_file("test.pdf")
    assert ext == "pdf"


def test_txt_uzantisi_kabul_edilir():
    ext = validate_file("aciklama.txt")
    assert ext == "txt"


def test_docx_uzantisi_kabul_edilir():
    ext = validate_file("rapor.docx")
    assert ext == "docx"


@pytest.mark.asyncio
async def test_pdf_yukleme_queued_doner():
    req = _http_req()
    with patch("app.api.routes.upload.uuid.uuid4", return_value="1234-abcd"):
        with patch("aiofiles.open", return_value=_aiofiles_mock()):
            result = await upload_documents(
                request=req, files=[_dosya()], session_id="sess-001"
            )
    assert len(result) == 1
    assert result[0].status == "queued"
    assert result[0].filename == "sozlesme.pdf"
    assert result[0].job_id == "test-job-id"
    req.app.state.arq_redis.enqueue_job.assert_called_once()
    args = req.app.state.arq_redis.enqueue_job.call_args[0]
    assert args[0] == "ingest_document"
    assert args[1] == "1234-abcd"
    assert "1234-abcd.pdf" in args[2]  # save_path
    assert args[3] == "sozlesme.pdf"  # sanitized_filename


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
