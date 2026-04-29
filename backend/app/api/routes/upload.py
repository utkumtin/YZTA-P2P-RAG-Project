import os
import unicodedata
import uuid

import aiofiles
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.config import get_settings
from app.services.document_service import DocumentUploadResponse

router = APIRouter()
settings = get_settings()

ALLOWED = set(settings.ALLOWED_EXTENSIONS)

# Magic bytes for each supported extension; None = skip magic check (plain text)
_MAGIC: dict[str, tuple[bytes, ...] | None] = {
    "pdf": (b"\x25\x50\x44\x46",),
    "docx": (b"\x50\x4B\x03\x04",),
    "doc": (b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1",),
    "txt": None,
}


def sanitize_filename(raw_name: str | None) -> str:
    if not raw_name or not str(raw_name).strip():
        raise HTTPException(status_code=400, detail="Dosya adı boş olamaz")

    normalized_path = str(raw_name).replace("\\", "/")
    basename = os.path.basename(normalized_path)
    nfc = unicodedata.normalize("NFC", basename)
    filtered = "".join(c for c in nfc if unicodedata.category(c)[0] != "C")

    if not filtered:
        raise HTTPException(status_code=400, detail="Geçerli bir dosya adı bulunamadı")

    parts = filtered.rsplit(".", 1)
    if len(parts) == 1:
        stem = parts[0]
        ext = ""
    else:
        stem = parts[0]
        ext = "." + parts[1]
        if not parts[1].strip():
            raise HTTPException(status_code=400, detail="Geçersiz dosya uzantısı")

    if not stem.strip(" .\t"):
        raise HTTPException(status_code=400, detail="Geçerli bir dosya adı gövdesi bulunamadı")

    max_len = 255
    if len(stem) + len(ext) > max_len:
        stem = stem[: max_len - len(ext)]

    return stem + ext


def validate_extension(filename: str) -> str:
    ext = filename.rsplit(".")[-1].lower() if "." in filename else ""
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=400, detail=f"Desteklenmeyen format: .{ext}. İzin verilenler: {ALLOWED}"
        )
    return ext


def validate_file_content(ext: str, contents: bytes) -> bytes:
    """İçerik doğrular; PDF'lerde preamble varsa siler. Temiz bytes döner."""
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Dosya boyutu {settings.MAX_FILE_SIZE_MB} MB sınırını aşıyor.",
        )

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Dosya boş.")

    magic_signatures = _MAGIC.get(ext)
    if magic_signatures is not None:
        # İlk 8 byte'ta eşleşme yoksa ilk 1024 byte'ı tara (ör. Java wrapper preamble)
        header = contents[:8]
        if not any(header.startswith(sig) for sig in magic_signatures):
            scan_window = contents[:1024]
            offset = -1
            for sig in magic_signatures:
                pos = scan_window.find(sig)
                if pos != -1 and (offset == -1 or pos < offset):
                    offset = pos
            if offset == -1:
                raise HTTPException(
                    status_code=400,
                    detail=f"Dosya içeriği .{ext} formatıyla eşleşmiyor (geçersiz magic bytes).",
                )
            contents = contents[offset:]

    return contents


@router.post("", response_model=list[DocumentUploadResponse])
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),
    session_id: str = "default",
):
    arq_redis = request.app.state.arq_redis
    responses = []

    for file in files:
        sanitized_filename = sanitize_filename(file.filename)
        ext = validate_extension(sanitized_filename)

        document_id = str(uuid.uuid4())
        save_path = os.path.join(settings.UPLOAD_DIR, f"{document_id}.{ext}")

        try:
            contents = await file.read()
            contents = validate_file_content(ext, contents)

            async with aiofiles.open(save_path, "wb") as f:
                await f.write(contents)

            job = await arq_redis.enqueue_job(
                "ingest_document", document_id, save_path, sanitized_filename, session_id
            )
            # doc_id → job_id mapping: delete endpoint'inin Redis cleanup yapabilmesi için
            await arq_redis.set(f"doc:{document_id}:job_id", job.job_id)
        except HTTPException:
            raise
        except Exception as e:
            if os.path.exists(save_path):
                os.remove(save_path)
            raise HTTPException(status_code=500, detail=f"Dosya işlenemedi: {str(e)}")

        responses.append(
            DocumentUploadResponse(
                job_id=job.job_id,
                document_id=document_id,
                filename=sanitized_filename,
                status="queued",
                message="Dosya alındı, işleme kuyruğa alındı.",
            )
        )

    return responses
