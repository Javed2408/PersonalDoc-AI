/**
 * What the header and notices say about the backend and the local model.
 * `tone` drives the colour; the label always carries the meaning too.
 */
export function serviceStatus(health) {
  if (health.status === 'loading') return { tone: 'pending', label: 'Connecting…', problem: null }
  if (health.status === 'error') return { tone: 'error', label: 'Backend offline', problem: 'backend' }

  const llm = health.data?.llm
  // An older backend without LLM status: say only what is known.
  if (!llm) return { tone: 'ok', label: 'Backend ready', problem: null }
  if (llm.status === 'ready') return { tone: 'ok', label: 'Local / Ready', problem: null, model: llm.model }
  if (llm.status === 'model_missing') {
    return { tone: 'warning', label: 'Model not installed', problem: 'model_missing', model: llm.model }
  }
  return { tone: 'warning', label: 'Ollama unavailable', problem: 'llm', model: llm.model }
}
