export type SummaryLength = 'short' | 'normal' | 'long'

export interface SummarizeOption {
  id: SummaryLength
  label: string
  hint: string
  maxLength: number
}

export interface SummarizeSourceInfo {
  filename: string
  page_number: number | null
  document_id: string
}

export interface SummarizeResponse {
  summary: string
  document_ids: string[]
  sources: SummarizeSourceInfo[]
}
