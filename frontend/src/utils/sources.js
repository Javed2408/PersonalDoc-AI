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
