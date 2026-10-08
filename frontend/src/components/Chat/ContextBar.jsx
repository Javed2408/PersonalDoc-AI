import Icon from '../Common/Icon.jsx'

/** Always shows which documents the next question will be answered from. */
export default function ContextBar({ selection, onChooseDocuments }) {
  const { selected, processed } = selection

  return (
    <div className="context-bar">
      <span className="context-bar__label" id="context-label">
        Context
      </span>

      {selected.length === 0 ? (
        <span className="context-bar__all">
          <Icon name="stack" size={14} />
          All processed documents ({processed.length})
        </span>
      ) : (
        <ul className="context-bar__chips" aria-labelledby="context-label">
          {selected.map((doc) => (
            <li key={doc.document_id} className="chip">
              <span className="chip__name" title={doc.original_filename}>
                {doc.original_filename}
              </span>
              <button
                type="button"
                className="chip__remove"
                aria-label={`Remove ${doc.original_filename} from context`}
                onClick={() => selection.remove(doc.document_id)}
              >
                <Icon name="close" size={12} />
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="context-bar__actions">
        {selected.length > 0 && (
          <button type="button" className="link-button" onClick={selection.clear}>
            Use all documents
          </button>
        )}
        {/* The sidebar is a drawer on narrow screens; this opens it. Hidden on wide screens. */}
        <button type="button" className="link-button context-bar__choose" onClick={onChooseDocuments}>
          Choose documents
        </button>
      </div>
    </div>
  )
}
