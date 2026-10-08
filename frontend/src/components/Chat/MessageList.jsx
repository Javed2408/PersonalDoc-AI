import { memo, useEffect, useRef } from 'react'
import AssistantMessage from './AssistantMessage.jsx'
import UserMessage from './UserMessage.jsx'

const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// Memoised: typing in the composer doesn't re-render the conversation.
function MessageList({ messages, onRetry, pending }) {
  const listRef = useRef(null)
  const last = messages[messages.length - 1]

  // Keep the latest question at the top of the view, so its answer reads from the start.
  useEffect(() => {
    if (!last) return
    const questionId = last.role === 'assistant' ? last.questionId : last.id
    const element = listRef.current?.querySelector(`[data-message-id="${questionId}"]`)
    element?.scrollIntoView?.({ block: 'start', behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
  }, [last?.id, last?.status, last?.questionId])

  return (
    <div role="log" aria-label="Conversation" className="messages-log">
      <ol ref={listRef} className="messages">
        {messages.map((message) => (
          <li key={message.id} data-message-id={message.id}>
            {message.role === 'user' ? (
              <UserMessage message={message} />
            ) : (
              <AssistantMessage message={message} onRetry={onRetry} retryDisabled={pending} />
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}

export default memo(MessageList)
