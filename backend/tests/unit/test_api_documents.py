from unittest.mock import MagicMock
from datetime import datetime, timezone

import pytest

from app.api.routes.documents import list_documents, delete_document


def _make_request(docs: list):
    """Fake FastAPI Request with mocked rag_pipeline."""
    vs_mock = MagicMock()
    vs_mock.list_documents.return_value = docs
    vs_mock.delete_document.return_value = None

    pipeline_mock = MagicMock()
    pipeline_mock.vector_store = vs_mock

    state = MagicMock()
    state.rag_pipeline = pipeline_mock

    req = MagicMock()
    req.app.state = state
    return req


@pytest.mark.asyncio
async def test_liste_bos_donuyor():
    req = _make_request([])
    result = await list_documents(request=req, session_id="default")
    assert result["documents"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_liste_dolu_donuyor():
    req = _make_request([
        {"doc_id": "abc-123", "filename": "test.pdf", "chunk_count": 5},
    ])
    result = await list_documents(request=req, session_id="default")
    assert result["total"] == 1
    assert result["documents"][0].document_id == "abc-123"
    assert result["documents"][0].filename == "test.pdf"


@pytest.mark.asyncio
async def test_silme_basarili_donus():
    req = _make_request([])
    result = await delete_document(document_id="doc-xyz-123", request=req, session_id="default")
    assert result.document_id == "doc-xyz-123"
    assert result.deleted is True


@pytest.mark.asyncio
async def test_silme_farkli_id():
    req = _make_request([])
    r1 = await delete_document(document_id="id-aaa", request=req, session_id="default")
    r2 = await delete_document(document_id="id-bbb", request=req, session_id="default")
    assert r1.document_id == "id-aaa"
    assert r2.document_id == "id-bbb"
