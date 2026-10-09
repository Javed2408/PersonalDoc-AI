import { Fragment } from 'react'
import { parseAnswer, parseInline } from '../../utils/answerFormat.js'

// Model output is untrusted: it is only ever rendered as React text nodes, never as HTML.
// A [Source N] marker becomes a button only if this answer has a source labelled "Source N";
// any other marker is shown exactly as the model wrote it.
function Inline({ text, citations, onCite }) {
  return parseInline(text).map((part, index) => {
    if (part.type === 'bold') return <strong key={index}>{part.text}</strong>
    if (part.type === 'code') return <code key={index}>{part.text}</code>
    if (part.type === 'cite') {
      const source = citations?.get(part.number)
      if (!source || !onCite) return <Fragment key={index}>{part.raw}</Fragment>
      return (
        <button
          key={index}
          type="button"
          className="cite"
          aria-label={`${source.label}: ${source.original_filename}, page ${source.page_number}`}
          title={`${source.original_filename}, page ${source.page_number}`}
          onClick={() => onCite(source)}
        >
          {source.label}
        </button>
      )
    }
    return <Fragment key={index}>{part.text}</Fragment>
  })
}

export default function AnswerText({ text, citations, onCite }) {
  const inline = (value) => <Inline text={value} citations={citations} onCite={onCite} />

  return (
    <div className="answer-text">
      {parseAnswer(text).map((block, index) => {
        if (block.type === 'heading') {
          return (
            <p key={index} className="answer-text__heading">
              {inline(block.text)}
            </p>
          )
        }
        if (block.type === 'list') {
          const List = block.ordered ? 'ol' : 'ul'
          return (
            <List key={index} start={block.ordered && block.start !== 1 ? block.start : undefined}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>{inline(item)}</li>
              ))}
            </List>
          )
        }
        return (
          <p key={index}>
            {block.lines.map((line, lineIndex) => (
              <Fragment key={lineIndex}>
                {lineIndex > 0 && <br />}
                {inline(line)}
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
