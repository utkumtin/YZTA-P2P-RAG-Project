import { useState, useCallback, useRef, useEffect } from 'react';
import { useSSE } from './useSSE';
import { getSessionId } from '../utils/session';
import { SSE_EVENT_TYPES } from '../utils/constants';

export interface SourceInfo {
  document_id: string;
  filename: string;
  chunk_text: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: SourceInfo[];
  isStreaming?: boolean;
  isCached?: boolean;
}

export interface UseChatReturn {
  messages: Message[];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (question: string) => void;
  clearMessages: () => void;
}

export function useChat(documentIds?: string[]): UseChatReturn {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { connect, disconnect } = useSSE();
  const streamingMessageIdRef = useRef<string | null>(null);
  const isTypewritingRef = useRef<boolean>(false);
  const typewritingIntervalRef = useRef<number | NodeJS.Timeout | null>(null);
  const pendingSourcesRef = useRef<SourceInfo[] | null>(null);

  const clearTypewriter = useCallback(() => {
    if (typewritingIntervalRef.current) {
      clearInterval(typewritingIntervalRef.current as number);
      typewritingIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      clearTypewriter();
    };
  }, [clearTypewriter]);

  const sendMessage = useCallback((question: string) => {
    if (isStreaming) return;

    clearTypewriter();
    pendingSourcesRef.current = null;

    const userMessage: Message = {
      id: crypto.randomUUID?.() ?? Date.now().toString(),
      role: 'user',
      content: question,
    };

    const assistantMessageId = crypto.randomUUID?.() ?? (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    };

    streamingMessageIdRef.current = assistantMessageId;
    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    setIsStreaming(true);
    setError(null);

    connect('/api/routes/chat/stream', {
      method: 'POST',
      body: {
        question,
        session_id: getSessionId(),
        document_ids: documentIds ?? null,
      },
      onMessage: ({ data }) => {
        const payload = data as { type: string; content?: string; documents?: SourceInfo[] };

        if (payload.type === SSE_EVENT_TYPES.TOKEN && payload.content !== undefined) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamingMessageIdRef.current
                ? { ...msg, content: msg.content + payload.content }
                : msg
            )
          );
        } else if (payload.type === SSE_EVENT_TYPES.CACHE_HIT && payload.content !== undefined) {
          isTypewritingRef.current = true;
          const text = payload.content;
          const targetId = streamingMessageIdRef.current;
          
          const TARGET_DURATION_MS = 800;
          const ITERATION_MS = 25; 
          const steps = Math.ceil(TARGET_DURATION_MS / ITERATION_MS); 
          const chunkSize = Math.max(1, Math.floor(text.length / steps));

          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === targetId ? { ...msg, isCached: true } : msg
            )
          );

          let currentLength = 0;
          typewritingIntervalRef.current = setInterval(() => {
            currentLength += chunkSize;
            const chunk = text.slice(0, currentLength);
            
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === targetId ? { ...msg, content: chunk } : msg
              )
            );

            if (currentLength >= text.length) {
              clearTypewriter();
              isTypewritingRef.current = false;
              
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === targetId 
                    ? { 
                        ...msg, 
                        isStreaming: false,
                        sources: pendingSourcesRef.current || msg.sources 
                      } 
                    : msg
                )
              );

              if (streamingMessageIdRef.current === targetId) {
                streamingMessageIdRef.current = null;
                setIsStreaming(false);
              }
            }
          }, ITERATION_MS);
        } else if (payload.type === SSE_EVENT_TYPES.SOURCES && payload.documents) {
          if (isTypewritingRef.current) {
            pendingSourcesRef.current = payload.documents;
          } else {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === streamingMessageIdRef.current
                  ? { ...msg, sources: payload.documents }
                  : msg
              )
            );
          }
        } else if (payload.type === SSE_EVENT_TYPES.DONE) {
          if (!isTypewritingRef.current) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === streamingMessageIdRef.current
                  ? { ...msg, isStreaming: false }
                  : msg
              )
            );
            streamingMessageIdRef.current = null;
            setIsStreaming(false);
          }
          disconnect();
        } else if (payload.type === SSE_EVENT_TYPES.ERROR) {
          const errMsg = (payload as { type: string; message?: string }).message ?? 'Bilinmeyen hata';
          if (!isTypewritingRef.current) {
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === streamingMessageIdRef.current
                  ? { ...msg, isStreaming: false, content: msg.content || errMsg }
                  : msg
              )
            );
            streamingMessageIdRef.current = null;
            setIsStreaming(false);
          }
          setError(errMsg);
          disconnect();
        }
      },
      onError: (err) => {
        if (!isTypewritingRef.current) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamingMessageIdRef.current
                ? { ...msg, isStreaming: false }
                : msg
            )
          );
          streamingMessageIdRef.current = null;
          setIsStreaming(false);
        }
        setError(err.message);
      },
      onClose: () => {
        if (streamingMessageIdRef.current && !isTypewritingRef.current) {
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === streamingMessageIdRef.current
                ? { ...msg, isStreaming: false }
                : msg
            )
          );
          streamingMessageIdRef.current = null;
          setIsStreaming(false);
        }
      },
    });
  }, [isStreaming, documentIds, connect, disconnect]);

  const clearMessages = useCallback(() => {
    disconnect();
    streamingMessageIdRef.current = null;
    setMessages([]);
    setIsStreaming(false);
    setError(null);
  }, [disconnect]);

  return { messages, isStreaming, error, sendMessage, clearMessages };
}
