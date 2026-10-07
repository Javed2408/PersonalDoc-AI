import StatusIndicator from './StatusIndicator.jsx'

export default function BackendStatusCard({ status, data, error, retry }) {
  return (
    <section className="card" aria-labelledby="backend-status-title" aria-live="polite">
      <div className="card__header">
        <h2 id="backend-status-title">Backend</h2>
        <StatusIndicator status={status} />
      </div>

      {status === 'loading' && <p className="muted">Contacting the API…</p>}

      {status === 'ok' && data && (
        <dl className="meta-list">
          <div>
            <dt>Service</dt>
            <dd>{data.app_name}</dd>
          </div>
          <div>
            <dt>Version</dt>
            <dd>{data.version}</dd>
          </div>
          <div>
            <dt>Environment</dt>
            <dd>{data.environment}</dd>
          </div>
        </dl>
      )}

      {status === 'error' && (
        <div className="card__error">
          <p>{error}</p>
          <p className="muted">Start it with the backend command in the README, then try again.</p>
          <button type="button" className="button" onClick={retry}>
            Retry connection
          </button>
        </div>
      )}
    </section>
  )
}
