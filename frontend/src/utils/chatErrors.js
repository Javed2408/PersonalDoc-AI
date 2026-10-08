/**
 * Turn a failed /api/chat call into a short title and a readable message.
 *
 * The backend's `detail` is written for users, so it is shown as-is wherever it helps. Exceptions:
 * an unreachable Ollama (its detail includes the server address) and unknown documents (the detail
 * lists internal IDs) get plainer wording.
 */
export function describeChatError(error) {
  const detail = error?.message || ''

  if (!error?.status || error.unreachable) {
    return { title: "Can't reach the backend", message: 'Make sure the API server is running, then retry.' }
  }

  switch (error.status) {
    case 503:
      if (/not installed/i.test(detail)) return { title: 'Local model not installed', message: detail }
      if (/ollama/i.test(detail)) {
        return { title: 'Local AI is unavailable', message: 'Make sure Ollama is running, then retry.' }
      }
      return { title: 'Search is unavailable', message: detail }
    case 504:
      return { title: 'The local model took too long', message: `${detail} Please try again.`.trim() }
    case 502:
      return { title: "Couldn't generate an answer", message: detail }
    case 404:
      return {
        title: 'A selected document no longer exists',
        message: 'It may have been deleted. Check the document list and try again.',
      }
    case 409:
      return { title: 'A selected document isn’t ready', message: detail }
    case 422:
      return { title: 'Please check your question', message: detail }
    default:
      return { title: 'Something went wrong', message: detail }
  }
}
