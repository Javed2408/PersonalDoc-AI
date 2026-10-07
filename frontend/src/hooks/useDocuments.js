import { useCallback, useEffect, useRef, useState } from 'react'
import { deleteDocument, listDocuments, uploadDocument } from '../services/api.js'

const UPLOADED_NOTICE_MS = 3000
const POLL_INTERVAL_MS = 1500
// Documents in these states are still changing on the server.
const PENDING_STATUSES = new Set(['uploaded', 'processing'])

let nextUploadId = 0

export function useDocuments() {
  const [library, setLibrary] = useState({ status: 'loading', documents: [], error: null })
  const [uploads, setUploads] = useState([])
  const [deletions, setDeletions] = useState({})
  const [attempt, setAttempt] = useState(0)
  const timers = useRef(new Set())
  const libraryStatus = useRef(library.status)
  libraryStatus.current = library.status
  // Bumped whenever an upload or delete changes the list locally. A list request that
  // started before the bump would overwrite that change with stale data.
  const mutations = useRef(0)

  useEffect(() => {
    const controller = new AbortController()
    const startedAt = mutations.current
    setLibrary((prev) => ({ ...prev, status: 'loading', error: null }))

    listDocuments({ signal: controller.signal })
      .then((documents) => {
        if (mutations.current !== startedAt) setAttempt((n) => n + 1)
        else setLibrary({ status: 'ok', documents, error: null })
      })
      .catch((error) => {
        if (error.name === 'AbortError') return
        setLibrary((prev) => ({ ...prev, status: 'error', error: error.message }))
      })

    return () => controller.abort()
  }, [attempt])

  const hasPending = library.documents.some((doc) => PENDING_STATUSES.has(doc.status))

  // Poll quietly (no loading state) while any document is still being processed.
  useEffect(() => {
    if (!hasPending) return undefined
    const controller = new AbortController()
    let timer

    const poll = async () => {
      const startedAt = mutations.current
      try {
        const documents = await listDocuments({ signal: controller.signal })
        if (mutations.current === startedAt) setLibrary({ status: 'ok', documents, error: null })
      } catch (error) {
        if (error.name === 'AbortError') return
        setLibrary((prev) => ({ ...prev, status: 'error', error: error.message }))
      }
      timer = setTimeout(poll, POLL_INTERVAL_MS)
    }

    timer = setTimeout(poll, POLL_INTERVAL_MS)
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [hasPending])

  useEffect(() => {
    const pending = timers.current
    return () => pending.forEach(clearTimeout)
  }, [])

  const refresh = useCallback(() => setAttempt((n) => n + 1), [])

  // The backend is evidently reachable again, so replace a stale list error with fresh data.
  const reloadIfStale = useCallback(() => {
    if (libraryStatus.current === 'error') refresh()
  }, [refresh])

  const updateUpload = (id, changes) =>
    setUploads((prev) => prev.map((item) => (item.id === id ? { ...item, ...changes } : item)))

  const dismissUpload = useCallback((id) => {
    setUploads((prev) => prev.filter((item) => item.id !== id))
  }, [])

  const runUpload = useCallback(async (id, file) => {
    updateUpload(id, { status: 'uploading', error: null })
    try {
      const document = await uploadDocument(file)
      mutations.current += 1
      setLibrary((prev) => ({ ...prev, documents: [document, ...prev.documents] }))
      reloadIfStale()
      updateUpload(id, { status: 'uploaded' })
      const timer = setTimeout(() => {
        timers.current.delete(timer)
        dismissUpload(id)
      }, UPLOADED_NOTICE_MS)
      timers.current.add(timer)
    } catch (error) {
      updateUpload(id, { status: 'failed', error: error.message })
    }
  }, [dismissUpload, reloadIfStale])

  const upload = useCallback((files) => {
    for (const file of files) {
      const id = `upload-${nextUploadId++}`
      setUploads((prev) => [...prev, { id, file, name: file.name, status: 'uploading', error: null }])
      runUpload(id, file)
    }
  }, [runUpload])

  const retryUpload = useCallback((id) => {
    const item = uploads.find((entry) => entry.id === id)
    if (item) runUpload(id, item.file)
  }, [uploads, runUpload])

  const remove = useCallback(async (documentId) => {
    setDeletions((prev) => ({ ...prev, [documentId]: { status: 'deleting', error: null } }))
    try {
      await deleteDocument(documentId)
    } catch (error) {
      // Already gone on the server: treat as deleted so the list matches reality.
      if (error.status !== 404) {
        setDeletions((prev) => ({ ...prev, [documentId]: { status: 'failed', error: error.message } }))
        return
      }
    }
    mutations.current += 1
    setLibrary((prev) => ({
      ...prev,
      documents: prev.documents.filter((doc) => doc.document_id !== documentId),
    }))
    setDeletions(({ [documentId]: _done, ...rest }) => rest)
    reloadIfStale()
  }, [reloadIfStale])

  return { ...library, uploads, deletions, refresh, upload, retryUpload, dismissUpload, remove }
}
