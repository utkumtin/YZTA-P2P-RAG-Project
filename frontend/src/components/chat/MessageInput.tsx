import { useState, useRef, useEffect, useMemo } from 'react'
import { useChat } from '../../hooks/useChat'
import { useDocumentStore } from '../../store/documentStore'

const SendIco = () => (
  <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
    <path d="M2.5 8l11-4.5L9.5 14l-2-5.5-5-.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" strokeLinecap="round"/>
  </svg>
)

export default function MessageInput() {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)
  const selectedDocumentIds = useDocumentStore(s => s.selectedDocumentIds)
  const documentIds = useMemo(() => [...selectedDocumentIds], [selectedDocumentIds])
  const { sendMessage, isStreaming } = useChat(documentIds.length > 0 ? documentIds : undefined)
  const ta = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!ta.current) return
    ta.current.style.height = 'auto'
    ta.current.style.height = Math.min(160, ta.current.scrollHeight) + 'px'
  }, [value])

  function submit() {
    const trimmed = value.trim()
    if (!trimmed || isStreaming) return
    sendMessage(trimmed)
    setValue('')
    if (ta.current) ta.current.style.height = 'auto'
  }

  const sendDisabled = isStreaming || !value.trim()

  return (
    <div style={{ padding: '8px 24px 22px' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <div style={{
          position: 'relative',
          border: focused ? '1px solid var(--accent-border-soft-strong)' : '1px solid var(--b-10)',
          background: 'var(--panel)',
          borderRadius: 14,
          boxShadow: focused ? '0 0 0 4px var(--accent-softer)' : 'none',
          transition: 'border-color .15s, box-shadow .15s',
        }}>
          <textarea
            ref={ta}
            value={value}
            onChange={e => setValue(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={e => {
              if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit() }
            }}
            placeholder="Belgelere bir soru sorun…"
            rows={1}
            disabled={isStreaming}
            style={{
              display: 'block', width: '100%',
              resize: 'none', border: 0, outline: 'none',
              background: 'transparent', color: '#fff',
              fontFamily: 'inherit', fontSize: 15, lineHeight: 1.5,
              letterSpacing: '-.005em',
              padding: '14px 56px 14px 16px',
              minHeight: 50, maxHeight: 160,
              overflow: 'hidden',
            }}
          />
          <button
            onClick={submit}
            disabled={sendDisabled}
            style={{
              position: 'absolute', right: 8, bottom: 8,
              cursor: sendDisabled ? 'default' : 'pointer',
              width: 34, height: 34, borderRadius: 9,
              background: sendDisabled ? 'var(--b-06)' : 'var(--accent-fg)',
              color: sendDisabled ? 'var(--txt-3)' : '#1a1320',
              border: 'none',
              display: 'grid', placeItems: 'center',
              transition: 'background .15s',
            }}
          >
            <SendIco />
          </button>
        </div>
      </div>
    </div>
  )
}
