import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App.jsx'
import { acceptFailedOnly, answered, deferred, failure, installBackend, makeDocument } from './test/fakeBackend.js'

/** Retrying a document whose processing failed (POST /api/documents/{id}/reindex). */

const report = makeDocument({ original_filename: 'report.pdf' })
const queued = makeDocument({ original_filename: 'queued.pdf', status: 'uploaded', page_count: null, chunk_count: null })
const busy = makeDocument({ original_filename: 'big.pdf', status: 'processing', page_count: null, chunk_count: null })
const failed = makeDocument({
  original_filename: 'scan.pdf',
  status: 'failed',
  processing_error: 'The embedding model could not be loaded. Check the backend logs.',
  page_count: null,
  chunk_count: null,
})
const recovered = { ...failed, status: 'processed', processing_error: null, page_count: 2, chunk_count: 2 }

const RETRY_PATH = `/api/documents/${failed.document_id}/reindex`

async function renderApp(options) {
  const backend = installBackend(options)
  const user = userEvent.setup()
  render(<App />)
  await screen.findByRole('checkbox', { name: 'Ask about report.pdf' })
  return { backend, user }
}

const rowOf = (filename) => screen.getByRole('checkbox', { name: `Ask about ${filename}` }).closest('li')
const retryButton = () => within(rowOf('scan.pdf')).getByRole('button', { name: /^(Retry processing|Retrying…) scan\.pdf$/ })

describe('retry processing', () => {
  it('is offered only for failed documents', async () => {
    await renderApp({ documents: [report, queued, busy, failed] })

    const buttons = screen.getAllByRole('button', { name: /^Retry processing/ })
    expect(buttons).toHaveLength(1)
    expect(buttons[0]).toHaveAccessibleName('Retry processing scan.pdf')
    expect(rowOf('scan.pdf')).toContainElement(buttons[0])
  })

  it('calls the reindex endpoint and shows the document processing', async () => {
    const { backend, user } = await renderApp({ documents: [report, failed] })

    await user.click(retryButton())

    const row = rowOf('scan.pdf')
    expect(await within(row).findByText('Processing…')).toBeInTheDocument()
    expect(backend.requests.filter((r) => r.path === RETRY_PATH)).toEqual([{ method: 'POST', path: RETRY_PATH, body: undefined }])
    expect(within(row).queryByText(failed.processing_error)).not.toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: /retry processing/i })).not.toBeInTheDocument()
    expect(within(row).getByText('Available for chat once processed')).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Ask about scan.pdf' })).toBeDisabled()
  })

  it('is disabled while the request is pending, so a second click sends nothing', async () => {
    const pending = deferred()
    const { backend, user } = await renderApp({
      documents: [report, failed],
      reindex: async (id, b) => {
        await pending.promise
        return acceptFailedOnly(id, b)
      },
    })

    await user.click(retryButton())
    expect(retryButton()).toHaveAccessibleName('Retrying… scan.pdf')
    expect(retryButton()).toBeDisabled()
    await user.click(retryButton())
    expect(backend.count('POST', RETRY_PATH)).toBe(1)

    pending.resolve()
    expect(await within(rowOf('scan.pdf')).findByText('Processing…')).toBeInTheDocument()
    expect(backend.count('POST', RETRY_PATH)).toBe(1)
  })

  it('shows the final result once processing finishes, and the document can then be asked about', async () => {
    const { backend, user } = await renderApp({ documents: [report, failed] })

    await user.click(retryButton())
    await within(rowOf('scan.pdf')).findByText('Processing…')
    backend.documents = [report, recovered] // The worker finishes; the list polls for it.

    expect(await within(rowOf('scan.pdf')).findByText('Processed', {}, { timeout: 4000 })).toBeInTheDocument()
    expect(within(rowOf('scan.pdf')).getByText('2 pages · 2 chunks')).toBeInTheDocument()
    const box = screen.getByRole('checkbox', { name: 'Ask about scan.pdf' })
    expect(box).toBeEnabled()

    await user.click(box)
    const composer = screen.getByRole('textbox', { name: /ask a question about your documents/i })
    await user.type(composer, 'What does the scan say?{Enter}')
    await waitFor(() => expect(backend.chatRequests()).toHaveLength(1))
    expect(backend.chatRequests()[0].body).toEqual({ question: 'What does the scan say?', document_ids: [failed.document_id] })
  })

  it('shows the same failure again when the retry fails during processing', async () => {
    const { backend, user } = await renderApp({ documents: [report, failed] })

    await user.click(retryButton())
    await within(rowOf('scan.pdf')).findByText('Processing…')
    backend.documents = [report, failed] // Failed again, with the same reason.

    expect(await within(rowOf('scan.pdf')).findByText('Failed', {}, { timeout: 4000 })).toBeInTheDocument()
    expect(within(rowOf('scan.pdf')).getByText(failed.processing_error)).toBeInTheDocument()
    expect(retryButton()).toBeEnabled()
  })
})

describe('retry errors', () => {
  it('explains a rejected request and lets the user try again', async () => {
    let reply = failure(500, 'The document library could not be loaded.')
    const { backend, user } = await renderApp({ documents: [report, failed], reindex: (id, b) => reply ?? acceptFailedOnly(id, b) })

    await user.click(retryButton())

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't retry: The document library could not be loaded.")
    expect(within(rowOf('scan.pdf')).getByText('Failed')).toBeInTheDocument()
    expect(retryButton()).toBeEnabled()

    reply = null
    await user.click(retryButton())
    expect(await within(rowOf('scan.pdf')).findByText('Processing…')).toBeInTheDocument()
    expect(screen.queryByText(/couldn't retry/i)).not.toBeInTheDocument()
    expect(backend.count('POST', RETRY_PATH)).toBe(2)
  })

  it('says when the backend cannot be reached', async () => {
    const { user } = await renderApp({ documents: [report, failed], reindex: () => failure(502) })

    await user.click(retryButton())

    expect(await screen.findByRole('alert')).toHaveTextContent("Couldn't retry: Can't reach the backend. Is the API server running?")
  })

  it('shows the current state when the document is no longer failed', async () => {
    const { backend, user } = await renderApp({
      documents: [report, failed],
      reindex: (id, b) => {
        b.documents = [report, { ...failed, status: 'processing', processing_error: null }] // Retried from another tab
        return failure(409, 'This document is already being processed.')
      },
    })
    const listLoads = backend.count('GET', '/api/documents')

    await user.click(retryButton())

    expect(await within(rowOf('scan.pdf')).findByText('Processing…')).toBeInTheDocument()
    expect(backend.count('GET', '/api/documents')).toBeGreaterThan(listLoads)
    expect(within(rowOf('scan.pdf')).queryByRole('button', { name: /retry processing/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('drops a document that was deleted elsewhere', async () => {
    const { user } = await renderApp({
      documents: [report, failed],
      reindex: (id, b) => {
        b.documents = [report]
        return failure(404, 'Document not found. It may have been deleted.')
      },
    })

    await user.click(retryButton())

    await waitFor(() => expect(screen.queryByRole('checkbox', { name: 'Ask about scan.pdf' })).not.toBeInTheDocument())
    expect(screen.getByRole('checkbox', { name: 'Ask about report.pdf' })).toBeEnabled()
  })
})

describe('around a retry', () => {
  it('keeps the selection and chat working', async () => {
    const { backend, user } = await renderApp({
      documents: [report, failed],
      chat: () => answered('From the report.', []),
    })
    await user.click(screen.getByRole('checkbox', { name: 'Ask about report.pdf' }))

    await user.click(retryButton())
    await within(rowOf('scan.pdf')).findByText('Processing…')

    expect(screen.getByRole('checkbox', { name: 'Ask about report.pdf' })).toBeChecked()
    const composer = screen.getByRole('textbox', { name: /ask a question about your documents/i })
    await user.type(composer, 'Summarize the report.{Enter}')
    expect(await screen.findByText('From the report.')).toBeInTheDocument()
    expect(backend.chatRequests()[0].body).toEqual({ question: 'Summarize the report.', document_ids: [report.document_id] })
  })
})
