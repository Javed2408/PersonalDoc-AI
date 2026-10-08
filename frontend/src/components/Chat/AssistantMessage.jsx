import Icon from '../Common/Icon.jsx'
import SourceList from '../Sources/SourceList.jsx'
import AnswerText from './AnswerText.jsx'
import ThinkingIndicator from './ThinkingIndicator.jsx'

export default function AssistantMessage({ message, onRetry, retryDisabled }) {
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
          <AnswerText text={message.answer} />
          <SourceList sources={message.sources} />
          {message.model && <p className="message__model">Answered locally by {message.model}</p>}
        </>
      )}
    </article>
  )
}
