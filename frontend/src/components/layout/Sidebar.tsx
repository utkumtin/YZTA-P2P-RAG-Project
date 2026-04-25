import { useUpload } from '../../hooks/useUpload'
import UploadZone from '../upload/UploadZone'
import UploadProgress from '../upload/UploadProgress'
import FileList from '../upload/FileList'

interface SidebarProps {
  open: boolean
}

export default function Sidebar({ open }: SidebarProps) {
  const { documents, uploading, upload, remove } = useUpload()

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
        <UploadZone onFiles={upload} />
        {uploading.length > 0 && <UploadProgress uploading={uploading} />}
        <FileList documents={documents} onRemove={remove} />
      </div>
    </aside>
  )
}
