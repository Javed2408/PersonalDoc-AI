import { useEffect, useRef } from 'react'
import Icon from '../Common/Icon.jsx'
import DocumentLibrary from '../Documents/DocumentLibrary.jsx'

/** Persistent on wide screens; a drawer on narrow ones (see the 720px breakpoint in global.css). */
export default function Sidebar({ open, onClose, library, selection }) {
  const panelRef = useRef(null)

  // When the drawer opens, move focus into it; Escape closes it.
  useEffect(() => {
    if (!open) return undefined
    panelRef.current?.querySelector('button, input')?.focus()
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [open, onClose])

  return (
    <>
      {/* Pointer-only backdrop; the drawer's Close button and Escape do the same for keyboards. */}
      {open && <div className="sidebar-backdrop" aria-hidden="true" onClick={onClose} />}
      <aside
        id="document-sidebar"
        ref={panelRef}
        className={`sidebar${open ? ' sidebar--open' : ''}`}
        aria-label="Documents"
      >
        <button type="button" className="icon-button sidebar__close" aria-label="Close documents" onClick={onClose}>
          <Icon name="close" size={16} />
        </button>
        <DocumentLibrary library={library} selection={selection} />
      </aside>
    </>
  )
}
