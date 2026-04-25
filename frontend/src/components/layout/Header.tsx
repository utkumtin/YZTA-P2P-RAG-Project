interface HeaderProps {
  onMenuClick: () => void
}

export default function Header({ onMenuClick }: HeaderProps) {
  return (
    <header className="h-14 bg-indigo-600 flex items-center px-4 gap-3 shadow-md flex-shrink-0">
      <button
        onClick={onMenuClick}
        className="text-white p-1 rounded hover:bg-indigo-500 transition-colors"
        aria-label="Menüyü aç/kapat"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <span className="text-white font-semibold text-lg tracking-wide">YZTA RAG</span>
    </header>
  )
}
