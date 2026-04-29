import { useState, useRef, useEffect } from 'react'
import { createPortal } from 'react-dom'
import type { Message, Source } from '../../types/chat'
import StreamingIndicator from './StreamingIndicator'

interface MessageBubbleProps {
  message: Message
  onHoverSrc?: (src: Source | null) => void
  sourceRegistry: Map<string, number>
}

const SparkleIco = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
    <path d="M8 2v4M8 10v4M2 8h4M10 8h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M4 4l1.5 1.5M10.5 10.5L12 12M4 12l1.5-1.5M10.5 5.5L12 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".6"/>
  </svg>
)

const CopyIco = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
    <rect x="5" y="5" width="9" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M2 11V3.5A1.5 1.5 0 0 1 3.5 2H11" stroke="currentColor" strokeWidth="1.2"/>
  </svg>
)

const subtleBtn: React.CSSProperties = {
  appearance: 'none', cursor: 'pointer',
  width: 28, height: 28, borderRadius: 6,
  border: '1px solid transparent', background: 'transparent',
  color: 'var(--txt-2)', display: 'grid', placeItems: 'center',
}

function CitationChip({
  n, source, onHover,
}: {
  n: number
  source: Source
  onHover?: (src: Source | null) => void
}) {
  const [open, setOpen] = useState(false)
  const chipRef = useRef<HTMLSpanElement>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 })
  const hasChunk = !!source.chunk_text

  useEffect(() => {
    if (!open) return
    function handleDown(e: MouseEvent) {
      if (
        chipRef.current?.contains(e.target as Node) ||
        popoverRef.current?.contains(e.target as Node)
      ) return
      setOpen(false)
    }
    document.addEventListener('mousedown', handleDown)
    return () => document.removeEventListener('mousedown', handleDown)
  }, [open])

  function handleClick(e: React.MouseEvent) {
    if (!hasChunk) return
    e.stopPropagation()
    const rect = chipRef.current?.getBoundingClientRect()
    if (rect) setPos({ top: rect.bottom + 6, left: rect.left, width: rect.width })
    setOpen(o => !o)
  }

  return (
    <>
      <span
        ref={chipRef}
        onMouseEnter={() => onHover?.(source)}
        onMouseLeave={() => onHover?.(null)}
        onClick={handleClick}
        style={{
          display: 'inline-flex', alignItems: 'center',
          fontSize: 11, fontWeight: 500,
          padding: '1px 6px', margin: '0 2px',
          background: open ? 'var(--accent-fg)' : 'var(--accent-soft)',
          color: open ? '#1a1320' : 'var(--accent-fg)',
          borderRadius: 4,
          cursor: hasChunk ? 'pointer' : 'default',
          verticalAlign: 'baseline',
          transition: 'background .12s, color .12s',
          userSelect: 'none',
        }}
      >
        {n}
      </span>

      {open && hasChunk && createPortal(
        <div
          ref={popoverRef}
          style={{
            position: 'fixed',
            top: pos.top,
            left: Math.max(8, Math.min(pos.left, window.innerWidth - 344)),
            width: 336,
            zIndex: 9999,
            background: 'var(--panel)',
            border: '1px solid var(--accent-border-soft)',
            borderRadius: 10,
            boxShadow: '0 8px 32px rgba(0,0,0,.45)',
            overflow: 'hidden',
          }}
        >
          <div style={{
            padding: '8px 12px',
            borderBottom: '1px solid var(--b-06)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 11, fontWeight: 500, color: 'var(--accent-fg)' }}>
              [{n}] {source.filename}
            </span>
            <button
              onClick={() => setOpen(false)}
              style={{
                background: 'transparent', border: 'none',
                color: 'var(--txt-3)', cursor: 'pointer',
                fontSize: 14, lineHeight: 1, padding: '0 2px',
              }}
            >×</button>
          </div>
          <div style={{
            padding: '10px 12px',
            fontSize: 12.5, lineHeight: 1.6,
            color: 'rgba(255,255,255,.8)',
            maxHeight: 260, overflowY: 'auto',
            whiteSpace: 'pre-wrap',
            letterSpacing: '-.003em',
          }}>
            {source.chunk_text}
          </div>
        </div>,
        document.body
      )}
    </>
  )
}

export default function MessageBubble({ message, onHoverSrc, sourceRegistry }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div style={{ display: 'flex', justifyContent: 'flex-end', margin: '20px 0' }}>
        <div style={{
          maxWidth: '72%',
          background: 'var(--bubble)',
          border: '1px solid var(--b-06)',
          borderRadius: 14,
          padding: '11px 16px',
          fontSize: 14.5, lineHeight: 1.55, color: '#fff',
          letterSpacing: '-.005em',
          whiteSpace: 'pre-wrap',
        }}>
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div style={{ margin: '20px 0', display: 'flex', gap: 14 }}>
      <div style={{
        width: 28, height: 28, flexShrink: 0, borderRadius: 8,
        background: 'var(--accent-soft)',
        border: '1px solid var(--accent-border-soft)',
        display: 'grid', placeItems: 'center',
        color: 'var(--accent-fg)',
      }}>
        <SparkleIco />
      </div>

      <div style={{ flex: 1, minWidth: 0, paddingTop: 2 }}>
        <div style={{
          fontSize: 14.5, lineHeight: 1.65,
          color: 'rgba(255,255,255,.92)', letterSpacing: '-.005em',
          whiteSpace: 'pre-wrap',
        }}>
          {message.content || (message.isStreaming ? <StreamingIndicator /> : null)}

          {message.isStreaming && message.content && (
            <span style={{
              display: 'inline-block', width: 2, height: 16,
              background: 'var(--accent-fg)', marginLeft: 2,
              verticalAlign: 'middle',
              animation: 'yz-pulse 1s infinite',
            }} />
          )}

          {message.isCached && (
            <span style={{ fontSize: 10, marginLeft: 8, color: 'var(--accent-fg)', fontWeight: 500 }}>
              (⚡ Hızlı)
            </span>
          )}

          {message.sources && message.sources.length > 0 && (
            <span style={{ marginLeft: 4 }}>
              {message.sources.map((s, i) => (
                <CitationChip
                  key={i}
                  n={sourceRegistry.get(s.document_id || s.filename) ?? i + 1}
                  source={s}
                  onHover={onHoverSrc}
                />
              ))}
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 2, marginTop: 10, marginLeft: -6 }}>
          <button
            style={subtleBtn}
            title="Kopyala"
            onClick={() => navigator.clipboard.writeText(message.content)}
          >
            <CopyIco />
          </button>
        </div>
      </div>
    </div>
  )
}
