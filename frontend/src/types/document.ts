export interface Document {
  document_id: string
  filename: string
  created_at: string
  chunk_count?: number
  status: 'queued' | 'processing' | 'completed' | 'failed'
}

export interface UploadingFile {
  id: string
  filename: string
  progress: number
  error?: string
}
