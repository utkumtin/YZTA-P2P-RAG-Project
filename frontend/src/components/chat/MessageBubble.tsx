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
  return (
    <span
      onMouseEnter={() => onHover?.(source)}
      onMouseLeave={() => onHover?.(null)}
      style={{
        display: 'inline-flex', alignItems: 'center',
        fontSize: 11, fontWeight: 500,
        padding: '1px 6px', margin: '0 2px',
        background: 'var(--accent-soft)',
        color: 'var(--accent-fg)',
        borderRadius: 4, cursor: 'default',
        verticalAlign: 'baseline',
      }}
    >
      {n}
    </span>
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
