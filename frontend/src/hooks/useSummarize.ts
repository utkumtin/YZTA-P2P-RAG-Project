import { useState } from 'react'
import { useChatStore } from '../store/chatStore'
import { useDocumentStore } from '../store/documentStore'
import { summarizeDocuments } from '../services/summarizeService'
import { getSessionId } from '../utils/session'
import type { SummarizeOption } from '../types/summarize'
import type { Source } from '../types/chat'

export function useSummarize() {
  const [loading, setLoading] = useState(false)
  const { selectedDocumentIds } = useDocumentStore()
  const { addMessage, setMessageContent, setSources, setStreaming } = useChatStore()

  const summarize = async (option: SummarizeOption) => {
    const ids = Array.from(selectedDocumentIds)
    if (ids.length === 0) return
    setLoading(true)

    addMessage({
      id: crypto.randomUUID(),
      role: 'user',
      content: `${option.label} özet (${ids.length} belge)`,
    })

    const placeholderId = crypto.randomUUID()
    addMessage({ id: placeholderId, role: 'assistant', content: '', isStreaming: true })

    try {
      const result = await summarizeDocuments({
        document_ids: ids,
        session_id: getSessionId(),
        max_length: option.maxLength,
      })

      const sources: Source[] = result.sources.map(s => ({
        document_id: s.document_id,
        filename: s.filename,
        chunk_text: s.page_number != null ? `Sayfa ${s.page_number}` : s.filename,
      }))

      setMessageContent(placeholderId, result.summary)
      setSources(placeholderId, sources)
    } catch (err) {
      const msg = err instanceof Error ? err.message : ''
      const isRateLimit = msg.includes('429') || msg.toLowerCase().includes('rate limit')
      setMessageContent(
        placeholderId,
        isRateLimit
          ? 'API günlük token limiti doldu. Birkaç dakika bekleyip tekrar deneyin.'
          : 'Özet oluşturulurken bir hata oluştu.',
      )
    } finally {
      setStreaming(placeholderId, false)
      setLoading(false)
    }
  }

  return {
    summarize,
    loading,
    canSummarize: selectedDocumentIds.size > 0 && !loading,
  }
}
