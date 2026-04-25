import { useChatStore } from '../store/chatStore'
import { streamChat, chatOnce } from '../services/chatService'

export function useChat() {
  const { addMessage, appendToken, setSources, setStreaming, setIsStreaming, isStreaming, sessionId } =
    useChatStore()

  async function sendMessage(text: string) {
    if (!text.trim() || isStreaming) return

    const userId = crypto.randomUUID()
    const assistantId = crypto.randomUUID()

    addMessage({ id: userId, role: 'user', content: text })
    addMessage({ id: assistantId, role: 'assistant', content: '', isStreaming: true })
    setIsStreaming(true)

    try {
      for await (const event of streamChat(text, sessionId)) {
        if (event.type === 'token') {
          appendToken(assistantId, event.content)
        } else if (event.type === 'done') {
          break
        }
      }

      // Fetch sources via non-streaming endpoint
      try {
        const result = await chatOnce(text, sessionId)
        setSources(assistantId, result.sources)
      } catch {
        // sources are optional — ignore failure
      }
    } catch (err) {
      appendToken(assistantId, '\n\n_(Bağlantı hatası)_')
    } finally {
      setStreaming(assistantId, false)
      setIsStreaming(false)
    }
  }

  return { sendMessage, isStreaming }
}
