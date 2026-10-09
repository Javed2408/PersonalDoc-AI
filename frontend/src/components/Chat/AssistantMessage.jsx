import { useCallback, useMemo, useState } from 'react'
import Icon from '../Common/Icon.jsx'
import SourceList from '../Sources/SourceList.jsx'
import { citationTargets } from '../../utils/sources.js'
import AnswerText from './AnswerText.jsx'
import ThinkingIndicator from './ThinkingIndicator.jsx'

export default function AssistantMessage({ message, onRetry, retryDisabled, isDocumentAvailable }) {
  const citations = useMemo(() => citationTargets(message.sources), [message.sources])
  // The chunk an inline citation last pointed at. `request` changes on every click, so clicking the
  // same citation again still brings its source back into view.
  const [target, setTarget] = useState(null)
  const showSource = useCallback(
    (source) => setTarget((prev) => ({ chunkId: source.chunk_id, request: (prev?.request ?? 0) + 1 })),
    [],
  )

  return (
    <article className={`message message--assistant message--${message.status}`} aria-label="Answer">
      {message.status === 'pending' && <ThinkingIndicator />}

      {message.status === 'error' && (
        <div className="message__error" role="alert">
          <Icon name="alert" size={16} />
          <div className="message__error-body">
            <p className="message__error-title">{message.error.title}</p>
            {message.error.message && <p>{message.error.message}</p>}
            <button
              type="button"
              className="button button--small"
              onClick={() => onRetry(message.id)}
              disabled={retryDisabled}
            >
              Retry
            </button>
          </div>
        </div>
      )}

      {message.status === 'not_found' && (
        <div className="message__not-found">
          <Icon name="info" size={16} />
          <div>
            <AnswerText text={message.answer} />
            <p className="message__hint">Try rephrasing the question, or choose different documents.</p>
          </div>
        </div>
      )}

      {message.status === 'answered' && (
        <>
          <AnswerText text={message.answer} citations={citations} onCite={showSource} />
          <SourceList
            messageId={message.id}
            sources={message.sources}
            target={target}
            isDocumentAvailable={isDocumentAvailable}
          />
          {message.model && <p className="message__model">Answered locally by {message.model}</p>}
        </>
      )}
    </article>
  )
}
