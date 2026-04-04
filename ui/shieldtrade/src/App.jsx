import { useState } from 'react';
import Sidebar from './components/Sidebar';
import TopBar from './components/TopBar';
import Dashboard from './pages/Dashboard';
import Chat from './pages/Chat';
import Agents from './pages/Agents';
import Portfolio from './pages/Portfolio';
import Placeholder from './pages/Placeholder';
import Settings from './pages/Settings';

function App() {
  const [page, setPage] = useState('chat');

  const renderPage = () => {
    switch (page) {
      case 'dashboard':
        return <Dashboard setPage={setPage} />;
      case 'chat':
        return <Chat />;
      case 'agents':
        return <Agents setPage={setPage} />;
      case 'portfolio':
        return <Portfolio />;
      case 'strategies':
        return <Placeholder title="Strategies" subtitle="Compose and test execution playbooks." />;
      case 'risk':
        return <Placeholder title="Risk Monitor" subtitle="Policy checks and guardrails stay centralized here." />;
      case 'settings':
        return <Settings />;
      default:
        return <Chat />;
    }
  };

  return (
    <>
      <div className="liquid-layer">
        <span className="liquid-orb liquid-orb-a" />
        <span className="liquid-orb liquid-orb-b" />
        <span className="liquid-orb liquid-orb-c" />
      </div>
      <div className="app-shell relative z-10">
        <Sidebar page={page} setPage={setPage} />
        <main className="app-main">
          <TopBar page={page} setPage={setPage} />
          <section className="app-content">{renderPage()}</section>
        </main>
      </div>
    </>
  );
}

export default App;
