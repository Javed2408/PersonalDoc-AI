import Header from './components/Layout/Header.jsx'
import Sidebar from './components/Layout/Sidebar.jsx'
import BackendStatusCard from './components/Common/BackendStatusCard.jsx'
import { useHealth } from './hooks/useHealth.js'

export default function App() {
  const health = useHealth()

  return (
    <div className="app-shell">
      <Header status={health.status} />
      <div className="app-body">
        <Sidebar />
        <main className="workspace">
          <section className="welcome">
            <h1>Your documents stay here.</h1>
            <p className="welcome__lede">Ask them questions.</p>
          </section>
          <BackendStatusCard {...health} />
        </main>
      </div>
    </div>
  )
}
