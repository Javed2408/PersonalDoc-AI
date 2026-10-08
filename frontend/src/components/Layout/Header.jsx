import Icon from '../Common/Icon.jsx'
import StatusIndicator from '../Common/StatusIndicator.jsx'

export default function Header({ service, drawerOpen, onToggleDrawer, selectedCount, onNewChat, canStartNewChat }) {
  return (
    <header className="app-header">
      <div className="app-header__start">
        {/* Only shown on narrow screens, where the document sidebar becomes a drawer. */}
        <button
          type="button"
          className="icon-button app-header__drawer-toggle"
          aria-label={drawerOpen ? 'Close documents' : 'Open documents'}
          aria-expanded={drawerOpen}
          aria-controls="document-sidebar"
          onClick={onToggleDrawer}
        >
          <Icon name="library" size={18} />
          {selectedCount > 0 && <span className="app-header__badge">{selectedCount}</span>}
        </button>
        <span className="app-header__brand">PersonalDoc AI</span>
      </div>

      <div className="app-header__end">
        <button
          type="button"
          className="button button--ghost app-header__new-chat"
          onClick={onNewChat}
          disabled={!canStartNewChat}
        >
          <Icon name="plus" size={15} />
          <span className="app-header__new-chat-label">New chat</span>
        </button>
        <StatusIndicator
          tone={service.tone}
          label={service.label}
          title={service.model ? `Answers by ${service.model}, running locally` : undefined}
        />
      </div>
    </header>
  )
}
