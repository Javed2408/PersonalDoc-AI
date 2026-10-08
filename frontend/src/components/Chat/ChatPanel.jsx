import { useCallback, useEffect, useRef } from 'react'
import { describeContext } from '../../hooks/useDocumentSelection.js'
import ChatEmptyState from './ChatEmptyState.jsx'
import Composer from './Composer.jsx'
import ContextBar from './ContextBar.jsx'
import MessageList from './MessageList.jsx'
import ServiceNotice from './ServiceNotice.jsx'

function composerPlaceholder(library, processedCount) {
  if (library.status === 'loading' && library.documents.length === 0) return 'Loading your documents…'
  if (library.documents.length === 0) return 'Upload a PDF to start asking questions'
  if (processedCount === 0) return 'Waiting for a document to finish processing…'
  return 'Ask something about your documents…'
}

// How close to the end still counts as "reading the latest message".
const BOTTOM_SLACK_PX = 48

/**
 * When the conversation area shrinks (a notice appears above the composer, the composer grows,
 * a phone keyboard opens), keep a reader who was at the end of the conversation at the end.
 */
function useStickToBottom(scrollRef) {
  useEffect(() => {
    const element = scrollRef.current
    if (!element || typeof ResizeObserver === 'undefined') return undefined
    let atBottom = true
    const onScroll = () => {
      atBottom = element.scrollHeight - element.scrollTop - element.clientHeight < BOTTOM_SLACK_PX
    }
    const observer = new ResizeObserver(() => {
      if (atBottom) element.scrollTop = element.scrollHeight
    })
    element.addEventListener('scroll', onScroll, { passive: true })
    observer.observe(element)
    return () => {
      element.removeEventListener('scroll', onScroll)
      observer.disconnect()
    }
  }, [scrollRef])
}

export default function ChatPanel({ chat, selection, library, service, onRecheck, onChooseDocuments, composerRef }) {
  const processedCount = selection.processed.length
  const canAsk = processedCount > 0
  const { selected } = selection
  const { retry: retryChat } = chat
  const scrollRef = useRef(null)
  useStickToBottom(scrollRef)

  const handleRetry = useCallback(
    (answerId) => retryChat(answerId, describeContext(selected, processedCount)),
    [retryChat, selected, processedCount],
  )

  return (
    <main className="chat" aria-label="Chat">
      <div className="chat__scroll" ref={scrollRef}>
        <div className="chat__column">
          {chat.messages.length === 0 ? (
            <ChatEmptyState
              library={library}
              selection={selection}
              onExample={(text) => composerRef.current?.fill(text)}
            />
          ) : (
            <MessageList messages={chat.messages} onRetry={handleRetry} pending={chat.pending} />
          )}
        </div>
      </div>

      <div className="chat__footer">
        <div className="chat__column">
          {/* Next to the composer, outside the scrolling conversation, so it never pushes messages away. */}
          <ServiceNotice service={service} onRetry={onRecheck} />
          {library.documents.length > 0 && <ContextBar selection={selection} onChooseDocuments={onChooseDocuments} />}
          <Composer
            ref={composerRef}
            pending={chat.pending}
            disabled={!canAsk}
            placeholder={composerPlaceholder(library, processedCount)}
            onSubmit={(text) => chat.send(text, describeContext(selected, processedCount))}
          />
          <p id="composer-hint" className="chat__hint">
            Enter to send · Shift + Enter for a new line · Answers use only your documents
          </p>
        </div>
      </div>
    </main>
  )
}
