/**
 * A deliberately small reader for the plain-text answers the local model writes: paragraphs,
 * line breaks, bullet and numbered lists, **bold**, `code` and [Source N] citations.
 *
 * It produces plain data that React renders as text, so model output can never become HTML.
 * Anything it doesn't recognise (tables, links, raw HTML) is shown verbatim.
 */

const BULLET = /^\s*[-*•]\s+(.*)$/
const NUMBERED = /^\s*(\d{1,3})[.)]\s+(.*)$/
const HEADING = /^\s{0,3}#{1,6}\s+(.*)$/
const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[\s*Source\s+\d+\s*\])/gi

/** Split one line into text, bold, code and citation pieces. */
export function parseInline(text) {
  const parts = []
  for (const piece of text.split(INLINE)) {
    if (!piece) continue
    if (/^\*\*[^*]+\*\*$/.test(piece)) parts.push({ type: 'bold', text: piece.slice(2, -2) })
    else if (/^`[^`]+`$/.test(piece)) parts.push({ type: 'code', text: piece.slice(1, -1) })
    else if (/^\[\s*Source\s+\d+\s*\]$/i.test(piece)) {
      parts.push({ type: 'cite', text: `Source ${piece.match(/\d+/)[0]}` })
    } else parts.push({ type: 'text', text: piece })
  }
  return parts
}

/** Group lines into paragraphs and lists. */
export function parseAnswer(answer) {
  const blocks = []
  let paragraph = null
  let list = null

  const closeAll = () => {
    paragraph = null
    list = null
  }

  for (const line of String(answer ?? '').replace(/\r\n?/g, '\n').split('\n')) {
    if (!line.trim()) {
      closeAll()
      continue
    }
    const bullet = line.match(BULLET)
    const numbered = line.match(NUMBERED)
    if (bullet || numbered) {
      const ordered = Boolean(numbered)
      if (!list || list.ordered !== ordered) {
        list = { type: 'list', ordered, start: ordered ? Number(numbered[1]) : undefined, items: [] }
        blocks.push(list)
      }
      list.items.push(ordered ? numbered[2] : bullet[1])
      paragraph = null
      continue
    }
    const heading = line.match(HEADING)
    if (heading) {
      blocks.push({ type: 'heading', text: heading[1] })
      closeAll()
      continue
    }
    if (list && /^\s{2,}\S/.test(line)) {
      // Indented continuation of the previous list item.
      list.items[list.items.length - 1] += ` ${line.trim()}`
      continue
    }
    list = null
    if (!paragraph) {
      paragraph = { type: 'paragraph', lines: [] }
      blocks.push(paragraph)
    }
    paragraph.lines.push(line.trim())
  }
  return blocks
}
