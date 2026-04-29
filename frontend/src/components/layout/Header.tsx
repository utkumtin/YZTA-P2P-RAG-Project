const SparkleIco = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
    <path d="M8 2v4M8 10v4M2 8h4M10 8h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    <path d="M4 4l1.5 1.5M10.5 10.5L12 12M4 12l1.5-1.5M10.5 5.5L12 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" opacity=".6"/>
  </svg>
)

const TrashIco = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
    <path d="M2.5 4.5h11M6 4.5V3h4v1.5M13 4.5l-.8 8.5H3.8L3 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

interface HeaderProps {
  inspectorOpen: boolean
  onToggleInspector: () => void
  onClear: () => void
}

export default function Header({ inspectorOpen, onToggleInspector, onClear }: HeaderProps) {
  return (
    <header style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 18px', height: 52,
      borderBottom: '1px solid var(--b-06)', background: 'var(--bg)',
      flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 6,
          background: 'var(--accent-soft)',
          border: '1px solid var(--accent-border-soft)',
          display: 'grid', placeItems: 'center', color: 'var(--accent-fg)',
        }}>
          <SparkleIco />
        </div>
        <span style={{ fontSize: 14, fontWeight: 500, letterSpacing: '-.01em', color: '#fff' }}>YZTA-P2P-RAG</span>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <button
          onClick={onClear}
          title="Sohbeti temizle"
          style={{
            appearance: 'none', cursor: 'pointer',
            width: 30, height: 30,
            background: 'transparent',
            color: 'var(--txt-2)',
            border: '1px solid var(--b-08)', borderRadius: 6,
            display: 'grid', placeItems: 'center',
            transition: 'background .15s, color .15s',
          }}
          onMouseEnter={e => { (e.currentTarget as HTMLButtonElement).style.background = 'var(--b-06)'; (e.currentTarget as HTMLButtonElement).style.color = '#fff' }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.background = 'transparent'; (e.currentTarget as HTMLButtonElement).style.color = 'var(--txt-2)' }}
        >
          <TrashIco />
        </button>
        <button
          onClick={onToggleInspector}
          style={{
            appearance: 'none', cursor: 'pointer',
            padding: '6px 12px', height: 30,
            background: inspectorOpen ? 'var(--b-06)' : 'transparent',
            color: inspectorOpen ? '#fff' : 'var(--txt-2)',
            border: '1px solid var(--b-08)', borderRadius: 6,
            fontSize: 13, fontWeight: 400, letterSpacing: '-.005em',
            transition: 'background .15s, color .15s',
          }}
        >
          Kaynaklar
        </button>
      </div>
    </header>
  )
}
