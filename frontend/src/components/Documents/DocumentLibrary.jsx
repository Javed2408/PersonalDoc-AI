import Icon from '../Common/Icon.jsx'
import DocumentItem from './DocumentItem.jsx'
import UploadDropzone from './UploadDropzone.jsx'
import UploadItem from './UploadItem.jsx'

export default function DocumentLibrary({ library, selection }) {
  const { status, documents, error, uploads, deletions } = library
  const loadingFirstTime = status === 'loading' && documents.length === 0
  const allSelected = selection.selected.length === 0

  return (
    <section className="library" aria-labelledby="library-title">
      <div className="library__header">
        <h2 id="library-title" className="sidebar__title">
          Documents{documents.length > 0 && <span className="library__count">{documents.length}</span>}
        </h2>
        <button
          type="button"
          className="icon-button"
          aria-label="Refresh document list"
          title="Refresh"
          disabled={status === 'loading'}
          onClick={library.refresh}
        >
          <Icon name="refresh" size={15} />
        </button>
      </div>

      <UploadDropzone onFiles={library.upload} />

      {uploads.length > 0 && (
        <ul className="upload-list" aria-live="polite">
          {uploads.map((upload) => (
            <UploadItem
              key={upload.id}
              upload={upload}
              onRetry={library.retryUpload}
              onDismiss={library.dismissUpload}
            />
          ))}
        </ul>
      )}

      {status === 'error' && (
        <div className="library__notice library__notice--error" role="alert">
          <p>{error}</p>
          <button type="button" className="button button--small" onClick={library.refresh}>
            Try again
          </button>
        </div>
      )}

      {loadingFirstTime && <p className="library__notice">Loading documents…</p>}

      {status === 'ok' && documents.length === 0 && uploads.length === 0 && (
        <div className="library__empty">
          <p>Your document library is empty.</p>
          <p className="muted">Upload a PDF to keep it here, on this machine.</p>
        </div>
      )}

      {documents.length > 0 && (
        <div className="library__context">
          <div className="library__context-header">
            <h3 className="sidebar__title">Chat context</h3>
            <span className="library__context-summary" aria-live="polite">
              {allSelected ? 'All documents' : `${selection.selected.length} selected`}
            </span>
          </div>

          <button
            type="button"
            className={`context-all${allSelected ? ' context-all--active' : ''}`}
            aria-pressed={allSelected}
            onClick={selection.clear}
          >
            <Icon name="stack" size={16} />
            <span className="context-all__label">All processed documents</span>
            <span className="context-all__count">{selection.processed.length}</span>
          </button>

          <ul className="doc-list">
            {documents.map((document) => (
              <DocumentItem
                key={document.document_id}
                document={document}
                deletion={deletions[document.document_id]}
                onDelete={library.remove}
                selected={selection.isSelected(document.document_id)}
                onToggle={selection.toggle}
              />
            ))}
          </ul>
        </div>
      )}
    </section>
  )
}
