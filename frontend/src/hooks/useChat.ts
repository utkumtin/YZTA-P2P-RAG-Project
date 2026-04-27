import { useState, useCallback, useRef, useEffect } from 'react';
import { useSSE } from './useSSE';
import { useChatStore } from '../store/chatStore';
import { getSessionId } from '../utils/session';
import { SSE_EVENT_TYPES } from '../utils/constants';
import type { Source } from '../types/chat';

export type SourceInfo = Source;

export type { Message } from '../types/chat';

export interface UseChatReturn {
  messages: ReturnType<typeof useChatStore.getState>['messages'];
  isStreaming: boolean;
  error: string | null;
  sendMessage: (question: string) => void;
  clearMessages: () => void;
}

// Token animation: drain 15 chars every 25ms → ~600 chars/sec
const DRAIN_CHARS = 15;
const DRAIN_INTERVAL_MS = 25;

export function useChat(documentIds?: string[]): UseChatReturn {
  const messages = useChatStore((s) => s.messages);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { connect, disconnect } = useSSE();
  const streamingMessageIdRef = useRef<string | null>(null);
  const isTypewritingRef = useRef<boolean>(false);
  const typewritingIntervalRef = useRef<number | null>(null);
  const pendingSourcesRef = useRef<SourceInfo[] | null>(null);

  // Token animation queue
  const pendingTokensRef = useRef<string>('');
  const drainIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const streamDoneRef = useRef<boolean>(false);

  const setMessages = useCallback(
    (updater: (prev: ReturnType<typeof useChatStore.getState>['messages']) => ReturnType<typeof useChatStore.getState>['messages']) => {
      useChatStore.setState((state) => ({ messages: updater(state.messages) }));
    },
    [],
  );

  const stopDrain = useCallback(() => {
    if (drainIntervalRef.current) {
      clearInterval(drainIntervalRef.current);
      drainIntervalRef.current = null;
    }
  }, []);

  const startDrain = useCallback(() => {
    if (drainIntervalRef.current) return;
    drainIntervalRef.current = setInterval(() => {
      if (pendingTokensRef.current.length === 0) {
        if (streamDoneRef.current) {
          stopDrain();
          const id = streamingMessageIdRef.current;
          if (id) {
            setMessages((prev) =>
              prev.map((msg) => (msg.id === id ? { ...msg, isStreaming: false } : msg))
            );
            streamingMessageIdRef.current = null;
            setIsStreaming(false);
          }
          streamDoneRef.current = false;
        }
        return;
      }
      const chunk = pendingTokensRef.current.slice(0, DRAIN_CHARS);
      pendingTokensRef.current = pendingTokensRef.current.slice(DRAIN_CHARS);
      const id = streamingMessageIdRef.current;
      if (id) {
        setMessages((prev) =>
          prev.map((msg) => (msg.id === id ? { ...msg, content: msg.content + chunk } : msg))
        );
      }
    }, DRAIN_INTERVAL_MS);
  }, [stopDrain, setMessages]);

  const flushDrain = useCallback(() => {
    stopDrain();
    const remaining = pendingTokensRef.current;
    pendingTokensRef.current = '';
    streamDoneRef.current = false;
    const id = streamingMessageIdRef.current;
    if (remaining && id) {
      setMessages((prev) =>
        prev.map((msg) => (msg.id === id ? { ...msg, content: msg.content + remaining } : msg))
      );
    }
  }, [stopDrain, setMessages]);

  const clearTypewriter = useCallback(() => {
    if (typewritingIntervalRef.current) {
      clearInterval(typewritingIntervalRef.current as number);
      typewritingIntervalRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => {
      clearTypewriter();
      stopDrain();
    };
  }, [clearTypewriter, stopDrain]);

  const sendMessage = useCallback((question: string) => {
    if (isStreaming) return;

    clearTypewriter();
    stopDrain();
    pendingTokensRef.current = '';
    streamDoneRef.current = false;
    pendingSourcesRef.current = null;

    const userMessage = {
      id: crypto.randomUUID?.() ?? Date.now().toString(),
      role: 'user' as const,
      content: question,
    };

    const assistantMessageId = crypto.randomUUID?.() ?? (Date.now() + 1).toString();
    const assistantMessage = {
      id: assistantMessageId,
      role: 'assistant' as const,
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
          pendingTokensRef.current += payload.content;
          startDrain();
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
                        sources: pendingSourcesRef.current || msg.sources,
                      }
                    : msg
                )
              );

              if (streamingMessageIdRef.current === targetId) {
                streamingMessageIdRef.current = null;
                setIsStreaming(false);
              }
            }
          }, ITERATION_MS) as unknown as number;
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
          // Mark done; drain interval will finalize the message when queue empties
          streamDoneRef.current = true;
          disconnect();
        } else if (payload.type === SSE_EVENT_TYPES.ERROR) {
          const errMsg = (payload as { type: string; message?: string }).message ?? 'Bilinmeyen hata';
          flushDrain();
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
        flushDrain();
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
          flushDrain();
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
  }, [isStreaming, documentIds, connect, disconnect, setMessages, startDrain, stopDrain, flushDrain, clearTypewriter]);

  const clearMessages = useCallback(() => {
    disconnect();
    clearTypewriter();
    flushDrain();
    streamingMessageIdRef.current = null;
    useChatStore.setState({ messages: [] });
    setIsStreaming(false);
    setError(null);
  }, [disconnect, clearTypewriter, flushDrain]);

  return { messages, isStreaming, error, sendMessage, clearMessages };
}
