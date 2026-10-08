const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const UNREACHABLE_MESSAGE = "Can't reach the backend. Is the API server running?"

// The Vite dev proxy answers with a gateway error (and no JSON body) when the backend is down.
// The backend itself also uses 502/503/504, but always with a `detail` message.
const GATEWAY_ERROR_STATUSES = new Set([502, 503, 504])

// Used when the backend doesn't send a readable `detail` message.
const FALLBACK_MESSAGES = {
  400: 'The request was invalid.',
  404: 'That item no longer exists.',
  413: 'The file is too large.',
  415: 'Only PDF files are supported.',
  422: 'The request was invalid.',
}

export class ApiError extends Error {
  // `status` is undefined when the backend couldn't be reached at all.
  constructor(message, status, { unreachable = false } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.unreachable = unreachable
  }
}

async function readDetail(response) {
  try {
    const body = await response.json()
    // FastAPI validation errors use a list here; only plain strings are user-facing.
    if (typeof body?.detail === 'string') return body.detail
  } catch {
    // Not JSON.
  }
  return null
}

async function request(path, { method = 'GET', body, json, signal } = {}) {
  const headers = { Accept: 'application/json' }
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(json)
  }

  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { method, body, headers, signal })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(UNREACHABLE_MESSAGE, undefined, { unreachable: true })
  }

  if (!response.ok) {
    const detail = await readDetail(response)
    if (detail === null && GATEWAY_ERROR_STATUSES.has(response.status)) {
      throw new ApiError(UNREACHABLE_MESSAGE, response.status, { unreachable: true })
    }
    const message =
      detail ?? FALLBACK_MESSAGES[response.status] ?? `Something went wrong on the server (${response.status}).`
    throw new ApiError(message, response.status)
  }

  try {
    return await response.json()
  } catch {
    throw new ApiError('The backend returned an unexpected response.', response.status)
  }
}

export function getHealth(options) {
  return request('/api/health', options)
}

export async function listDocuments(options) {
  const { documents } = await request('/api/documents', options)
  return documents
}

export function uploadDocument(file, options) {
  const body = new FormData()
  body.append('file', file)
  return request('/api/documents/upload', { ...options, method: 'POST', body })
}

export function deleteDocument(documentId, options) {
  return request(`/api/documents/${encodeURIComponent(documentId)}`, { ...options, method: 'DELETE' })
}

/**
 * Ask one question. The backend retrieves, generates and returns { answer, status, model, sources }.
 * Omitted `documentIds` (or []) means all processed documents; omitted `k` uses the backend default.
 */
export function chat({ question, documentIds, k, signal }) {
  const json = { question }
  if (documentIds?.length) json.document_ids = documentIds
  if (k !== undefined) json.k = k
  return request('/api/chat', { method: 'POST', json, signal })
}
