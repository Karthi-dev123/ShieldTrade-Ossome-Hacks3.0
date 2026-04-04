const PAGE = {
  dashboard: { title: 'Control Room', subtitle: 'Minimal operational view' },
  chat: { title: 'Agent Chat Console', subtitle: 'Primary workflow for command execution' },
  agents: { title: 'Agent Registry', subtitle: 'Status and ownership overview' },
  portfolio: { title: 'Portfolio', subtitle: 'Paper trading positions and logs' },
  strategies: { title: 'Strategies', subtitle: 'Automation templates' },
  risk: { title: 'Risk Monitor', subtitle: 'Policy and guardrails' },
  settings: { title: 'Settings', subtitle: 'Runtime and environment setup' },
};

export default function TopBar({ page, setPage }) {
  const info = PAGE[page] ?? PAGE.chat;

  return (
    <header className="glass-card px-4 py-3 flex items-center gap-3 max-[700px]:flex-wrap">
      <div className="min-w-0">
        <h1 className="title-font text-xl leading-none">{info.title}</h1>
        <p className="text-xs text-[var(--muted)] mt-1">{info.subtitle}</p>
      </div>

      <div className="ml-auto flex items-center gap-2 max-[700px]:w-full max-[700px]:ml-0">
        <div className="soft-card h-10 px-3 flex items-center gap-2 flex-1 min-w-[170px]">
          <SearchIcon />
          <input
            type="text"
            placeholder="Search here..."
            className="bg-transparent border-0 outline-none text-sm text-[var(--text)] placeholder:text-[var(--muted)] w-full"
          />
        </div>

        <button
          onClick={() => setPage('chat')}
          className="h-10 px-3 rounded-xl text-sm font-semibold"
          style={{ background: 'var(--accent)', color: '#1a2000' }}
        >
          Open Chat
        </button>

        <div className="soft-card h-10 px-3 flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-white/15 border border-white/25" />
          <div className="text-xs leading-tight hidden sm:block">
            <div className="text-[var(--text)]">Team Operator</div>
            <div className="text-[var(--muted)]">secure mode</div>
          </div>
        </div>
      </div>
    </header>
  );
}

function SearchIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-4 h-4 text-[var(--muted)]">
      <circle cx="9" cy="9" r="5" />
      <path d="m13 13 4 4" />
    </svg>
  );
}
