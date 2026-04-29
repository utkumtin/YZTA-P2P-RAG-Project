import { useState, useEffect, useMemo } from 'react'
import { useChatStore } from './store/chatStore'
import Header from './components/layout/Header'
import Sidebar from './components/layout/Sidebar'
import ChatWindow from './components/chat/ChatWindow'
import MessageInput from './components/chat/MessageInput'
import Inspector from './components/chat/Inspector'
import Toast from './components/ui/Toast'
import type { Source } from './types/chat'

export default function App() {
  const [vw, setVw] = useState(window.innerWidth)
  const [inspectorOpen, setInspectorOpen] = useState(true)
  const [userToggled, setUserToggled] = useState(false)
  const [hoverSrc, setHoverSrc] = useState<Source | null>(null)

  const messages = useChatStore(s => s.messages)
  const clearMessages = useChatStore(s => s.clearMessages)

  // Global kaynak indeks haritası: document_id → sohbet geneli sıra numarası
  const sourceRegistry = useMemo(() => {
    const registry = new Map<string, number>()
    let counter = 1
    for (const msg of messages) {
      for (const src of msg.sources ?? []) {
        const key = src.document_id || src.filename
        if (!registry.has(key)) registry.set(key, counter++)
      }
    }
    return registry
  }, [messages])

  useEffect(() => {
    const onR = () => setVw(window.innerWidth)
    window.addEventListener('resize', onR)
    return () => window.removeEventListener('resize', onR)
  }, [])

  const narrow = vw < 1180
  const veryNarrow = vw < 900

  useEffect(() => {
    if (!userToggled) setInspectorOpen(!narrow)
  }, [narrow, userToggled])

  const inspectorAsDrawer = narrow && inspectorOpen
  const inspectorInline = !narrow && inspectorOpen

  const toggle = () => { setUserToggled(true); setInspectorOpen(o => !o) }

  const sidebarW = veryNarrow ? '0px' : vw < 1024 ? '240px' : '272px'
  const inspectorW = inspectorInline ? (vw < 1280 ? '300px' : '340px') : '0px'

  return (
    <div style={{
      height: '100vh', width: '100vw',
      display: 'grid', gridTemplateRows: '52px 1fr',
      background: 'var(--bg)', color: '#fff', fontFamily: 'var(--sans)',
      overflow: 'hidden',
    }}>
      <Header inspectorOpen={inspectorOpen} onToggleInspector={toggle} onClear={clearMessages} />

      <div style={{
        display: 'grid',
        gridTemplateColumns: `${sidebarW} minmax(0,1fr) ${inspectorW}`,
        minHeight: 0,
      }}>
        {!veryNarrow && <Sidebar />}

        <div style={{ display: 'grid', gridTemplateRows: '1fr auto', minHeight: 0, overflow: 'hidden' }}>
          <ChatWindow setHoverSrc={setHoverSrc} sourceRegistry={sourceRegistry} />
          <MessageInput />
        </div>

        {inspectorInline && (
          <Inspector hoverSrc={hoverSrc} messages={messages} sourceRegistry={sourceRegistry} onClose={toggle} />
        )}
      </div>

      {inspectorAsDrawer && (
        <>
          <div
            onClick={toggle}
            style={{ position: 'fixed', inset: 0, zIndex: 8, background: 'rgba(0,0,0,.5)' }}
          />
          <div style={{
            position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 9,
            width: Math.min(360, vw - 40),
            boxShadow: '-12px 0 32px rgba(0,0,0,.4)',
            animation: 'yz-slide .22s ease-out',
          }}>
            <Inspector hoverSrc={hoverSrc} messages={messages} sourceRegistry={sourceRegistry} onClose={toggle} />
          </div>
        </>
      )}

      <Toast />
    </div>
  )
}
