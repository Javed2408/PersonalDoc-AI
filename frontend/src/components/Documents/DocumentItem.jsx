import { useState } from 'react'
import Icon from '../Common/Icon.jsx'
import { formatBytes, formatDate } from '../../utils/format.js'

// "Processed" = text extracted and chunked. Nothing here is indexed/searchable yet.
const STATUS_LABELS = {
  uploaded: 'Uploaded',
  processing: 'Processing…',
  processed: 'Processed',
  failed: 'Failed',
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

export default function DocumentItem({ document, deletion, onDelete }) {
  const [confirming, setConfirming] = useState(false)
  const deleting = deletion?.status === 'deleting'
  const name = document.original_filename

  return (
    <li className="doc-item" aria-busy={deleting}>
      <Icon name="file" size={18} />
      <div className="doc-item__body">
        <span className="doc-item__name" title={name}>
          {name}
        </span>
        <span className="doc-item__meta">
          {document.file_type.toUpperCase()} · {formatBytes(document.file_size)} · {formatDate(document.created_at)}
        </span>
        <span className="doc-item__status">
          <span className={`badge badge--${document.status}`}>
            {document.status === 'processing' && <span className="spinner" aria-hidden="true" />}
            {STATUS_LABELS[document.status] ?? document.status}
          </span>
          {document.status === 'processed' && document.page_count != null && (
            <span className="doc-item__meta">
              {plural(document.page_count, 'page')} · {plural(document.chunk_count, 'chunk')}
            </span>
          )}
        </span>

        {document.status === 'failed' && document.processing_error && (
          <p className="doc-item__error">{document.processing_error}</p>
        )}

        {deletion?.status === 'failed' && <p className="doc-item__error">{deletion.error}</p>}

        {confirming && (
          <div
            className="doc-item__confirm"
            onKeyDown={(event) => event.key === 'Escape' && setConfirming(false)}
          >
            <span>Delete this document?</span>
            <button
              type="button"
              className="button button--small button--danger"
              disabled={deleting}
              autoFocus
              onClick={async () => {
                await onDelete(document.document_id)
                setConfirming(false)
              }}
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
            <button
              type="button"
              className="button button--small"
              disabled={deleting}
              onClick={() => setConfirming(false)}
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {!confirming && (
        <button
          type="button"
          className="icon-button icon-button--danger"
          aria-label={`Delete ${name}`}
          onClick={() => setConfirming(true)}
        >
          <Icon name="trash" size={15} />
        </button>
      )}
    </li>
  )
}
