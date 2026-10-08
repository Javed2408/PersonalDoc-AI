import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App.jsx'
import {
  answered,
  deferred,
  failure,
  installBackend,
  makeDocument,
  makeSource,
  notFound,
} from './test/fakeBackend.js'

const report = makeDocument({ original_filename: 'report.pdf' })
const notes = makeDocument({ original_filename: 'notes.pdf' })
const processing = makeDocument({ original_filename: 'big.pdf', status: 'processing', page_count: null })
const failed = makeDocument({
  original_filename: 'scan.pdf',
  status: 'failed',
  processing_error: 'No extractable text.',
  page_count: null,
})

async function renderApp(options) {
  const backend = installBackend(options)
  const user = userEvent.setup()
  render(<App />)
  return { backend, user }
}

const composer = () => screen.getByRole('textbox', { name: /ask a question about your documents/i })
const sendButton = () => screen.getByRole('button', { name: 'Send question' })
const conversation = () => screen.getByRole('log', { name: 'Conversation' })

async function ask(user, question) {
  await waitFor(() => expect(composer()).toBeEnabled())
  await user.type(composer(), question)
  await user.click(sendButton())
}

describe('empty states', () => {
  it('invites a first question when processed documents exist', async () => {
    await renderApp({ documents: [report, notes] })

    expect(await screen.findByRole('heading', { name: 'Ask your documents anything.' })).toBeInTheDocument()
    expect(screen.getByText('all 2 processed documents')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'What are the main findings?' })).toBeInTheDocument()
  })

  it('asks for an upload when the library is empty, and disables the composer', async () => {
    await renderApp({ documents: [] })

    expect(await screen.findByRole('heading', { name: 'Your document library is empty.' })).toBeInTheDocument()
    expect(within(screen.getByRole('main')).getByRole('button', { name: /upload pdf/i })).toBeInTheDocument()
    expect(composer()).toBeDisabled()
  })

  it('waits for processing when no document is ready yet', async () => {
    await renderApp({ documents: [processing] })

    expect(await screen.findByRole('heading', { name: /getting your documents ready/i })).toBeInTheDocument()
    expect(composer()).toBeDisabled()
  })

  it('fills the composer from an example question without sending it', async () => {
    const { backend, user } = await renderApp({ documents: [report] })

    await user.click(await screen.findByRole('button', { name: 'Summarize the key points.' }))

    expect(composer()).toHaveValue('Summarize the key points.')
    expect(backend.chatRequests()).toHaveLength(0)
  })
})

describe('document selection', () => {
  it('selects, deselects and clears documents, and shows the context everywhere', async () => {
    const { user } = await renderApp({ documents: [report, notes] })
    const reportBox = await screen.findByRole('checkbox', { name: 'Ask about report.pdf' })
    const notesBox = screen.getByRole('checkbox', { name: 'Ask about notes.pdf' })
    const allButton = screen.getByRole('button', { name: /all processed documents/i })

    expect(allButton).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText('All processed documents (2)')).toBeInTheDocument()

    await user.click(reportBox)
    await user.click(notesBox)
    expect(reportBox).toBeChecked()
    expect(notesBox).toBeChecked()
    expect(allButton).toHaveAttribute('aria-pressed', 'false')
    expect(screen.getByText('2 selected')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Remove report.pdf from context' })).toBeInTheDocument()

    await user.click(notesBox)
    expect(notesBox).not.toBeChecked()
    expect(screen.getByText('1 selected')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Use all documents' }))
    expect(reportBox).not.toBeChecked()
    expect(screen.getByText('All processed documents (2)')).toBeInTheDocument()
  })

  it('removes a document from the context with its chip', async () => {
    const { user } = await renderApp({ documents: [report] })

    await user.click(await screen.findByRole('checkbox', { name: 'Ask about report.pdf' }))
    await user.click(screen.getByRole('button', { name: 'Remove report.pdf from context' }))

    expect(screen.getByRole('checkbox', { name: 'Ask about report.pdf' })).not.toBeChecked()
  })

  it('does not let processing or failed documents be selected', async () => {
    const { user } = await renderApp({ documents: [report, processing, failed] })

    const processingBox = await screen.findByRole('checkbox', { name: 'Ask about big.pdf' })
    const failedBox = screen.getByRole('checkbox', { name: 'Ask about scan.pdf' })
    expect(processingBox).toBeDisabled()
    expect(failedBox).toBeDisabled()
    expect(screen.getByText('Available for chat once processed')).toBeInTheDocument()

    await user.click(failedBox)
    expect(failedBox).not.toBeChecked()
    // Only the processed document counts towards "all".
    expect(screen.getByText('All processed documents (1)')).toBeInTheDocument()
  })
})

describe('asking a question', () => {
  it('shows the question at once, then a loading state, then the answer with its sources', async () => {
    const reply = deferred()
    const { user } = await renderApp({ documents: [report], chat: () => reply.promise })

    await ask(user, 'What are the main findings?')

    const log = conversation()
    expect(within(log).getByText('What are the main findings?')).toBeInTheDocument()
    expect(within(log).getByText(/searching your documents and writing an answer/i)).toBeInTheDocument()
    expect(composer()).toHaveValue('')

    reply.resolve(answered('Revenue grew by 12%. [Source 1]', [makeSource(report, { page_number: 14 })]))

    expect(await within(log).findByText(/revenue grew by 12%/i)).toBeInTheDocument()
    expect(within(log).queryByText(/searching your documents/i)).not.toBeInTheDocument()
    const sources = within(log).getByRole('region', { name: 'Sources' })
    expect(within(sources).getByText('report.pdf')).toBeInTheDocument()
    expect(within(sources).getByText('Page 14 · Source 1')).toBeInTheDocument()
    expect(within(log).getByText('Answered locally by llama3.2:3b')).toBeInTheDocument()
    expect(sendButton()).toBeDisabled() // Empty composer again
  })

  it('sends all processed documents by omitting document_ids, and the selected IDs otherwise', async () => {
    const { backend, user } = await renderApp({ documents: [report, notes] })

    await ask(user, 'First question')
    await within(conversation()).findByText('An answer.')
    expect(backend.chatRequests()[0].body).toEqual({ question: 'First question' })

    await user.click(screen.getByRole('checkbox', { name: 'Ask about report.pdf' }))
    await user.click(screen.getByRole('checkbox', { name: 'Ask about notes.pdf' }))
    await ask(user, 'Second question')

    await waitFor(() => expect(backend.chatRequests()).toHaveLength(2))
    expect(backend.chatRequests()[1].body).toEqual({
      question: 'Second question',
      document_ids: [report.document_id, notes.document_id],
    })
  })

  it('labels each question with the documents it was asked about', async () => {
    const { user } = await renderApp({ documents: [report, notes] })

    await ask(user, 'Across everything?')
    await user.click(screen.getByRole('checkbox', { name: 'Ask about report.pdf' }))
    await within(conversation()).findByText('An answer.')
    await ask(user, 'Only the report?')

    const questions = within(conversation()).getAllByRole('article', { name: 'Your question' })
    expect(within(questions[0]).getByText('All processed documents (2)')).toBeInTheDocument()
    expect(within(questions[1]).getByText('report.pdf')).toBeInTheDocument()
  })

  it('submits with Enter and adds a line with Shift+Enter', async () => {
    const { backend, user } = await renderApp({ documents: [report] })
    await waitFor(() => expect(composer()).toBeEnabled())

    await user.type(composer(), 'Line one{Shift>}{Enter}{/Shift}line two')
    expect(composer()).toHaveValue('Line one\nline two')
    expect(backend.chatRequests()).toHaveLength(0)

    await user.type(composer(), '{Enter}')
    await waitFor(() => expect(backend.chatRequests()).toHaveLength(1))
    expect(backend.chatRequests()[0].body.question).toBe('Line one\nline two')
  })

  it('rejects an empty or whitespace-only question', async () => {
    const { backend, user } = await renderApp({ documents: [report] })
    await waitFor(() => expect(composer()).toBeEnabled())

    expect(sendButton()).toBeDisabled()
    await user.type(composer(), '   {Enter}')

    expect(sendButton()).toBeDisabled()
    expect(backend.chatRequests()).toHaveLength(0)
    expect(screen.queryByRole('log')).not.toBeInTheDocument()
  })

  it('does not send a second question while an answer is pending', async () => {
    const reply = deferred()
    const { backend, user } = await renderApp({ documents: [report], chat: () => reply.promise })

    await ask(user, 'First')
    await user.type(composer(), 'Second{Enter}')

    expect(composer()).toHaveValue('Second') // Kept as a draft
    expect(sendButton()).toBeDisabled()
    expect(backend.chatRequests()).toHaveLength(1)

    reply.resolve(answered('Done.', []))
    await within(conversation()).findByText('Done.')
    expect(sendButton()).toBeEnabled()
  })

  it('shows the not-found fallback without sources', async () => {
    const { user } = await renderApp({ documents: [report], chat: () => notFound() })

    await ask(user, 'What is the capital of Australia?')

    const log = conversation()
    expect(await within(log).findByText(/couldn't find enough information/i)).toBeInTheDocument()
    expect(within(log).getByText(/try rephrasing the question/i)).toBeInTheDocument()
    expect(within(log).queryByRole('region', { name: 'Sources' })).not.toBeInTheDocument()
  })
})

describe('sources', () => {
  it('groups chunks from the same page and keeps every source', async () => {
    const sources = [
      makeSource(report, { label: 'Source 1', chunk_id: 'a', page_number: 2, chunk_index: 4, similarity: 0.81 }),
      makeSource(notes, { label: 'Source 2', chunk_id: 'b', page_number: 1, chunk_index: 0, similarity: 0.66 }),
      makeSource(report, { label: 'Source 3', chunk_id: 'c', page_number: 2, chunk_index: 5, similarity: 0.62 }),
    ]
    const { user } = await renderApp({
      documents: [report, notes],
      chat: () => answered('From both. [Source 1] [Source 2]', sources),
    })

    await ask(user, 'Compare them')

    const region = await within(conversation()).findByRole('region', { name: 'Sources' })
    expect(within(region).getByText('2 pages from 2 documents')).toBeInTheDocument()
    const cards = within(region).getAllByRole('listitem').filter((item) => item.classList.contains('source-card'))
    expect(cards).toHaveLength(2)
    expect(within(cards[0]).getByText('Page 2 · Source 1, Source 3')).toBeInTheDocument()
    expect(within(cards[1]).getByText('notes.pdf')).toBeInTheDocument()

    const toggle = within(cards[0]).getByRole('button', { name: /report\.pdf/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(within(cards[0]).getByText('Similarity 0.81')).toBeInTheDocument()
    expect(within(cards[0]).getByText('Chunk 6')).toBeInTheDocument()
    expect(within(cards[0]).getByText(/not a confidence score/i)).toBeInTheDocument()
    expect(within(region).queryByText(/confidence:|%/i)).not.toBeInTheDocument()
  })
})

describe('errors and retry', () => {
  it('explains an Ollama outage without exposing its address, then retries the same question', async () => {
    let calls = 0
    const { backend, user } = await renderApp({
      documents: [report],
      chat: () => {
        calls += 1
        return calls === 1
          ? failure(503, "Can't reach Ollama at http://127.0.0.1:11434. Make sure Ollama is installed and running.")
          : answered('It works now.', [makeSource(report)])
      },
    })

    await ask(user, 'Will this fail?')

    const alert = await within(conversation()).findByRole('alert')
    expect(within(alert).getByText('Local AI is unavailable')).toBeInTheDocument()
    expect(within(alert).getByText('Make sure Ollama is running, then retry.')).toBeInTheDocument()
    expect(alert).not.toHaveTextContent('11434')
    expect(within(conversation()).getByText('Will this fail?')).toBeInTheDocument() // Question kept

    await user.click(within(alert).getByRole('button', { name: 'Retry' }))

    expect(await within(conversation()).findByText('It works now.')).toBeInTheDocument()
    expect(within(conversation()).getAllByText('Will this fail?')).toHaveLength(1) // Not duplicated
    expect(backend.chatRequests().map((r) => r.body.question)).toEqual(['Will this fail?', 'Will this fail?'])
  })

  it('retries with the documents selected now', async () => {
    let calls = 0
    const { backend, user } = await renderApp({
      documents: [report, notes],
      chat: () => (++calls === 1 ? failure(504, 'The local language model did not answer within 120 seconds.') : notFound()),
    })

    await ask(user, 'Slow question')
    const alert = await within(conversation()).findByRole('alert')
    expect(within(alert).getByText('The local model took too long')).toBeInTheDocument()

    await user.click(screen.getByRole('checkbox', { name: 'Ask about notes.pdf' }))
    await user.click(within(alert).getByRole('button', { name: 'Retry' }))

    await waitFor(() => expect(backend.chatRequests()).toHaveLength(2))
    expect(backend.chatRequests()[1].body.document_ids).toEqual([notes.document_id])
    const question = within(conversation()).getByRole('article', { name: 'Your question' })
    expect(within(question).getByText('notes.pdf')).toBeInTheDocument()
  })

  it.each([
    [failure(503, "The model 'llama3.2:3b' is not installed in Ollama. Run: ollama pull llama3.2:3b"), 'Local model not installed', /ollama pull llama3\.2:3b/],
    [failure(502, 'The local language model returned an empty answer.'), "Couldn't generate an answer", /empty answer/],
    [failure(404, 'Unknown document ID(s): 0123.'), 'A selected document no longer exists', /check the document list/i],
    [failure(409, "These documents are not processed, so they can't be searched: big.pdf (processing)."), 'A selected document isn’t ready', /big\.pdf \(processing\)/],
    [failure(502), "Can't reach the backend", /api server is running/i],
  ])('shows a readable message for %#', async (reply, title, message) => {
    const { user } = await renderApp({ documents: [report], chat: () => reply })

    await ask(user, 'Question')

    const alert = await within(conversation()).findByRole('alert')
    expect(within(alert).getByText(title)).toBeInTheDocument()
    expect(alert).toHaveTextContent(message)
    expect(alert).not.toHaveTextContent(/traceback|exception/i)
  })

  it('refreshes the document list after a 404', async () => {
    const { backend, user } = await renderApp({ documents: [report], chat: () => failure(404, 'Unknown document ID(s): x.') })
    await waitFor(() => expect(backend.count('GET', '/api/documents')).toBe(1))

    await ask(user, 'Question')
    await within(conversation()).findByRole('alert')

    await waitFor(() => expect(backend.count('GET', '/api/documents')).toBe(2))
  })
})

describe('new chat', () => {
  it('clears the conversation but keeps the selection and the documents', async () => {
    const { backend, user } = await renderApp({ documents: [report, notes] })
    const newChat = await screen.findByRole('button', { name: /new chat/i })
    expect(newChat).toBeDisabled()

    await user.click(screen.getByRole('checkbox', { name: 'Ask about report.pdf' }))
    await ask(user, 'Something')
    await within(conversation()).findByText('An answer.')

    await user.click(newChat)

    expect(screen.queryByRole('log')).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Ask your documents anything.' })).toBeInTheDocument()
    expect(screen.getByRole('checkbox', { name: 'Ask about report.pdf' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: 'Ask about notes.pdf' })).toBeInTheDocument()
    expect(backend.requests.some((r) => r.method === 'DELETE')).toBe(false)
    expect(composer()).toHaveFocus()
  })

  it('drops an answer that was still on its way', async () => {
    const reply = deferred()
    const { user } = await renderApp({ documents: [report], chat: () => reply.promise })

    await ask(user, 'Slow one')
    await user.click(screen.getByRole('button', { name: /new chat/i }))
    reply.resolve(answered('Too late.', []))

    await new Promise((r) => setTimeout(r, 20))
    expect(screen.queryByText('Too late.')).not.toBeInTheDocument()
    expect(sendButton()).toBeDisabled() // Not stuck in a pending state: just an empty draft
    await user.type(composer(), 'Next')
    expect(sendButton()).toBeEnabled()
  })
})

describe('untrusted model output', () => {
  it('renders HTML in answers as text, never as markup', async () => {
    const hostile = '<img src=x onerror="window.__pwned=1"> <script>window.__pwned=2</script> **bold** <b>not bold</b>'
    const { user } = await renderApp({ documents: [report], chat: () => answered(hostile, []) })

    await ask(user, 'Inject?')

    const log = conversation()
    await within(log).findByText(/onerror/)
    expect(log.querySelector('img, script, b')).toBeNull()
    expect(log).toHaveTextContent('<script>window.__pwned=2</script>')
    expect(within(log).getByText('bold').tagName).toBe('STRONG')
    expect(window.__pwned).toBeUndefined()
  })
})

describe('header status', () => {
  it('says Local / Ready only when the backend and the model are both available', async () => {
    await renderApp({ documents: [report] })
    expect(await screen.findByText('Local / Ready')).toBeInTheDocument()
  })

  it('reports an unavailable Ollama and explains how to fix it', async () => {
    await renderApp({ documents: [report], llm: { status: 'unavailable', model: 'llama3.2:3b' } })

    expect(await screen.findByText('Ollama unavailable')).toBeInTheDocument()
    expect(screen.queryByText('Local / Ready')).not.toBeInTheDocument()
    expect(screen.getByText('Local AI is unavailable')).toBeInTheDocument()
  })

  it('names the model to pull when it is missing', async () => {
    await renderApp({ documents: [report], llm: { status: 'model_missing', model: 'llama3.2:3b' } })

    expect(await screen.findByText('Model not installed')).toBeInTheDocument()
    expect(screen.getByText('ollama pull llama3.2:3b')).toBeInTheDocument()
  })

  it('reports an offline backend and re-checks on request', async () => {
    const { backend, user } = await renderApp({ documents: [report], healthDown: true })

    expect(await screen.findByText('Backend offline')).toBeInTheDocument()
    backend.healthDown = false
    await user.click(screen.getByRole('button', { name: 'Check again' }))

    expect(await screen.findByText('Local / Ready')).toBeInTheDocument()
    expect(backend.count('GET', '/api/health')).toBe(2)
  })
})

describe('narrow-screen drawer', () => {
  it('opens and closes the document drawer from the header, with Escape, and from the context bar', async () => {
    const { user } = await renderApp({ documents: [report] })
    const toggle = await screen.findByRole('button', { name: 'Open documents' })
    const sidebar = screen.getByRole('complementary', { name: 'Documents' })

    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(toggle).toHaveAttribute('aria-controls', sidebar.id)
    expect(sidebar).not.toHaveClass('sidebar--open')

    await user.click(toggle)
    expect(sidebar).toHaveClass('sidebar--open')
    expect(screen.getByRole('button', { name: 'Close documents', expanded: true })).toBeInTheDocument()
    expect(sidebar).toContainElement(document.activeElement) // Focus moved into the drawer

    await user.keyboard('{Escape}')
    expect(sidebar).not.toHaveClass('sidebar--open')

    await user.click(screen.getByRole('button', { name: 'Choose documents' }))
    expect(sidebar).toHaveClass('sidebar--open')
    await user.click(within(sidebar).getByRole('button', { name: 'Close documents' }))
    expect(sidebar).not.toHaveClass('sidebar--open')
  })

  it('shows the number of selected documents on the drawer toggle', async () => {
    const { user } = await renderApp({ documents: [report, notes] })

    await user.click(await screen.findByRole('checkbox', { name: 'Ask about report.pdf' }))

    expect(within(screen.getByRole('button', { name: 'Open documents' })).getByText('1')).toBeInTheDocument()
  })
})
