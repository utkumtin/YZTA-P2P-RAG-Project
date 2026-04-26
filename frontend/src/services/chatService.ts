import api from './api'
import type { Source } from '../types/chat'

interface ChatResponse {
  answer: string
  sources: Source[]
  question: string
}

interface SSEToken {
  type: 'token'
  content: string
}

interface SSEDone {
  type: 'done'
}

type SSEEvent = SSEToken | SSEDone

export async function* streamChat(
  question: string,
  sessionId: string
): AsyncGenerator<SSEEvent> {
  const response = await fetch('/api/routes/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, session_id: sessionId }),
  })

  if (!response.ok || !response.body) {
    throw new Error(`Stream failed: ${response.status}`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue
      const raw = line.slice(6).trim()
      if (!raw) continue
      try {
        const event = JSON.parse(raw) as SSEEvent
        yield event
      } catch {
        // malformed line — skip
      }
    }
  }
}

export async function chatOnce(
  question: string,
  sessionId: string
): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>('/chat', {
    question,
    session_id: sessionId,
  })
  return data
}
