import DocumentLibrary from '../Documents/DocumentLibrary.jsx'

export default function Sidebar() {
  return (
    <aside className="sidebar" aria-label="Documents">
      <DocumentLibrary />
    </aside>
  )
}
