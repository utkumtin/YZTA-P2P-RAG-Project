import type { Document } from '../../types/document'
import { formatDate } from '../../utils/formatters'

interface FileListProps {
  documents: Document[]
  onRemove: (id: string) => void
}

const statusDot: Record<Document['status'], string> = {
  queued: 'bg-yellow-400',
  processing: 'bg-blue-400 animate-pulse',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
}

const statusTitle: Record<Document['status'], string> = {
  queued: 'Kuyrukta',
  processing: 'İşleniyor',
  completed: 'Tamamlandı',
  failed: 'Başarısız',
}

export default function FileList({ documents, onRemove }: FileListProps) {
  if (documents.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-400 text-xs py-6">
        Henüz döküman yok
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1 overflow-y-auto flex-1">
      {documents.map((doc) => (
        <div
          key={doc.document_id}
          className="group flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-gray-200 transition-colors"
        >
          <span
            className={`shrink-0 w-2 h-2 rounded-full ${statusDot[doc.status]}`}
            title={statusTitle[doc.status]}
          />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium text-gray-700 truncate">{doc.filename}</p>
            <p className="text-[10px] text-gray-400">{formatDate(doc.created_at)}</p>
          </div>
          <button
            onClick={() => onRemove(doc.document_id)}
            className="shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded hover:bg-red-100 text-gray-400 hover:text-red-500"
            title="Sil"
          >
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          </button>
        </div>
      ))}
    </div>
  )
}
