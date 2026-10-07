const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

const UNREACHABLE_MESSAGE = "Can't reach the backend. Is the API server running?"

// The Vite dev proxy answers with a gateway error when the backend is down.
const GATEWAY_ERROR_STATUSES = new Set([502, 503, 504])

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, { signal } = {}) {
  let response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
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
    throw new ApiError(`The backend responded with an error (${response.status}).`, response.status)
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
