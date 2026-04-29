import { create } from 'zustand'
import type { Document, UploadingFile } from '../types/document'

interface DocumentStore {
  documents: Document[]
  uploading: UploadingFile[]
  selectedDocumentIds: Set<string>
  setDocuments: (docs: Document[]) => void
  upsertDocument: (doc: Document) => void
  removeDocument: (id: string) => void
  addUploading: (f: UploadingFile) => void
  updateUploading: (id: string, updates: Partial<UploadingFile>) => void
  removeUploading: (id: string) => void
  toggleDocumentSelection: (id: string) => void
  setDocumentSelection: (id: string, selected: boolean) => void
  selectAllDocuments: (ids: string[]) => void
  clearDocumentSelection: () => void
}

export const useDocumentStore = create<DocumentStore>((set) => ({
  documents: [],
  uploading: [],
  selectedDocumentIds: new Set(),

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
    set((state) => {
      const next = new Set(state.selectedDocumentIds)
      next.delete(id)
      return {
        documents: state.documents.filter((d) => d.document_id !== id),
        selectedDocumentIds: next,
      }
    }),

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

  toggleDocumentSelection: (id) =>
    set((state) => {
      const next = new Set(state.selectedDocumentIds)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { selectedDocumentIds: next }
    }),

  setDocumentSelection: (id, selected) =>
    set((state) => {
      const next = new Set(state.selectedDocumentIds)
      if (selected) next.add(id)
      else next.delete(id)
      return { selectedDocumentIds: next }
    }),

  selectAllDocuments: (ids) =>
    set((state) => {
      const next = new Set(state.selectedDocumentIds)
      ids.forEach((id) => next.add(id))
      return { selectedDocumentIds: next }
    }),

  clearDocumentSelection: () =>
    set({ selectedDocumentIds: new Set() }),
}))
