from app.api.routes.documents import delete_document, list_documents


async def test_liste_bos_donuyor():
    result = await list_documents()
    assert result["documents"] == []
    assert result["total"] == 0


async def test_silme_basarili_donus():
    result = await delete_document("doc-xyz-123")
    assert result.document_id == "doc-xyz-123"
    assert result.deleted is True


async def test_silme_farkli_id():
    r1 = await delete_document("id-aaa")
    r2 = await delete_document("id-bbb")
    assert r1.document_id == "id-aaa"
    assert r2.document_id == "id-bbb"
