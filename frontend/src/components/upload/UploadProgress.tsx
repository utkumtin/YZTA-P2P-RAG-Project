import type { UploadingFile } from '../../types/document'

interface UploadProgressProps {
  uploading: UploadingFile[]
}

function statusLabel(f: UploadingFile): string {
  if (f.error) return 'Başarısız'
  if (f.progress < 100) return 'Yükleniyor…'
  return 'İşleniyor…'
}

export default function UploadProgress({ uploading }: UploadProgressProps) {
  if (uploading.length === 0) return null

  return (
    <div className="flex flex-col gap-2">
      {uploading.map((f) => (
        <div key={f.id} className="text-xs">
          <div className="flex justify-between mb-1 text-gray-600">
            <span className="truncate max-w-[160px]">{f.filename}</span>
            <span
              className={
                f.error
                  ? 'text-red-500'
                  : f.progress === 100
                  ? 'text-blue-500'
                  : 'text-indigo-500'
              }
            >
              {statusLabel(f)}
            </span>
          </div>
          <div className="h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-300 ${
                f.error
                  ? 'bg-red-400'
                  : f.progress === 100
                  ? 'bg-blue-400 animate-pulse'
                  : 'bg-indigo-500'
              }`}
              style={{ width: `${f.error ? 100 : f.progress}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}
