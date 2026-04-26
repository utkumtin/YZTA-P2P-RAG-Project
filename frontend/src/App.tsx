import { useState, useEffect } from 'react'
import Header from './components/layout/Header'
import Sidebar from './components/layout/Sidebar'
import ChatWindow from './components/chat/ChatWindow'
import MessageInput from './components/chat/MessageInput'
import Toast from './components/ui/Toast'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(() => window.innerWidth >= 768)

  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth >= 768) {
        setSidebarOpen(true)
      } else {
        setSidebarOpen(false)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className="flex flex-col h-full">
      <Header onMenuClick={() => setSidebarOpen(prev => !prev)} />
      <div className="flex flex-1 overflow-hidden relative">
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/40 z-10 md:hidden"
            onClick={() => setSidebarOpen(false)}
          />
        )}
        <Sidebar open={sidebarOpen} />
        <main className="flex flex-col flex-1 overflow-hidden bg-white">
          <ChatWindow />
          <MessageInput />
        </main>
      </div>
      <Toast />
    </div>
  )
}
