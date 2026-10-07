const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const UNREACHABLE_MESSAGE = "Can't reach the backend. Is the API server running?"

// The Vite dev proxy answers with a gateway error when the backend is down.
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
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function errorMessageFor(response) {
  try {
    const body = await response.json()
    // FastAPI validation errors use a list here; only plain strings are user-facing.
    if (typeof body?.detail === 'string') return body.detail
  } catch {
    // Not JSON; fall through to a generic message.
  }
  return FALLBACK_MESSAGES[response.status] ?? `Something went wrong on the server (${response.status}).`
}

async function request(path, { method = 'GET', body, signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      body,
      headers: { Accept: 'application/json' },
      signal,
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(UNREACHABLE_MESSAGE)
  }

  if (GATEWAY_ERROR_STATUSES.has(response.status)) {
    throw new ApiError(UNREACHABLE_MESSAGE, response.status)
  }

  if (!response.ok) {
    throw new ApiError(await errorMessageFor(response), response.status)
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
