from fastapi import APIRouter, HTTPException

from app.services.document_service import DocumentDeleteResponse

router = APIRouter()


@router.get("")
async def list_documents():
    # qdrant baglaninca dolacak burasi
    return {"documents": [], "total": 0}


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(document_id: str):
    # qdrant baglaninca dolacak burasi
    return DocumentDeleteResponse(document_id=document_id, deleted=True)