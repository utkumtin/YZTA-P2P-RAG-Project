import type { SummarizeResponse } from '../types/summarize'

interface SummarizePayload {
  document_ids: string[]
  session_id: string
  max_length: number
}

export async function summarizeDocuments(payload: SummarizePayload): Promise<SummarizeResponse> {
  const res = await fetch('/api/routes/summarize', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    const detail = (err as { detail?: string }).detail ?? `Özet alınamadı (${res.status})`
    throw new Error(res.status === 429 ? `429: ${detail}` : detail)
  }
  return res.json() as Promise<SummarizeResponse>
}
