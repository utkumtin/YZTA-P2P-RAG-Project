import { create } from 'zustand'
import type { Message, Source } from '../types/chat'

interface ChatStore {
  messages: Message[]
  isStreaming: boolean
  sessionId: string
  addMessage: (msg: Message) => void
  appendToken: (id: string, token: string) => void
  setSources: (id: string, sources: Source[]) => void
  setStreaming: (id: string, val: boolean) => void
  setIsStreaming: (val: boolean) => void
  clearMessages: () => void
}

export const useChatStore = create<ChatStore>((set) => ({
  messages: [],
  isStreaming: false,
  sessionId: crypto.randomUUID(),

  addMessage: (msg) =>
    set((state) => ({ messages: [...state.messages, msg] })),

  appendToken: (id, token) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, content: m.content + token } : m
      ),
    })),

  setSources: (id, sources) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, sources } : m
      ),
    })),

  setStreaming: (id, val) =>
    set((state) => ({
      messages: state.messages.map((m) =>
        m.id === id ? { ...m, isStreaming: val } : m
      ),
    })),

  setIsStreaming: (val) => set({ isStreaming: val }),

  clearMessages: () => set({ messages: [], isStreaming: false }),
}))
