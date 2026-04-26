import { useEffect, useRef } from 'react'
import { useChatStore } from '../../store/chatStore'
import MessageBubble from './MessageBubble'
import type { Source } from '../../types/chat'

const SparkleIco = () => (
  <svg width="22" height="22" viewBox="0 0 16 16" fill="none">
    <path d="M8 2v4M8 10v4M2 8h4M10 8h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M4 4l1.5 1.5M10.5 10.5L12 12M4 12l1.5-1.5M10.5 5.5L12 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".6"/>
  </svg>
)

interface ChatWindowProps {
  setHoverSrc: (src: Source | null) => void
}

export default function ChatWindow({ setHoverSrc }: ChatWindowProps) {
  const messages = useChatStore(s => s.messages)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  if (messages.length === 0) {
    return (
      <div style={{
        flex: 1, overflowY: 'auto',
        display: 'grid', placeItems: 'center',
        padding: '32px 24px',
      }}>
        <div style={{ textAlign: 'center', maxWidth: 420 }}>
          <div style={{
            margin: '0 auto',
            width: 48, height: 48, borderRadius: 12,
            background: 'var(--accent-soft)',
            border: '1px solid var(--accent-border-soft)',
            display: 'grid', placeItems: 'center', color: 'var(--accent-fg)',
          }}>
            <SparkleIco />
          </div>
          <h1 style={{
            fontSize: 24, fontWeight: 500, letterSpacing: '-.02em', lineHeight: 1.2,
            margin: '20px 0 8px', color: '#fff',
          }}>
            Belgeleriniz hakkında soru sorun
          </h1>
          <p style={{
            fontSize: 14, color: 'var(--txt-2)', letterSpacing: '-.005em',
            margin: 0, lineHeight: 1.6,
          }}>
            Soldaki paneldeki belgeler kullanılarak yanıt vereceğim.
            Kaynaklar her yanıtın yanında listelenir.
          </p>
        </div>
      </div>
    )
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '32px 24px 8px' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        {messages.map(m => (
          <MessageBubble key={m.id} message={m} onHoverSrc={setHoverSrc} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
