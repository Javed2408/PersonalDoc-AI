import Icon from '../Common/Icon.jsx'

/** Explains a backend or local-model problem reported by the health check, with a way to re-check. */
export default function ServiceNotice({ service, onRetry }) {
  if (!service.problem) return null

  let title
  let message
  if (service.problem === 'backend') {
    title = "Can't reach the backend"
    message = 'Start the API server (see the README), then check again.'
  } else if (service.problem === 'model_missing') {
    title = 'The local model isn’t installed'
    message = (
      <>
        Install it with <code>ollama pull {service.model}</code>, then check again.
      </>
    )
  } else {
    title = 'Local AI is unavailable'
    message = 'Make sure Ollama is running, then check again. Your documents are still available.'
  }

  return (
    <div className="service-notice" role="status">
      <Icon name="alert" size={16} />
      <div className="service-notice__body">
        <p className="service-notice__title">{title}</p>
        <p>{message}</p>
      </div>
      <button type="button" className="button button--small" onClick={onRetry}>
        Check again
      </button>
    </div>
  )
}
