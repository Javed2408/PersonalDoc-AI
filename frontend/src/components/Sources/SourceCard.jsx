import { useId, useState } from 'react'
import Icon from '../Common/Icon.jsx'
import { formatSimilarity } from '../../utils/sources.js'

/** One document page the answer drew on. Several retrieved chunks from the same page share a card. */
export default function SourceCard({ group }) {
  const [open, setOpen] = useState(false)
  const detailsId = useId()
  const labels = group.sources.map((source) => source.label).join(', ')

  return (
    <li className={`source-card${open ? ' source-card--open' : ''}`}>
      <button
        type="button"
        className="source-card__toggle"
        aria-expanded={open}
        aria-controls={detailsId}
        onClick={() => setOpen((value) => !value)}
      >
        <Icon name="file" size={16} />
        <span className="source-card__main">
          <span className="source-card__name" title={group.filename}>
            {group.filename}
          </span>
          <span className="source-card__meta">
            Page {group.pageNumber} · {labels}
          </span>
        </span>
        <span className="source-card__chevron">
          <Icon name="chevron" size={14} />
        </span>
      </button>

      {open && (
        <div id={detailsId} className="source-card__details">
          <ul className="source-card__chunks">
            {group.sources.map((source) => (
              <li key={source.chunk_id}>
                <span className="source-card__chunk-label">{source.label}</span>
                <span>Chunk {source.chunk_index + 1}</span>
                <span>Similarity {formatSimilarity(source.similarity)}</span>
              </li>
            ))}
          </ul>
          <p className="source-card__note">
            Similarity shows how close this passage is to your question (higher is closer). It is not a confidence
            score.
          </p>
        </div>
      )}
    </li>
  )
}
