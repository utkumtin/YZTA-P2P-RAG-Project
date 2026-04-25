export default function StreamingIndicator() {
  return (
    <div className="flex gap-1 items-center h-5">
      <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
      <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
      <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" />
    </div>
  )
}
