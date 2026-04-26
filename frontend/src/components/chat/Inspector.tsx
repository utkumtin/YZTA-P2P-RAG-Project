import type { Message, Source } from '../../types/chat'

interface InspectorProps {
  hoverSrc: Source | null
  messages: Message[]
  onClose: () => void
}

const XIco = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
    <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
)

const subtleBtn: React.CSSProperties = {
  appearance: 'none', cursor: 'pointer',
  width: 28, height: 28, borderRadius: 6,
  border: '1px solid transparent', background: 'transparent',
  color: 'var(--txt-2)', display: 'grid', placeItems: 'center',
}

export default function Inspector({ hoverSrc, messages, onClose }: InspectorProps) {
  const last = [...messages].reverse().find(m => m.role === 'assistant')
  const sources = last?.sources ?? []

  return (
    <div style={{
      borderLeft: '1px solid var(--b-06)', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      minHeight: 0, overflow: 'hidden', height: '100%', width: '100%',
    }}>
      <div style={{
        padding: '16px 16px 12px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        borderBottom: '1px solid var(--b-06)',
        flexShrink: 0,
      }}>
        <div style={{ fontSize: 13.5, fontWeight: 500, color: '#fff', letterSpacing: '-.005em' }}>
          Kaynaklar
        </div>
        <button onClick={onClose} style={subtleBtn}><XIco /></button>
      </div>

      {sources.length === 0 ? (
        <div style={{
          flex: 1, display: 'grid', placeItems: 'center',
          padding: 24, textAlign: 'center',
        }}>
          <div style={{ color: 'var(--txt-3)', fontSize: 13, maxWidth: 220, lineHeight: 1.5 }}>
            Bir soru sorduğunuzda kaynaklar burada görünür.
          </div>
        </div>
      ) : (
        <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '12px 14px 16px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {sources.map((s, i) => {
              const isHovered = hoverSrc === s
              return (
                <div key={i} style={{
                  border: `1px solid ${isHovered ? 'var(--accent-border-soft)' : 'var(--b-06)'}`,
                  borderRadius: 8, padding: '10px 12px',
                  background: isHovered ? 'var(--accent-softer)' : 'var(--panel)',
                  display: 'flex', alignItems: 'flex-start', gap: 10,
                  transition: 'border-color .15s, background .15s',
                }}>
                  <span style={{
                    fontSize: 11, fontWeight: 500, color: 'var(--accent-fg)',
                    background: 'var(--accent-soft)',
                    padding: '1px 6px', borderRadius: 4, flexShrink: 0, marginTop: 1,
                  }}>
                    {i + 1}
                  </span>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{
                      fontSize: 13, color: '#fff',
                      whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                      letterSpacing: '-.005em',
                    }}>
                      {s.filename || 'Belge'}
                    </div>
                    {s.chunk_text && (
                      <div style={{
                        fontSize: 12, color: 'var(--txt-3)', marginTop: 4, lineHeight: 1.5,
                      }}>
                        {s.chunk_text.length > 160 ? s.chunk_text.slice(0, 160) + '…' : s.chunk_text}
                      </div>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
