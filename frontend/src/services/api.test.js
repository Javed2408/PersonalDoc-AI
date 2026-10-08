import { describe, expect, it, vi } from 'vitest'
import { ApiError, chat, getHealth } from './api.js'

function stubFetch(status, body) {
  const fetchMock = vi.fn(async () =>
    new Response(body === undefined ? '' : JSON.stringify(body), { status }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const ok = { question: 'q', answer: 'a', status: 'answered', model: 'm', sources: [] }

describe('chat', () => {
  it('posts JSON with only the question by default, so the backend defaults apply', async () => {
    const fetchMock = stubFetch(200, ok)

    await chat({ question: 'Hello?' })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/chat')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({ question: 'Hello?' })
  })

  it('sends document IDs and k when given', async () => {
    const fetchMock = stubFetch(200, ok)

    await chat({ question: 'Hello?', documentIds: ['a', 'b'], k: 6 })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ question: 'Hello?', document_ids: ['a', 'b'], k: 6 })
  })

  it('omits an empty document list', async () => {
    const fetchMock = stubFetch(200, ok)

    await chat({ question: 'Hello?', documentIds: [] })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ question: 'Hello?' })
  })

  it("keeps the backend's detail for its own 503s", async () => {
    stubFetch(503, { detail: "The model 'x' is not installed in Ollama. Run: ollama pull x" })

    const error = await chat({ question: 'q' }).catch((e) => e)

    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(503)
    expect(error.unreachable).toBe(false)
    expect(error.message).toMatch(/ollama pull x/)
  })

  it('treats a gateway error without a body as an unreachable backend', async () => {
    stubFetch(502)

    const error = await chat({ question: 'q' }).catch((e) => e)

    expect(error.unreachable).toBe(true)
    expect(error.message).toMatch(/can't reach the backend/i)
  })

  it('uses a generic message for validation error lists', async () => {
    stubFetch(422, { detail: [{ msg: 'String should have at least 1 character' }] })

    const error = await chat({ question: ' ' }).catch((e) => e)

    expect(error.status).toBe(422)
    expect(error.message).toBe('The request was invalid.')
  })
})

describe('request', () => {
  it('reports a network failure as unreachable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('Failed to fetch')
    }))

    const error = await getHealth().catch((e) => e)

    expect(error.unreachable).toBe(true)
    expect(error.status).toBeUndefined()
  })
})
