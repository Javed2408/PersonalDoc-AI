import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import App from './App.jsx'
import { answered, installBackend, makeDocument, makeSource } from './test/fakeBackend.js'

/** Phase 8: source excerpts, inline citations and opening the original PDF. */

const report = makeDocument({ original_filename: 'report.pdf' })
const notes = makeDocument({ original_filename: 'notes.pdf' })

const REVENUE = 'Revenue grew by 12% in 2025, driven by the new product line.'
const COSTS = 'Operating costs stayed flat at 4.1 million.'
const OUTLOOK = 'The outlook for 2026 is cautious.'

// Two chunks from report.pdf page 14 and one from notes.pdf page 3, as the backend labels them.
const sources = [
  makeSource(report, { label: 'Source 1', chunk_id: `${report.document_id}-00021`, page_number: 14, chunk_index: 21, text: REVENUE, similarity: 0.77 }),
  makeSource(notes, { label: 'Source 2', chunk_id: `${notes.document_id}-00004`, page_number: 3, chunk_index: 4, text: OUTLOOK, similarity: 0.61 }),
  makeSource(report, { label: 'Source 3', chunk_id: `${report.document_id}-00022`, page_number: 14, chunk_index: 22, text: COSTS, similarity: 0.58 }),
]

async function askWith(answer, { documents = [report, notes], replySources = sources } = {}) {
  const backend = installBackend({ documents, chat: () => answered(answer, replySources) })
  const user = userEvent.setup()
  render(<App />)
  const composer = screen.getByRole('textbox', { name: /ask a question/i })
  await waitFor(() => expect(composer).toBeEnabled())
  await user.type(composer, 'What happened?{Enter}')
  const log = screen.getByRole('log', { name: 'Conversation' })
  await within(log).findByRole('region', { name: 'Sources' })
  return { backend, user, log }
}

const cardFor = (log, filename) =>
  within(log).getByRole('button', { name: new RegExp(`^${filename.replace('.', '\\.')}`) }).closest('li')

describe('source excerpts', () => {
  it('expand and collapse to show the exact retrieved text, without touching the conversation', async () => {
    const { user, log } = await askWith('Revenue grew. [Source 1]')
    const toggle = within(cardFor(log, 'report.pdf')).getByRole('button', { name: /^report\.pdf/ })

    expect(within(log).queryByText(REVENUE)).not.toBeInTheDocument()

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(within(log).getByText(REVENUE).tagName).toBe('BLOCKQUOTE')
    expect(within(log).getByText(/exact passages the model was given, not the whole page/)).toBeInTheDocument()

    await user.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(within(log).queryByText(REVENUE)).not.toBeInTheDocument()
    expect(within(log).getByText('What happened?')).toBeInTheDocument()
    expect(within(log).getByText('Revenue grew.', { exact: false })).toBeInTheDocument()
  })

  it('keeps several chunks from the same page individually accessible', async () => {
    const { user, log } = await askWith('Both. [Source 1] [Source 3]')
    const card = cardFor(log, 'report.pdf')

    expect(within(card).getByText('Page 14 · Source 1, Source 3')).toBeInTheDocument()
    await user.click(within(card).getByRole('button', { name: /^report\.pdf/ }))

    const chunks = within(card).getAllByRole('listitem').filter((item) => item.classList.contains('source-chunk'))
    expect(chunks).toHaveLength(2)
    expect(within(chunks[0]).getByText('Source 1')).toBeInTheDocument()
    expect(within(chunks[0]).getByText(REVENUE)).toBeInTheDocument()
    expect(within(chunks[0]).getByText('Excerpt · chunk 22')).toBeInTheDocument()
    expect(within(chunks[1]).getByText('Source 3')).toBeInTheDocument()
    expect(within(chunks[1]).getByText(COSTS)).toBeInTheDocument()
    expect(new Set(chunks.map((chunk) => chunk.id)).size).toBe(2)
  })

  it('never invents text for a source that came without any', async () => {
    const { user, log } = await askWith('See [Source 1]', { replySources: [{ ...sources[0], text: '' }] })

    await user.click(within(cardFor(log, 'report.pdf')).getByRole('button', { name: /^report\.pdf/ }))

    expect(within(log).getByText('No text was returned for this source.')).toBeInTheDocument()
  })
})

describe('inline citations', () => {
  it('map each marker to the source with that label, whatever order the sources arrive in', async () => {
    const shuffled = [sources[2], sources[0], sources[1]]
    const { log } = await askWith('Growth [Source 1], outlook [Source 2], costs [Source 3].', { replySources: shuffled })

    expect(within(log).getByRole('button', { name: 'Source 1: report.pdf, page 14' })).toBeInTheDocument()
    expect(within(log).getByRole('button', { name: 'Source 2: notes.pdf, page 3' })).toBeInTheDocument()
    expect(within(log).getByRole('button', { name: 'Source 3: report.pdf, page 14' })).toBeInTheDocument()
  })

  it('open the cited source and focus its exact chunk, then move when another is clicked', async () => {
    const { user, log } = await askWith('Growth [Source 3] and outlook [Source 2].')

    await user.click(within(log).getByRole('button', { name: /^Source 3:/ }))

    const reportCard = cardFor(log, 'report.pdf')
    expect(within(reportCard).getByRole('button', { name: /^report\.pdf/ })).toHaveAttribute('aria-expanded', 'true')
    const focused = document.activeElement
    expect(focused).toHaveTextContent(COSTS) // Source 3, not the other chunk on the same page
    // Located by message ID + stable chunk ID, not by position.
    expect(focused.id).toMatch(new RegExp(`^source-a-[0-9]+-${report.document_id}-00022$`))
    expect(within(focused).getByText('Selected from the answer')).toBeInTheDocument()
    expect(within(reportCard).getAllByText('Selected from the answer')).toHaveLength(1)

    await user.click(within(log).getByRole('button', { name: /^Source 2:/ }))

    expect(document.activeElement).toHaveTextContent(OUTLOOK)
    expect(within(log).getAllByText('Selected from the answer')).toHaveLength(1)
    expect(within(cardFor(log, 'notes.pdf')).getByText('Selected from the answer')).toBeInTheDocument()
  })

  it('scope citations to their own answer when several answers cite the same chunk', async () => {
    const { user, log } = await askWith('First. [Source 1]')
    await user.type(screen.getByRole('textbox', { name: /ask a question/i }), 'Again?{Enter}')
    await waitFor(() => expect(within(log).getAllByRole('region', { name: 'Sources' })).toHaveLength(2))

    const answers = within(log).getAllByRole('article', { name: 'Answer' })
    await user.click(within(answers[1]).getByRole('button', { name: /^Source 1:/ }))

    expect(answers[1]).toContainElement(document.activeElement)
    expect(within(answers[0]).queryByText('Selected from the answer')).not.toBeInTheDocument()
  })

  it.each([
    ['out of range', 'Something [Source 9] here.', '[Source 9]'],
    ['zero', 'Something [Source 0] here.', '[Source 0]'],
    ['no number', 'Something [Source] here.', '[Source]'],
    ['other word', 'Something [Src 1] here.', '[Src 1]'],
    ['trailing text', 'Something [Source 1a] here.', '[Source 1a]'],
    ['list form', 'Something [Source 1, 2] here.', '[Source 1, 2]'],
  ])('leave a %s marker as plain text', async (_, answer, marker) => {
    const { log } = await askWith(answer)

    const paragraph = within(log).getByText(/Something/)
    expect(paragraph).toHaveTextContent(`Something ${marker} here.`)
    expect(within(paragraph).queryByRole('button')).not.toBeInTheDocument()
  })

  it('still show the sources when the answer cites none', async () => {
    const { log } = await askWith('Revenue grew by 12 percent.')

    expect(within(log).queryByRole('button', { name: /^Source \d:/ })).not.toBeInTheDocument()
    expect(within(log).getByText('2 pages from 2 documents')).toBeInTheDocument()
    expect(cardFor(log, 'report.pdf')).toBeInTheDocument()
    expect(cardFor(log, 'notes.pdf')).toBeInTheDocument()
  })
})

describe('similarity wording', () => {
  it('labels similarity as similarity, never as confidence or a percentage', async () => {
    const { user, log } = await askWith('See [Source 1]')

    await user.click(within(cardFor(log, 'report.pdf')).getByRole('button', { name: /^report\.pdf/ }))

    const region = within(log).getByRole('region', { name: 'Sources' })
    expect(within(region).getByText('Similarity 0.77')).toBeInTheDocument()
    // Only the labels: the excerpt itself may legitimately contain numbers like "12%".
    for (const label of region.querySelectorAll('.source-card__meta, .source-chunk__meta, .sources__title')) {
      expect(label).not.toHaveTextContent(/confidence|%|probability/i)
    }
    expect(region).toHaveTextContent('it is not a confidence score')
  })
})

describe('opening the original PDF', () => {
  it('links each source page to the stored PDF, at that page, in a new tab', async () => {
    const { log } = await askWith('See [Source 1]')

    const link = within(cardFor(log, 'report.pdf')).getByRole('link', { name: 'Open report.pdf at page 14 (PDF, new tab)' })
    expect(link).toHaveAttribute('href', `/api/documents/${report.document_id}/file#page=14`)
    expect(link).toHaveAttribute('target', '_blank')
    expect(link.getAttribute('rel')).toMatch(/noopener/)
    expect(link.getAttribute('rel')).toMatch(/noreferrer/)
    expect(within(cardFor(log, 'notes.pdf')).getByRole('link')).toHaveAttribute(
      'href',
      `/api/documents/${notes.document_id}/file#page=3`,
    )
  })

  it('keeps the PDF link and the excerpt toggle as separate controls (usable on touch screens)', async () => {
    const { log } = await askWith('See [Source 1]')
    const card = cardFor(log, 'report.pdf')

    const toggle = within(card).getByRole('button', { name: /^report\.pdf/ })
    const link = within(card).getByRole('link')
    expect(toggle).not.toContainElement(link)
    expect(link).not.toContainElement(toggle)
  })

  it('explains that a deleted document can no longer be opened, but keeps its excerpts', async () => {
    // notes.pdf was deleted before this answer is shown: it is not in the library.
    const { user, log } = await askWith('See [Source 2]', { documents: [report] })
    const card = cardFor(log, 'notes.pdf')

    expect(within(card).queryByRole('link')).not.toBeInTheDocument()
    expect(within(card).getByText('Deleted')).toBeInTheDocument()

    await user.click(within(log).getByRole('button', { name: /^Source 2:/ }))
    expect(within(card).getByText(/has been deleted, so its PDF can’t be opened/)).toBeInTheDocument()
    expect(within(card).getByText(OUTLOOK)).toBeInTheDocument()
  })

  it('turns the link off when the document is deleted during the conversation', async () => {
    const { user, log } = await askWith('See [Source 1]')
    expect(within(cardFor(log, 'report.pdf')).getByRole('link')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Delete report.pdf' }))
    await user.click(screen.getByRole('button', { name: 'Delete' }))

    await waitFor(() => expect(within(cardFor(log, 'report.pdf')).queryByRole('link')).not.toBeInTheDocument())
    expect(within(cardFor(log, 'report.pdf')).getByText('Deleted')).toBeInTheDocument()
  })
})

describe('untrusted text', () => {
  it('shows HTML in answers and in excerpts as text, and never executes it', async () => {
    const hostileExcerpt = '<img src=x onerror="window.__excerptPwned=1"><script>window.__excerptPwned=2</script>'
    const { user, log } = await askWith('<b>Bold?</b> <a href="javascript:alert(1)">x</a> [Source 1]', {
      replySources: [{ ...sources[0], text: hostileExcerpt }],
    })

    await user.click(within(log).getByRole('button', { name: /^Source 1:/ }))

    expect(log.querySelector('img, script, .answer-text b, .answer-text a, .source-chunk__excerpt *')).toBeNull()
    expect(within(log).getByText(hostileExcerpt)).toBeInTheDocument()
    expect(log).toHaveTextContent('<b>Bold?</b>')
    expect(window.__excerptPwned).toBeUndefined()
  })
})
