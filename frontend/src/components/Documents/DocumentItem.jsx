import { useState } from 'react'
import Icon from '../Common/Icon.jsx'
import { formatBytes, formatDate } from '../../utils/format.js'

// "Processed" = text extracted, chunked and embedded into the local vector index.
const STATUS_LABELS = {
  uploaded: 'Uploaded',
  processing: 'Processing…',
  processed: 'Processed',
  failed: 'Failed',
}

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

export default function DocumentItem({ document, deletion, onDelete, selected, onToggle }) {
  const [confirming, setConfirming] = useState(false)
  const deleting = deletion?.status === 'deleting'
  const name = document.original_filename
  const id = document.document_id
  // Only processed documents are in the vector index, so only they can be chat context.
  const selectable = document.status === 'processed' && !deleting

  const classes = ['doc-item']
  if (selected) classes.push('doc-item--selected')
  if (document.status !== 'processed') classes.push('doc-item--unavailable')

  return (
    <li className={classes.join(' ')} aria-busy={deleting}>
      <input
        id={`doc-select-${id}`}
        type="checkbox"
        className="doc-item__check"
        checked={selected}
        disabled={!selectable}
        aria-label={`Ask about ${name}`}
        aria-describedby={`doc-status-${id}`}
        onChange={() => onToggle(id)}
      />
      <div className="doc-item__body">
        <label htmlFor={`doc-select-${id}`} className="doc-item__name" title={name}>
          {name}
        </label>
        <span className="doc-item__meta">
          {document.file_type.toUpperCase()} · {formatBytes(document.file_size)} · {formatDate(document.created_at)}
        </span>
        <span className="doc-item__status" id={`doc-status-${id}`}>
          <span className={`badge badge--${document.status}`}>
            {document.status === 'processing' && <span className="spinner" aria-hidden="true" />}
            {STATUS_LABELS[document.status] ?? document.status}
          </span>
          {(document.status === 'uploaded' || document.status === 'processing') && (
            <span className="doc-item__meta">Available for chat once processed</span>
          )}
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
