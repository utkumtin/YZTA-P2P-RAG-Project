import { useUpload } from '../../hooks/useUpload'
import UploadZone from '../upload/UploadZone'
import UploadProgress from '../upload/UploadProgress'
import FileList from '../upload/FileList'
import type { Document, UploadingFile } from '../../types/document'

interface SidebarProps {
  open: boolean
}

export default function Sidebar({ open }: SidebarProps) {
  const { uploads, uploadFiles, removeUpload } = useUpload()

  const documents: Document[] = uploads
    .filter((u) => u.status === 'done' || u.status === 'error')
    .map((u) => ({
      document_id: u.document_id,
      filename: u.filename,
      created_at: new Date().toISOString(),
      status: u.status === 'done' ? 'completed' : 'failed',
    }))

  const uploadingFiles: UploadingFile[] = uploads
    .filter((u) => u.status !== 'done' && u.status !== 'error')
    .map((u) => ({
      id: u.document_id,
      filename: u.filename,
      progress: u.status === 'processing' ? 50 : 10,
      error: u.error,
    }))

  return (
    <aside
      className={`
        w-72 bg-gray-100 border-r border-gray-200 flex flex-col flex-shrink-0
        transition-all duration-300
        ${open ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}
      `}
    >
      <div className="p-4 flex flex-col gap-3 flex-1 overflow-hidden">
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wider shrink-0">
          Dökümanlar
        </h2>
        <UploadZone onFiles={uploadFiles} />
        {uploadingFiles.length > 0 && <UploadProgress uploading={uploadingFiles} />}
        <FileList documents={documents} onRemove={removeUpload} />
      </div>
    </aside>
  )
}
