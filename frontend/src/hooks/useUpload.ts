import { useEffect, useRef } from 'react'
import { useDocumentStore } from '../store/documentStore'
import { useChatStore } from '../store/chatStore'
import { listDocuments, uploadFiles, deleteDocument } from '../services/documentService'
import { validateFile } from '../utils/validators'
import { UPLOAD_POLL_INTERVAL_MS } from '../utils/constants'

export function useUpload() {
  const {
    documents,
    uploading,
    setDocuments,
    upsertDocument,
    removeDocument,
    addUploading,
    updateUploading,
    removeUploading,
  } = useDocumentStore()
  const sessionId = useChatStore((s) => s.sessionId)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    listDocuments().then(setDocuments).catch(() => {})
  }, [])

  useEffect(() => {
    const hasActive = documents.some(
      (d) => d.status === 'queued' || d.status === 'processing'
    )

    if (hasActive && !intervalRef.current) {
      intervalRef.current = setInterval(async () => {
        try {
          const updated = await listDocuments()
          updated.forEach((d) => upsertDocument(d))
          const stillActive = updated.some(
            (d) => d.status === 'queued' || d.status === 'processing'
          )
          if (!stillActive && intervalRef.current) {
            clearInterval(intervalRef.current)
            intervalRef.current = null
          }
        } catch {
          // polling failure — keep trying
        }
      }, UPLOAD_POLL_INTERVAL_MS)
    }

    if (!hasActive && intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [documents])

  async function upload(files: File[]) {
    const validFiles = files.filter((f) => validateFile(f).valid)
    if (validFiles.length === 0) return

    const uploadingEntries = validFiles.map((f) => ({
      id: crypto.randomUUID(),
      filename: f.name,
      progress: 0,
    }))
    uploadingEntries.forEach((e) => addUploading(e))

    try {
      const uploaded = await uploadFiles(validFiles, sessionId, (fileIndex, progress) => {
        updateUploading(uploadingEntries[fileIndex].id, { progress })
      })
      uploaded.forEach((doc) => upsertDocument(doc))
    } catch {
      uploadingEntries.forEach((e) =>
        updateUploading(e.id, { error: 'Yükleme başarısız' })
      )
      setTimeout(() => {
        uploadingEntries.forEach((e) => removeUploading(e.id))
      }, 3000)
      return
    }

    uploadingEntries.forEach((e) => removeUploading(e.id))
  }

  async function remove(documentId: string) {
    try {
      await deleteDocument(documentId)
      removeDocument(documentId)
    } catch {
      // silme hatası — kullanıcıya yansıtmıyoruz
    }
  }

  return { documents, uploading, upload, remove }
}
