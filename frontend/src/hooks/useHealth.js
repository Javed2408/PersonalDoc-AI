import { useCallback, useEffect, useState } from 'react'
import { getHealth } from '../services/api.js'

// Checked on load, on request (retry buttons) and after chat errors. Never polled.
export function useHealth() {
  const [state, setState] = useState({ status: 'loading', data: null, error: null })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    // Re-checks while connected stay quiet: the header keeps its state until the answer arrives.
    setState((prev) => (prev.status === 'ok' ? prev : { ...prev, status: 'loading', error: null }))

    getHealth({ signal: controller.signal })
      .then((data) => setState({ status: 'ok', data, error: null }))
      .catch((error) => {
        if (error.name === 'AbortError') return
        setState({ status: 'error', data: null, error: error.message })
      })

    return () => controller.abort()
  }, [attempt])

  const retry = useCallback(() => setAttempt((n) => n + 1), [])

  return { ...state, retry }
}
