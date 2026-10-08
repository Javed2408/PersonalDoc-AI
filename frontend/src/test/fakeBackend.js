import { vi } from 'vitest'

/** A stand-in for the FastAPI backend, installed as `fetch`. Records every request. */

export function makeDocument(overrides = {}) {
  const id = overrides.document_id ?? `${'0'.repeat(30)}${String(makeDocument.count++).padStart(2, '0')}`
  return {
    document_id: id,
    original_filename: 'report.pdf',
    stored_filename: `${id}.pdf`,
    file_type: 'pdf',
    file_size: 2048,
    status: 'processed',
    created_at: '2026-10-09T10:00:00Z',
    page_count: 3,
    chunk_count: 3,
    processing_error: null,
    ...overrides,
  }
}
makeDocument.count = 1

export function makeSource(document, overrides = {}) {
  return {
    label: 'Source 1',
    chunk_id: `${document.document_id}-00000`,
    document_id: document.document_id,
    original_filename: document.original_filename,
    page_number: 1,
    chunk_index: 0,
    text: 'Some passage from the document.',
    distance: 0.3,
    similarity: 0.7,
    ...overrides,
  }
}

export function answered(answer, sources, model = 'llama3.2:3b') {
  return { status: 200, body: { question: 'q', answer, status: 'answered', model, sources } }
}

export function notFound() {
  return {
    status: 200,
    body: {
      question: 'q',
      answer: "I couldn't find enough information in the selected documents to answer that reliably.",
      status: 'not_found',
      model: 'llama3.2:3b',
      sources: [],
    },
  }
}

export function failure(status, detail) {
  return { status, body: detail === undefined ? null : { detail } }
}

function toResponse({ status, body }) {
  return new Response(body === null ? '' : JSON.stringify(body), {
    status,
    headers: body === null ? {} : { 'Content-Type': 'application/json' },
  })
}

/**
 * `chat` is a function (requestBody) => reply | Promise<reply>, where reply is
 * { status, body } (see answered / notFound / failure).
 */
export function installBackend({
  documents = [],
  llm = { status: 'ready', model: 'llama3.2:3b' },
  healthDown = false,
  chat = () => answered('An answer.', []),
} = {}) {
  const backend = { documents, llm, healthDown, chat, requests: [] }

  const fetchMock = vi.fn(async (url, init = {}) => {
    const method = init.method ?? 'GET'
    const path = new URL(url, 'http://localhost').pathname
    const body = typeof init.body === 'string' ? JSON.parse(init.body) : init.body
    backend.requests.push({ method, path, body })

    if (path === '/api/health') {
      if (backend.healthDown) return toResponse({ status: 502, body: null })
      return toResponse({
        status: 200,
        body: { status: 'ok', app_name: 'PersonalDoc AI', version: '0.1.0', environment: 'test', llm: backend.llm },
      })
    }
    if (path === '/api/documents' && method === 'GET') {
      return toResponse({ status: 200, body: { documents: backend.documents } })
    }
    if (path === '/api/chat' && method === 'POST') {
      return toResponse(await backend.chat(body))
    }
    return toResponse({ status: 404, body: { detail: 'Not Found' } })
  })

  vi.stubGlobal('fetch', fetchMock)
  backend.chatRequests = () => backend.requests.filter((r) => r.path === '/api/chat')
  backend.count = (method, path) => backend.requests.filter((r) => r.method === method && r.path === path).length
  return backend
}

/** A promise you resolve from the test, to hold a request in flight. */
export function deferred() {
  let resolve
  const promise = new Promise((r) => {
    resolve = r
  })
  return { promise, resolve }
}
