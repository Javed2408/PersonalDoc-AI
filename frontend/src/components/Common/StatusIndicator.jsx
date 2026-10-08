// The text label accompanies the colour, so status never relies on colour alone.
export default function StatusIndicator({ tone, label, title }) {
  return (
    <span className={`status-indicator status-indicator--${tone}`} title={title}>
      <span className="status-indicator__dot" aria-hidden="true" />
      {label}
    </span>
  )
}
