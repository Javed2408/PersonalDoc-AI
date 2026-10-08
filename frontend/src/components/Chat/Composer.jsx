import { useImperativeHandle, useLayoutEffect, useRef, useState } from 'react'
import Icon from '../Common/Icon.jsx'

// The backend accepts questions up to 2000 characters.
const MAX_QUESTION_LENGTH = 2000

/**
 * Enter sends, Shift+Enter adds a line. While an answer is pending the box stays editable (so the
 * next question can be drafted and focus isn't lost), but sending is disabled.
 */
export default function Composer({ ref, onSubmit, pending, disabled, placeholder }) {
  const [draft, setDraft] = useState('')
  const textareaRef = useRef(null)
  const canSend = !disabled && !pending && draft.trim().length > 0

  useImperativeHandle(ref, () => ({
    focus: () => textareaRef.current?.focus(),
    fill: (text) => {
      setDraft(text)
      requestAnimationFrame(() => {
        const textarea = textareaRef.current
        if (!textarea) return
        textarea.focus()
        textarea.setSelectionRange(text.length, text.length)
      })
    },
  }))

  // Grow with the text, up to the CSS max-height.
  useLayoutEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${textarea.scrollHeight}px`
  }, [draft])

  const submit = () => {
    if (!canSend) return
    if (onSubmit(draft)) setDraft('')
  }

  return (
    <form
      className="composer"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <label htmlFor="question-input" className="visually-hidden">
        Ask a question about your documents
      </label>
      <textarea
        id="question-input"
        ref={textareaRef}
        className="composer__input"
        rows={1}
        value={draft}
        maxLength={MAX_QUESTION_LENGTH}
        placeholder={placeholder}
        disabled={disabled}
        aria-describedby="composer-hint"
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            submit()
          }
        }}
      />
      <button type="submit" className="composer__send" aria-label="Send question" disabled={!canSend}>
        {pending ? <span className="spinner" aria-hidden="true" /> : <Icon name="send" size={18} />}
      </button>
    </form>
  )
}
