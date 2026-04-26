import { useRef, useState } from 'react'
import { useUpload } from '../../hooks/useUpload'
import { validateFile } from '../../utils/validators'

const SearchIco = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
    <circle cx="7" cy="7" r="4.5" stroke="currentColor" strokeWidth="1.3"/>
    <path d="M10.5 10.5L14 14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
  </svg>
)

const UpIco = () => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
    <path d="M12 17V5M6 11l6-6 6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
)

const DocIco = () => (
  <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
    <path d="M3.5 1.5h6L13 5v9.5H3.5v-13z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    <path d="M9.5 1.5V5H13" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
  </svg>
)

const XIco = () => (
  <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
    <path d="M3.5 3.5l9 9M12.5 3.5l-9 9" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
  </svg>
)

export default function Sidebar() {
  const { uploads, uploadFiles, removeUpload } = useUpload()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [q, setQ] = useState('')

  function handleFiles(fileList: FileList | null) {
    if (!fileList) return
    const valid = Array.from(fileList).filter(f => validateFile(f).valid)
    if (valid.length > 0) uploadFiles(valid)
  }

  const allDocs = uploads.map(u => ({
    id: u.document_id,
    name: u.filename,
    status: u.status,
    progress: u.status === 'processing' ? 0.5 : u.status === 'uploading' ? 0.2 : 1,
  }))

  const filtered = allDocs.filter(d => d.name.toLowerCase().includes(q.toLowerCase()))

  return (
    <aside style={{
      borderRight: '1px solid var(--b-06)',
      background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      minHeight: 0, overflow: 'hidden',
    }}>
      <div style={{ padding: '16px 16px 8px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12,
        }}>
          <div style={{ fontSize: 13.5, fontWeight: 500, color: '#fff', letterSpacing: '-.005em' }}>
            Belgeler
          </div>
          {allDocs.length > 0 && (
            <span style={{ fontSize: 12, color: 'var(--txt-3)' }}>{allDocs.length} belge</span>
          )}
        </div>

        {/* Upload zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files) }}
          onClick={() => inputRef.current?.click()}
          style={{
            border: `1px dashed ${dragging ? 'var(--accent-fg)' : 'var(--b-12)'}`,
            borderRadius: 8, padding: '16px 12px',
            display: 'flex', alignItems: 'center', gap: 12,
            cursor: 'pointer',
            background: dragging ? 'var(--accent-softer)' : 'transparent',
            transition: 'border-color .15s, background .15s',
          }}
        >
          <span style={{
            width: 32, height: 32, borderRadius: 7,
            background: 'var(--accent-softer)',
            color: 'var(--accent-fg)',
            display: 'grid', placeItems: 'center', flexShrink: 0,
          }}>
            <UpIco />
          </span>
          <span style={{ textAlign: 'left' }}>
            <span style={{ display: 'block', fontSize: 13, color: '#fff' }}>Belge ekle</span>
            <span style={{ display: 'block', fontSize: 11.5, color: 'var(--txt-3)', marginTop: 2 }}>
              PDF · DOCX · TXT
            </span>
          </span>
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".pdf,.docx,.doc,.txt"
            style={{ display: 'none' }}
            onChange={e => handleFiles(e.target.files)}
            onClick={e => e.stopPropagation()}
          />
        </div>

        {/* Search */}
        <div style={{
          marginTop: 10,
          display: 'flex', alignItems: 'center', gap: 8,
          border: '1px solid var(--b-06)', borderRadius: 8, padding: '7px 10px',
          background: 'var(--panel)',
        }}>
          <span style={{ color: 'var(--txt-3)', display: 'flex' }}><SearchIco /></span>
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Ara…"
            style={{
              flex: 1, background: 'transparent', border: 0, outline: 'none',
              color: '#fff', fontSize: 13, fontFamily: 'inherit',
            }}
          />
        </div>
      </div>

      {/* Document list */}
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', padding: '4px 10px 14px' }}>
        {filtered.length === 0 && (
          <div style={{ padding: '24px 10px', textAlign: 'center', color: 'var(--txt-3)', fontSize: 13 }}>
            {allDocs.length === 0 ? 'Henüz belge yok' : 'Eşleşen belge yok'}
          </div>
        )}
        {filtered.map(doc => (
          <DocItem
            key={doc.id}
            doc={doc}
            onRemove={() => removeUpload(doc.id)}
          />
        ))}
      </div>
    </aside>
  )
}

interface DocItemProps {
  doc: { id: string; name: string; status: string; progress: number }
  onRemove: () => void
}

function DocItem({ doc, onRemove }: DocItemProps) {
  const isIndexed = doc.status === 'done' || doc.status === 'completed'
  const isFailed = doc.status === 'error' || doc.status === 'failed'

  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '10px 12px', borderRadius: 8, marginBottom: 2,
      border: '1px solid transparent',
    }}>
      <span style={{ color: 'var(--txt-3)', flexShrink: 0, display: 'flex' }}><DocIco /></span>
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{
          fontSize: 13.5, color: '#fff', fontWeight: 400, letterSpacing: '-.005em',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}>
          {doc.name}
        </div>
        <div style={{ marginTop: 2, fontSize: 12, color: isFailed ? '#f87171' : 'var(--txt-3)' }}>
          {isFailed ? 'Başarısız' : isIndexed ? 'İndekslendi' : 'İşleniyor…'}
        </div>
        {!isIndexed && !isFailed && (
          <div style={{ marginTop: 6, height: 2, background: 'var(--b-06)', borderRadius: 99, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${doc.progress * 100}%`,
              background: 'var(--accent-fg)', borderRadius: 99, transition: 'width .3s',
            }} />
          </div>
        )}
      </div>
      <button
        onClick={e => { e.stopPropagation(); onRemove() }}
        title="Kaldır"
        style={{
          background: 'transparent', border: 'none', color: 'var(--txt-4)',
          cursor: 'pointer', padding: 4, borderRadius: 4,
          display: 'grid', placeItems: 'center', flexShrink: 0,
        }}
      >
        <XIco />
      </button>
    </div>
  )
}
