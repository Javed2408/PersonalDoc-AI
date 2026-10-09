import { useEffect, useId, useRef, useState } from 'react'
import Icon from '../Common/Icon.jsx'
import { documentFileUrl } from '../../services/api.js'
import { formatSimilarity, sourceElementId } from '../../utils/sources.js'

/**
 * One document page the answer drew on. Every retrieved chunk from that page is listed separately,
 * with its exact text. A citation in the answer (`target`) opens the card and focuses its chunk.
 */
export default function SourceCard({ messageId, group, target, available }) {
  const [open, setOpen] = useState(false)
  const detailsId = useId()
  const pendingFocus = useRef(null)
  const labels = group.sources.map((source) => source.label).join(', ')
  const { filename, pageNumber, documentId } = group

  // A citation was clicked: open the card, then (once the chunk is rendered) bring it into view.
  useEffect(() => {
    if (!target) return
    pendingFocus.current = target.chunkId
    setOpen(true)
  }, [target?.request])

  useEffect(() => {
    if (!open || !pendingFocus.current) return
    const element = document.getElementById(sourceElementId(messageId, pendingFocus.current))
    pendingFocus.current = null
    if (!element) return
    // An instant jump, like following a link: no animation to wait for (or to stall in a background tab).
    element.focus({ preventScroll: true })
    element.scrollIntoView?.({ block: 'nearest' })
  })

  return (
    <li className={`source-card${open ? ' source-card--open' : ''}${target ? ' source-card--targeted' : ''}`}>
      <div className="source-card__header">
        <button
          type="button"
          className="source-card__toggle"
          aria-expanded={open}
          aria-controls={detailsId}
          onClick={() => setOpen((value) => !value)}
        >
          <Icon name="file" size={16} />
          <span className="source-card__main">
            <span className="source-card__name" title={filename}>
              {filename}
            </span>
            <span className="source-card__meta">
              Page {pageNumber} · {labels}
            </span>
          </span>
          <span className="source-card__chevron">
            <Icon name="chevron" size={14} />
          </span>
        </button>

        {available ? (
          <a
            className="source-card__pdf"
            href={documentFileUrl(documentId, pageNumber)}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Open ${filename} at page ${pageNumber} (PDF, new tab)`}
          >
            <Icon name="external" size={13} />
            PDF p.{pageNumber}
          </a>
        ) : (
          <span className="source-card__deleted">Deleted</span>
        )}
      </div>

      {open && (
        <div id={detailsId} className="source-card__details">
          {!available && (
            <p className="source-card__notice">
              This document has been deleted, so its PDF can’t be opened. The excerpts below are the text this answer
              was based on.
            </p>
          )}
          <ul className="source-chunks">
            {group.sources.map((source) => {
              const targeted = target?.chunkId === source.chunk_id
              return (
                <li
                  key={source.chunk_id}
                  id={sourceElementId(messageId, source.chunk_id)}
                  tabIndex={-1}
                  className={`source-chunk${targeted ? ' source-chunk--targeted' : ''}`}
                >
                  <p className="source-chunk__meta">
                    <span className="source-chunk__label">{source.label}</span>
                    <span>Excerpt · chunk {source.chunk_index + 1}</span>
                    <span>Similarity {formatSimilarity(source.similarity)}</span>
                    {targeted && <span className="source-chunk__tag">Selected from the answer</span>}
                  </p>
                  {source.text ? (
                    <blockquote className="source-chunk__excerpt">{source.text}</blockquote>
                  ) : (
                    <p className="source-chunk__missing">No text was returned for this source.</p>
                  )}
                </li>
              )
            })}
          </ul>
          <p className="source-card__note">
            Excerpts are the exact passages the model was given, not the whole page. Similarity shows how close a
            passage is to your question (higher is closer); it is not a confidence score.
          </p>
        </div>
      )}
    </li>
  )
}
