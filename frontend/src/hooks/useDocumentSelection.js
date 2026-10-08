import { useCallback, useMemo, useState } from 'react'

/**
 * Which documents the next question is asked about.
 *
 * Nothing selected means "all processed documents", the same as the API's default. Only processed
 * documents can be selected, and the selection is always read through the current list, so a
 * document that is deleted or stops being processed silently leaves the context.
 */
export function useDocumentSelection(documents) {
  const [selectedIds, setSelectedIds] = useState([])

  const processed = useMemo(() => documents.filter((doc) => doc.status === 'processed'), [documents])

  const selected = useMemo(() => {
    const byId = new Map(processed.map((doc) => [doc.document_id, doc]))
    return selectedIds.map((id) => byId.get(id)).filter(Boolean)
  }, [processed, selectedIds])

  const selectedSet = useMemo(() => new Set(selected.map((doc) => doc.document_id)), [selected])

  const toggle = useCallback(
    (documentId) => {
      if (!processed.some((doc) => doc.document_id === documentId)) return
      setSelectedIds((prev) =>
        prev.includes(documentId) ? prev.filter((id) => id !== documentId) : [...prev, documentId],
      )
    },
    [processed],
  )

  const remove = useCallback((documentId) => {
    setSelectedIds((prev) => prev.filter((id) => id !== documentId))
  }, [])

  const clear = useCallback(() => setSelectedIds([]), [])

  const isSelected = useCallback((documentId) => selectedSet.has(documentId), [selectedSet])

  return { processed, selected, isSelected, toggle, remove, clear }
}

/** A snapshot of the context a question was asked in, kept with the message. */
export function describeContext(selected, processedCount) {
  if (selected.length === 0) {
    return { documentIds: [], label: `All processed documents (${processedCount})` }
  }
  if (selected.length === 1) {
    return { documentIds: [selected[0].document_id], label: selected[0].original_filename }
  }
  return {
    documentIds: selected.map((doc) => doc.document_id),
    label: `${selected.length} documents`,
    names: selected.map((doc) => doc.original_filename),
  }
}
