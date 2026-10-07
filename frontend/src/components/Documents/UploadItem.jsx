import Icon from '../Common/Icon.jsx'

const LABELS = {
  uploading: 'Uploading…',
  uploaded: 'Uploaded',
  failed: 'Upload failed',
}

export default function UploadItem({ upload, onRetry, onDismiss }) {
  return (
    <li className={`upload-item upload-item--${upload.status}`}>
      <div className="upload-item__row">
        <span className="upload-item__name" title={upload.name}>
          {upload.name}
        </span>
        <span className="upload-item__state">
          {upload.status === 'uploading' && <span className="spinner" aria-hidden="true" />}
          {LABELS[upload.status]}
        </span>
      </div>

      {upload.status === 'failed' && (
        <>
          <p className="upload-item__error">{upload.error}</p>
          <div className="upload-item__actions">
            <button type="button" className="button button--small" onClick={() => onRetry(upload.id)}>
              Retry
            </button>
            <button
              type="button"
              className="icon-button"
              aria-label={`Dismiss failed upload of ${upload.name}`}
              onClick={() => onDismiss(upload.id)}
            >
              <Icon name="close" size={14} />
            </button>
          </div>
        </>
      )}
    </li>
  )
}
