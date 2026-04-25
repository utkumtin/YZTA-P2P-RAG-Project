import api from './api'
import type { Document } from '../types/document'

interface ListDocumentsResponse {
  documents: Document[]
  total: number
}

interface UploadFilesResponse {
  documents: Document[]
}

export async function listDocuments(): Promise<Document[]> {
  const { data } = await api.get<ListDocumentsResponse>('/documents')
  return data.documents
}

export async function uploadFiles(
  files: File[],
  sessionId: string,
  onProgress?: (fileIndex: number, progress: number) => void
): Promise<Document[]> {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  form.append('session_id', sessionId)

  const { data } = await api.post<UploadFilesResponse>('/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        const pct = Math.round((evt.loaded / evt.total) * 100)
        files.forEach((_, i) => onProgress(i, pct))
      }
    },
  })
  return data.documents
}

export async function deleteDocument(documentId: string): Promise<void> {
  await api.delete(`/documents/${documentId}`)
}
