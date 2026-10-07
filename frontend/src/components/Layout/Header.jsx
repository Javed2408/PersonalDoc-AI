import StatusIndicator from '../Common/StatusIndicator.jsx'

export default function Header({ status }) {
  return (
    <header className="app-header">
      <span className="app-header__brand">PersonalDoc AI</span>
      <StatusIndicator status={status} />
    </header>
  )
}
