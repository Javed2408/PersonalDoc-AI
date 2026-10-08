import { describe, expect, it } from 'vitest'
import { parseAnswer, parseInline } from './answerFormat.js'
import { describeChatError } from './chatErrors.js'
import { countDocuments, formatSimilarity, groupSources } from './sources.js'
import { serviceStatus } from './status.js'

describe('parseAnswer', () => {
  it('splits paragraphs on blank lines and keeps single line breaks', () => {
    expect(parseAnswer('First line\nsecond line\n\nNew paragraph')).toEqual([
      { type: 'paragraph', lines: ['First line', 'second line'] },
      { type: 'paragraph', lines: ['New paragraph'] },
    ])
  })

  it('reads bullet and numbered lists, keeping the starting number', () => {
    expect(parseAnswer('Remedies:\n- more data\n* dropout\n\n3. third\n4. fourth')).toEqual([
      { type: 'paragraph', lines: ['Remedies:'] },
      { type: 'list', ordered: false, start: undefined, items: ['more data', 'dropout'] },
      { type: 'list', ordered: true, start: 3, items: ['third', 'fourth'] },
    ])
  })

  it('joins indented continuation lines to the list item', () => {
    expect(parseAnswer('1. Collect more data\n   when possible')[0].items).toEqual(['Collect more data when possible'])
  })

  it('treats markdown headings as emphasised lines, and copes with empty input', () => {
    expect(parseAnswer('## Summary')).toEqual([{ type: 'heading', text: 'Summary' }])
    expect(parseAnswer('')).toEqual([])
    expect(parseAnswer(undefined)).toEqual([])
  })
})

describe('parseInline', () => {
  it('finds bold, code and citations and leaves everything else as text', () => {
    expect(parseInline('Use **L2** with `lambda` [Source 2] <b>x</b>')).toEqual([
      { type: 'text', text: 'Use ' },
      { type: 'bold', text: 'L2' },
      { type: 'text', text: ' with ' },
      { type: 'code', text: 'lambda' },
      { type: 'text', text: ' ' },
      { type: 'cite', text: 'Source 2' },
      { type: 'text', text: ' <b>x</b>' },
    ])
  })
})

describe('describeChatError', () => {
  it('treats a missing status as an unreachable backend', () => {
    expect(describeChatError({ message: 'x' }).title).toBe("Can't reach the backend")
    expect(describeChatError({ status: 502, unreachable: true, message: 'x' }).title).toBe("Can't reach the backend")
  })

  it('keeps the backend message for search outages and validation errors', () => {
    expect(describeChatError({ status: 503, message: 'The vector index is unavailable.' })).toEqual({
      title: 'Search is unavailable',
      message: 'The vector index is unavailable.',
    })
    expect(describeChatError({ status: 422, message: 'k must be between 1 and 20.' }).message).toBe(
      'k must be between 1 and 20.',
    )
  })
})

describe('sources helpers', () => {
  const source = (document_id, page_number, label) => ({ document_id, page_number, label, original_filename: `${document_id}.pdf` })

  it('groups by document and page in rank order', () => {
    const groups = groupSources([source('a', 1, 'Source 1'), source('b', 1, 'Source 2'), source('a', 1, 'Source 3')])
    expect(groups.map((g) => [g.filename, g.pageNumber, g.sources.map((s) => s.label)])).toEqual([
      ['a.pdf', 1, ['Source 1', 'Source 3']],
      ['b.pdf', 1, ['Source 2']],
    ])
    expect(countDocuments([source('a', 1), source('a', 2)])).toBe(1)
  })

  it('formats similarity as a plain two-decimal number', () => {
    expect(formatSimilarity(0.7712)).toBe('0.77')
    expect(formatSimilarity(undefined)).toBe('–')
  })
})

describe('serviceStatus', () => {
  it('never claims readiness it cannot know', () => {
    expect(serviceStatus({ status: 'loading' }).label).toBe('Connecting…')
    expect(serviceStatus({ status: 'error' }).label).toBe('Backend offline')
    expect(serviceStatus({ status: 'ok', data: {} }).label).toBe('Backend ready')
    expect(serviceStatus({ status: 'ok', data: { llm: { status: 'ready', model: 'm' } } }).label).toBe('Local / Ready')
  })
})
