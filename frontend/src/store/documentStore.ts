import { create } from 'zustand'
import type { Document, UploadingFile } from '../types/document'

interface DocumentStore {
  documents: Document[]
  uploading: UploadingFile[]
  setDocuments: (docs: Document[]) => void
  upsertDocument: (doc: Document) => void
  removeDocument: (id: string) => void
  addUploading: (f: UploadingFile) => void
  updateUploading: (id: string, updates: Partial<UploadingFile>) => void
  removeUploading: (id: string) => void
}

export const useDocumentStore = create<DocumentStore>((set) => ({
  documents: [],
  uploading: [],

  setDocuments: (docs) => set({ documents: docs }),

  upsertDocument: (doc) =>
    set((state) => {
      const exists = state.documents.some((d) => d.document_id === doc.document_id)
      if (exists) {
        return {
          documents: state.documents.map((d) =>
            d.document_id === doc.document_id ? doc : d
          ),
        }
      }
      return { documents: [doc, ...state.documents] }
    }),

  removeDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.document_id !== id),
    })),

  addUploading: (f) =>
    set((state) => ({ uploading: [...state.uploading, f] })),

  updateUploading: (id, updates) =>
    set((state) => ({
      uploading: state.uploading.map((f) =>
        f.id === id ? { ...f, ...updates } : f
      ),
    })),

  removeUploading: (id) =>
    set((state) => ({
      uploading: state.uploading.filter((f) => f.id !== id),
    })),
}))
