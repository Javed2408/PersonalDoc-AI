import { countDocuments, groupSources } from '../../utils/sources.js'
import SourceCard from './SourceCard.jsx'

function plural(count, word) {
  return `${count} ${word}${count === 1 ? '' : 's'}`
}

/** The passages the model was given, exactly as the backend returned them, grouped by page. */
export default function SourceList({ messageId, sources, target, isDocumentAvailable }) {
  if (!sources?.length) return null
  const groups = groupSources(sources)

  return (
    <section className="sources" aria-label="Sources">
      <h3 className="sources__title">
        Sources
        <span className="sources__summary">
          {plural(groups.length, 'page')} from {plural(countDocuments(sources), 'document')}
        </span>
      </h3>
      <ul className="sources__list">
        {groups.map((group) => (
          <SourceCard
            key={group.key}
            messageId={messageId}
            group={group}
            target={group.sources.some((source) => source.chunk_id === target?.chunkId) ? target : null}
            available={isDocumentAvailable ? isDocumentAvailable(group.documentId) : true}
          />
        ))}
      </ul>
    </section>
  )
}
