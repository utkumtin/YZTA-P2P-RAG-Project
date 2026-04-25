export interface Source {
  document_id: string
  filename: string
  chunk_text: string
}

export type MessageRole = 'user' | 'assistant'

export interface Message {
  id: string
  role: MessageRole
  content: string
  sources?: Source[]
  isStreaming?: boolean
}
