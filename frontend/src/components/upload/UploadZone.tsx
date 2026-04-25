import { useRef, useState } from 'react'
import { validateFile } from '../../utils/validators'

interface UploadZoneProps {
  onFiles: (files: File[]) => void
}

export default function UploadZone({ onFiles }: UploadZoneProps) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  function handleFiles(fileList: FileList | null) {
    if (!fileList) return
    const valid = Array.from(fileList).filter((f) => validateFile(f).valid)
    if (valid.length > 0) onFiles(valid)
  }

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setDragging(true)
  }

  function handleDragLeave() {
    setDragging(false)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
      className={`
        border-2 border-dashed rounded-lg p-4 text-center cursor-pointer
        transition-colors select-none
        ${dragging
          ? 'border-indigo-500 bg-indigo-50 text-indigo-600'
          : 'border-gray-300 hover:border-indigo-400 hover:bg-gray-50 text-gray-400'
        }
      `}
    >
      <svg
        className="mx-auto mb-1 w-6 h-6"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={1.5}
          d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
        />
      </svg>
      <p className="text-xs font-medium">Dosya sürükle veya tıkla</p>
      <p className="text-[10px] mt-0.5">PDF, DOCX, DOC, TXT — maks 50 MB</p>
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.doc,.txt"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
        onClick={(e) => e.stopPropagation()}
      />
    </div>
  )
}
