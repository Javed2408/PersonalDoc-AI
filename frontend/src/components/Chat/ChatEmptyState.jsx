import UploadDropzone from '../Documents/UploadDropzone.jsx'

// Generic on purpose: nothing here pretends to know what the user's documents contain.
const EXAMPLES = [
  { label: 'What are the main findings?', text: 'What are the main findings?' },
  { label: 'Summarize the key points.', text: 'Summarize the key points.' },
  { label: 'What does the document say about …?', text: 'What does the document say about ' },
]

export default function ChatEmptyState({ library, selection, onExample }) {
  const { status, documents } = library
  const processedCount = selection.processed.length

  if (status === 'loading' && documents.length === 0) {
    return (
      <div className="chat-empty">
        <p className="muted">Loading your documents…</p>
      </div>
    )
  }

  if (status === 'error' && documents.length === 0) {
    return (
      <div className="chat-empty">
        <h1 className="chat-empty__title">Your documents couldn’t be loaded.</h1>
        <p className="chat-empty__lede">{library.error}</p>
        <button type="button" className="button" onClick={library.refresh}>
          Try again
        </button>
      </div>
    )
  }

  if (documents.length === 0) {
    return (
      <div className="chat-empty">
        <h1 className="chat-empty__title">Your document library is empty.</h1>
        <p className="chat-empty__lede">Upload a PDF to start asking questions about your documents, locally.</p>
        <UploadDropzone onFiles={library.upload} />
      </div>
    )
  }

  if (processedCount === 0) {
    return (
      <div className="chat-empty">
        <h1 className="chat-empty__title">Getting your documents ready…</h1>
        <p className="chat-empty__lede">
          You can ask questions as soon as a document finishes processing. Progress is shown in the document list.
        </p>
      </div>
    )
  }

  const scope =
    selection.selected.length === 0
      ? `all ${processedCount} processed document${processedCount === 1 ? '' : 's'}`
      : selection.selected.length === 1
        ? selection.selected[0].original_filename
        : `${selection.selected.length} selected documents`

  return (
    <div className="chat-empty">
      <h1 className="chat-empty__title">Ask your documents anything.</h1>
      <p className="chat-empty__lede">
        Answers come only from <strong>{scope}</strong>, with the pages they’re based on. Choose specific documents to
        narrow the search.
      </p>
      <div className="chat-empty__examples">
        <p className="chat-empty__examples-title">Try</p>
        <ul>
          {EXAMPLES.map((example) => (
            <li key={example.label}>
              <button type="button" className="example-button" onClick={() => onExample(example.text)}>
                {example.label}
              </button>
            </li>
          ))}
        </ul>
      </div>
      <p className="chat-empty__note">
        Each question is answered on its own from your documents; earlier messages aren’t sent to the model.
      </p>
    </div>
  )
}
