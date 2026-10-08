import { useEffect, useState } from 'react'

const SHOW_ELAPSED_AFTER_S = 3
const SLOW_HINT_AFTER_S = 15

// One honest state: the backend searches and generates in a single request, so there are no
// separate stages to report. Elapsed time reassures during slow local inference.
export default function ThinkingIndicator() {
  const [seconds, setSeconds] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="thinking">
      <span className="thinking__dots" aria-hidden="true">
        <span />
        <span />
        <span />
      </span>
      <span>
        <span role="status">Searching your documents and writing an answer…</span>
        {/* Visual only: a ticking counter would be re-announced every second. */}
        {seconds >= SHOW_ELAPSED_AFTER_S && (
          <span className="thinking__elapsed" aria-hidden="true">
            {' '}
            {seconds}s
          </span>
        )}
      </span>
      {seconds >= SLOW_HINT_AFTER_S && (
        <span className="thinking__hint">Local models can be slow, especially on the first question.</span>
      )}
    </div>
  )
}
