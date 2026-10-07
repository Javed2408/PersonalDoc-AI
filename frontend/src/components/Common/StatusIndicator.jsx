const LABELS = {
  loading: 'Checking…',
  ok: 'Local / Ready',
  error: 'Backend offline',
}

export default function StatusIndicator({ status }) {
  return (
    <span className={`status-indicator status-indicator--${status}`}>
      <span className="status-indicator__dot" aria-hidden="true" />
      {LABELS[status]}
    </span>
  )
}
