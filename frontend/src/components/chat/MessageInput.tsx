import { useState, useRef } from 'react'
import { useChat } from '../../hooks/useChat'

export default function MessageInput() {
  const [value, setValue] = useState('')
  const { sendMessage, isStreaming } = useChat()
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    sendMessage(trimmed)
    setValue('')
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div className="border-t border-gray-200 p-3 md:p-4 flex gap-3 bg-white items-end">
      <textarea
        ref={textareaRef}
        rows={1}
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        disabled={isStreaming}
        placeholder="Sorunuzu yazın… (Enter = gönder, Shift+Enter = satır)"
        className="flex-1 resize-none border border-gray-300 rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent disabled:opacity-50 leading-relaxed overflow-hidden"
      />
      <button
        onClick={submit}
        disabled={isStreaming || !value.trim()}
        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg disabled:opacity-50 disabled:cursor-not-allowed transition-colors shrink-0"
      >
        {isStreaming ? 'Yanıtlanıyor…' : 'Gönder'}
      </button>
    </div>
  )
}
