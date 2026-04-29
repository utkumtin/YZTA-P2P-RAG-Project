import { useState, useRef, useCallback, useEffect } from 'react';

export interface SSEEvent {
  type: string;
  data: unknown;
}

export interface SSEOptions {
  method?: 'GET' | 'POST';
  body?: unknown;
  onMessage: (event: SSEEvent) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  onClose?: () => void;
  maxRetries?: number;
}

export interface SSEState {
  isConnected: boolean;
  error: Error | null;
  connect: (url: string, options: SSEOptions) => void;
  disconnect: () => void;
}

export function useSSE(): SSEState {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const retryCountRef = useRef(0);
  const retryTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const disconnect = useCallback(() => {
    if (retryTimeoutRef.current) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const connect = useCallback((url: string, options: SSEOptions) => {
    const { method = 'GET', body, onMessage, onError, onOpen, onClose, maxRetries = 3 } = options;

    disconnect();
    retryCountRef.current = 0;

    const attemptConnect = async () => {
      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const fetchOptions: RequestInit = {
          method,
          signal: controller.signal,
          headers: {
            Accept: 'text/event-stream',
            'Cache-Control': 'no-cache',
            ...(body ? { 'Content-Type': 'application/json' } : {}),
          },
          ...(body ? { body: JSON.stringify(body) } : {}),
        };

        const response = await fetch(url, fetchOptions);

        if (!response.ok) {
          throw new Error(`SSE bağlantı hatası: ${response.status} ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error('Response body boş');
        }

        setIsConnected(true);
        setError(null);
        retryCountRef.current = 0;
        onOpen?.();

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        try {
          while (true) {
            const { done, value } = await reader.read();

            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const line of lines) {
              const trimmed = line.trim();
              if (!trimmed || trimmed.startsWith(':')) continue;

              if (trimmed.startsWith('data:')) {
                const rawData = trimmed.slice(5).trim();
                try {
                  const parsed = JSON.parse(rawData);
                  onMessage({ type: parsed.type ?? 'message', data: parsed });
                } catch {
                  onMessage({ type: 'message', data: rawData });
                }
              }
            }
          }
        } finally {
          reader.cancel();
        }

        setIsConnected(false);
        onClose?.();
      } catch (err) {
        if ((err as Error).name === 'AbortError') {
          return;
        }

        const connError = err instanceof Error ? err : new Error(String(err));
        setIsConnected(false);

        if (retryCountRef.current < maxRetries) {
          const delay = 60 * Math.pow(2, retryCountRef.current);
          retryCountRef.current++;
          retryTimeoutRef.current = setTimeout(attemptConnect, delay);
        } else {
          setError(connError);
          onError?.(connError);
          onClose?.();
        }
      }
    };

    attemptConnect();
  }, [disconnect]);

  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return { isConnected, error, connect, disconnect };
}
