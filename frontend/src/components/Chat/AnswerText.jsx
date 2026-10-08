import { Fragment } from 'react'
import { parseAnswer, parseInline } from '../../utils/answerFormat.js'

// Model output is untrusted: it is only ever rendered as React text nodes, never as HTML.
function Inline({ text }) {
  return parseInline(text).map((part, index) => {
    if (part.type === 'bold') return <strong key={index}>{part.text}</strong>
    if (part.type === 'code') return <code key={index}>{part.text}</code>
    if (part.type === 'cite') return <span key={index} className="cite">{part.text}</span>
    return <Fragment key={index}>{part.text}</Fragment>
  })
}

export default function AnswerText({ text }) {
  return (
    <div className="answer-text">
      {parseAnswer(text).map((block, index) => {
        if (block.type === 'heading') {
          return (
            <p key={index} className="answer-text__heading">
              <Inline text={block.text} />
            </p>
          )
        }
        if (block.type === 'list') {
          const List = block.ordered ? 'ol' : 'ul'
          return (
            <List key={index} start={block.ordered && block.start !== 1 ? block.start : undefined}>
              {block.items.map((item, itemIndex) => (
                <li key={itemIndex}>
                  <Inline text={item} />
                </li>
              ))}
            </List>
          )
        }
        return (
          <p key={index}>
            {block.lines.map((line, lineIndex) => (
              <Fragment key={lineIndex}>
                {lineIndex > 0 && <br />}
                <Inline text={line} />
              </Fragment>
            ))}
          </p>
        )
      })}
    </div>
  )
}
