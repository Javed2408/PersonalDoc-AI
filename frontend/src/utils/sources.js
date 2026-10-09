/**
 * Group an answer's sources by document and page, in rank order, for display.
 * Every source the backend returned is kept inside its group; nothing is dropped.
 */
export function groupSources(sources = []) {
  const groups = new Map()
  for (const source of sources) {
    const key = `${source.document_id}:${source.page_number}`
    if (!groups.has(key)) {
      groups.set(key, {
        key,
        documentId: source.document_id,
        filename: source.original_filename,
        pageNumber: source.page_number,
        sources: [],
      })
    }
    groups.get(key).sources.push(source)
  }
  return [...groups.values()]
}

/** Cosine similarity with two decimals. A geometric closeness score, not a confidence. */
export function formatSimilarity(value) {
  return Number.isFinite(value) ? value.toFixed(2) : '–'
}

export function countDocuments(sources = []) {
  return new Set(sources.map((source) => source.document_id)).size
}

/**
 * Which source each [Source N] marker in an answer refers to: N -> the source the backend labelled
 * "Source N" for this answer. Markers with no entry here point at nothing and stay plain text.
 */
export function citationTargets(sources = []) {
  const targets = new Map()
  for (const source of sources) {
    const match = /^Source (\d+)$/.exec(source.label ?? '')
    if (match && !targets.has(Number(match[1]))) targets.set(Number(match[1]), source)
  }
  return targets
}

/** DOM id of one source chunk in one answer. Chunk IDs are stable; the message ID keeps answers apart. */
export function sourceElementId(messageId, chunkId) {
  return `source-${messageId}-${chunkId}`
}
