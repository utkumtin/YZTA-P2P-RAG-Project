import { useEffect } from 'react'
import { useUIStore, Toast as ToastType } from '../../store/uiStore'

const colorMap: Record<ToastType['type'], string> = {
  success: 'bg-green-500',
  error: 'bg-red-500',
  info: 'bg-indigo-500',
}

function ToastItem({ toast }: { toast: ToastType }) {
  const removeToast = useUIStore((s) => s.removeToast)

  useEffect(() => {
    const timer = setTimeout(() => removeToast(toast.id), toast.duration ?? 4000)
    return () => clearTimeout(timer)
  }, [toast.id, toast.duration, removeToast])

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-lg text-white shadow-lg text-sm ${colorMap[toast.type]}`}
    >
      <span className="flex-1">{toast.message}</span>
      <button
        onClick={() => removeToast(toast.id)}
        className="opacity-70 hover:opacity-100 transition-opacity"
      >
        ✕
      </button>
    </div>
  )
}

export default function Toast() {
  const toasts = useUIStore((s) => s.toasts)

  if (toasts.length === 0) return null

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80">
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} />
      ))}
    </div>
  )
}
