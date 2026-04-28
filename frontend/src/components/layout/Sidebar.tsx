import { useRef, useState, useEffect } from 'react'
import { useUpload } from '../../hooks/useUpload'
import { useDocumentStore } from '../../store/documentStore'
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

const CheckIco = ({ checked }: { checked: boolean }) => (
  <span style={{
    flexShrink: 0, width: 16, height: 16, borderRadius: 5,
    border: checked ? 'none' : '1.5px solid var(--b-12)',
    background: checked ? 'var(--accent-fg)' : 'transparent',
    display: 'grid', placeItems: 'center',
    transition: 'background .12s, border .12s',
    color: '#1a1320',
  }}>
    {checked && (
      <svg width="9" height="9" viewBox="0 0 10 10" fill="none">
        <path d="M2 5l2.5 2.5L8 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    )}
  </span>
)

export default function Sidebar() {
  const { uploads, uploadFiles, removeUpload } = useUpload()
  const {
    selectedDocumentIds,
    toggleDocumentSelection,
    setDocumentSelection,
    clearDocumentSelection,
  } = useDocumentStore()
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [q, setQ] = useState('')
  const autoSelectedRef = useRef<Set<string>>(new Set())

  function handleFiles(fileList: FileList | null) {
    if (!fileList) return
    const valid = Array.from(fileList).filter(f => validateFile(f).valid)
    if (valid.length > 0) uploadFiles(valid)
  }

  // Auto-select newly completed docs
  useEffect(() => {
    uploads
      .filter(u => u.status === 'done' && !autoSelectedRef.current.has(u.document_id))
      .forEach(u => {
        autoSelectedRef.current.add(u.document_id)
        setDocumentSelection(u.document_id, true)
      })
  }, [uploads, setDocumentSelection])

  const allDocs = uploads.map(u => ({
    id: u.document_id,
    name: u.filename,
    status: u.status,
    progress: u.status === 'processing' ? 0.5 : u.status === 'uploading' ? 0.2 : 1,
  }))

  const doneDocs = allDocs.filter(d => d.status === 'done')
  const allSelected = doneDocs.length > 0 && doneDocs.every(d => selectedDocumentIds.has(d.id))

  const toggleAll = () => {
    if (allSelected) {
      clearDocumentSelection()
    } else {
      doneDocs.forEach(d => setDocumentSelection(d.id, true))
    }
  }

  const filtered = allDocs.filter(d => d.name.toLowerCase().includes(q.toLowerCase()))

  function handleRemove(docId: string) {
    setDocumentSelection(docId, false)
    autoSelectedRef.current.delete(docId)
    removeUpload(docId)
  }

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
          {doneDocs.length > 0 && (
            <button
              onClick={toggleAll}
              style={{
                appearance: 'none', cursor: 'pointer',
                fontSize: 12, color: 'var(--accent-fg)',
                background: 'var(--accent-softer)',
                border: '1px solid var(--accent-border-soft)',
                padding: '3px 9px', borderRadius: 6, letterSpacing: '-.005em',
              }}
            >
              {allSelected ? 'Tümünü kaldır' : 'Tümünü seç'}
            </button>
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
              PDF · DOCX · DOC · TXT · maks 50 MB
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

        {/* Selection summary */}
        {selectedDocumentIds.size > 0 && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--accent-fg)', letterSpacing: '-.005em' }}>
            {selectedDocumentIds.size} belge seçili
          </div>
        )}
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
            selected={selectedDocumentIds.has(doc.id)}
            onToggle={() => toggleDocumentSelection(doc.id)}
            onRemove={() => handleRemove(doc.id)}
          />
        ))}
      </div>
    </aside>
  )
}

interface DocItemProps {
  doc: { id: string; name: string; status: string; progress: number }
  selected: boolean
  onToggle: () => void
  onRemove: () => void
}

function DocItem({ doc, selected, onToggle, onRemove }: DocItemProps) {
  const isIndexed = doc.status === 'done' || doc.status === 'completed'
  const isFailed = doc.status === 'error' || doc.status === 'failed'

  return (
    <div
      onClick={isIndexed ? onToggle : undefined}
      style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '10px 12px', borderRadius: 8, marginBottom: 2,
        background: selected ? 'var(--accent-softer)' : 'transparent',
        border: selected ? '1px solid var(--accent-border-soft)' : '1px solid transparent',
        cursor: isIndexed ? 'pointer' : 'default',
        transition: 'background .15s, border-color .15s',
      }}
    >
      {isIndexed ? (
        <CheckIco checked={selected} />
      ) : (
        <span style={{ color: 'var(--txt-3)', flexShrink: 0, display: 'flex' }}><DocIco /></span>
      )}
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
