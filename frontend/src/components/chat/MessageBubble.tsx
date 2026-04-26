import type { Message } from '../../types/chat'
import StreamingIndicator from './StreamingIndicator'
import CitationCard from './CitationCard'

interface MessageBubbleProps {
  message: Message
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-3`}>
      <div className={`max-w-[85vw] md:max-w-2xl flex flex-col gap-2 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? 'bg-indigo-600 text-white rounded-br-sm'
              : 'bg-slate-100 text-slate-800 rounded-bl-sm'
          }`}
        >
          {message.content || (message.isStreaming ? <StreamingIndicator /> : null)}
          
          {message.isCached && !isUser && (
            <span className="inline-flex items-center gap-1 text-[10px] ml-2 text-indigo-400 font-medium" title="Önbellekten hızlı yanıt">
              (⚡ Hızlı)
            </span>
          )}

          {message.isStreaming && message.content && (
            <span className="inline-block w-0.5 h-4 bg-current ml-0.5 animate-pulse align-middle" />
          )}
        </div>

        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="w-full flex flex-col gap-1">
            {message.sources.map((src, i) => (
              <CitationCard key={src.document_id + i} source={src} index={i + 1} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
