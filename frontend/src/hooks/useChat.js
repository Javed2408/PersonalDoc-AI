import { useCallback, useEffect, useReducer, useRef } from 'react'
import { chat } from '../services/api.js'
import { describeChatError } from '../utils/chatErrors.js'

/**
 * The conversation for this browser tab. It lives only in React state: nothing is stored on the
 * server or in the browser, and a reload starts a new chat. Each question is sent on its own;
 * the backend answers from the documents, not from earlier messages.
 *
 * Messages:
 *   { id, role: 'user', content, context }
 *   { id, role: 'assistant', questionId, status: 'pending' | 'answered' | 'not_found' | 'error',
 *     answer, sources, model, error: { title, message } }
 */

let nextId = 0
const newId = (prefix) => `${prefix}-${++nextId}`

function updateMessage(messages, id, changes) {
  return messages.map((message) => (message.id === id ? { ...message, ...changes } : message))
}

function reducer(messages, action) {
  switch (action.type) {
    case 'ask':
      return [
        ...messages,
        { id: action.questionId, role: 'user', content: action.question, context: action.context },
        { id: action.answerId, role: 'assistant', questionId: action.questionId, status: 'pending' },
      ]
    case 'retry':
      return updateMessage(
        updateMessage(messages, action.questionId, { context: action.context }),
        action.answerId,
        { status: 'pending', error: null },
      )
    case 'resolve':
      return updateMessage(messages, action.answerId, {
        status: action.response.status === 'not_found' ? 'not_found' : 'answered',
        answer: action.response.answer,
        sources: action.response.sources ?? [],
        model: action.response.model,
      })
    case 'fail':
      return updateMessage(messages, action.answerId, { status: 'error', error: action.error })
    case 'clear':
      return []
    default:
      return messages
  }
}

export function useChat({ onSettled } = {}) {
  const [messages, dispatch] = useReducer(reducer, [])
  const messagesRef = useRef(messages)
  messagesRef.current = messages
  const controllers = useRef(new Map())
  const onSettledRef = useRef(onSettled)
  onSettledRef.current = onSettled

  const pending = messages.some((message) => message.status === 'pending')
  // Set synchronously when a request starts, so a double Enter can't send twice before a re-render.
  const busy = () => controllers.current.size > 0

  const run = useCallback(async (answerId, question, context) => {
    const controller = new AbortController()
    controllers.current.set(answerId, controller)
    try {
      const response = await chat({ question, documentIds: context.documentIds, signal: controller.signal })
      dispatch({ type: 'resolve', answerId, response })
      onSettledRef.current?.({ response })
    } catch (error) {
      if (error.name === 'AbortError') return
      dispatch({ type: 'fail', answerId, error: describeChatError(error) })
      onSettledRef.current?.({ error })
    } finally {
      controllers.current.delete(answerId)
    }
  }, [])

  /** Ask a question. Returns false (and does nothing) for blank input or while an answer is pending. */
  const send = useCallback(
    (text, context) => {
      const question = text.trim()
      if (!question || busy()) return false
      const questionId = newId('q')
      const answerId = newId('a')
      dispatch({ type: 'ask', question, context, questionId, answerId })
      run(answerId, question, context)
      return true
    },
    [run],
  )

  /** Ask a failed question again, with the documents selected now. The question isn't duplicated. */
  const retry = useCallback(
    (answerId, context) => {
      if (busy()) return
      const current = messagesRef.current
      const answer = current.find((message) => message.id === answerId)
      const question = answer && current.find((message) => message.id === answer.questionId)
      if (!question || answer.status !== 'error') return
      dispatch({ type: 'retry', answerId, questionId: question.id, context })
      run(answerId, question.content, context)
    },
    [run],
  )

  /** Start over: forget the messages and drop any answer still on its way. Documents are untouched. */
  const clear = useCallback(() => {
    controllers.current.forEach((controller) => controller.abort())
    controllers.current.clear()
    dispatch({ type: 'clear' })
  }, [])

  useEffect(() => {
    const active = controllers.current
    return () => active.forEach((controller) => controller.abort())
  }, [])

  return { messages, pending, send, retry, clear }
}
