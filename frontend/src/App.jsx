import { useCallback, useRef, useState } from 'react'
import Header from './components/Layout/Header.jsx'
import Sidebar from './components/Layout/Sidebar.jsx'
import ChatPanel from './components/Chat/ChatPanel.jsx'
import { useChat } from './hooks/useChat.js'
import { useDocuments } from './hooks/useDocuments.js'
import { useDocumentSelection } from './hooks/useDocumentSelection.js'
import { useHealth } from './hooks/useHealth.js'
import { serviceStatus } from './utils/status.js'

// Errors that may mean the backend or Ollama changed state: worth a fresh health check.
const SERVICE_ERROR_STATUSES = new Set([502, 503, 504])

export default function App() {
  const health = useHealth()
  const library = useDocuments()
  const selection = useDocumentSelection(library.documents)
  const service = serviceStatus(health)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const composerRef = useRef(null)

  const chat = useChat({
    onSettled: ({ error }) => {
      if (error) {
        if (error.unreachable || SERVICE_ERROR_STATUSES.has(error.status)) health.retry()
        // A selected document was deleted or changed state elsewhere: show the current list.
        if (error.status === 404 || error.status === 409) library.refresh()
      } else if (service.problem) {
        // An answer arrived, so a reported problem may have been fixed.
        health.retry()
      }
    },
  })

  const recheck = useCallback(() => {
    health.retry()
    if (library.status === 'error') library.refresh()
  }, [health, library])

  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  const startNewChat = useCallback(() => {
    chat.clear()
    composerRef.current?.focus()
  }, [chat])

  return (
    <div className="app-shell">
      <Header
        service={service}
        drawerOpen={drawerOpen}
        onToggleDrawer={() => setDrawerOpen((open) => !open)}
        selectedCount={selection.selected.length}
        onNewChat={startNewChat}
        canStartNewChat={chat.messages.length > 0}
      />
      <div className="app-body">
        <Sidebar open={drawerOpen} onClose={closeDrawer} library={library} selection={selection} />
        <ChatPanel
          chat={chat}
          selection={selection}
          library={library}
          service={service}
          onRecheck={recheck}
          onChooseDocuments={() => setDrawerOpen(true)}
          composerRef={composerRef}
        />
      </div>
    </div>
  )
}
