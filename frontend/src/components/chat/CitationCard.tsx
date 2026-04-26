import { useState } from 'react'
import type { Source } from '../../types/chat'

interface CitationCardProps {
  source: Source
  index: number
}

export default function CitationCard({ source, index }: CitationCardProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-gray-200 rounded-md text-xs overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-1.5 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <span className="shrink-0 w-5 h-5 bg-indigo-100 text-indigo-700 rounded-full flex items-center justify-center font-semibold text-[10px]">
          {index}
        </span>
        <span className="truncate text-gray-700 font-medium">{source.filename}</span>
        <span className="ml-auto text-gray-400">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-3 py-2 text-gray-600 bg-white leading-relaxed whitespace-pre-wrap">
          {source.chunk_text}
        </div>
      )}
    </div>
  )
}
