const agents = [
  { name: 'Analyst', role: 'Market analysis and recommendation', state: 'Ready' },
  { name: 'Risk Manager', role: 'Deterministic policy verification', state: 'Guarding' },
  { name: 'Trader', role: 'Paper order execution and logging', state: 'Standby' },
];

export default function Agents({ setPage }) {
  return (
    <div className="page-wrap">
      <div className="glass-card p-5 h-full overflow-y-auto">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div>
            <h2 className="title-font text-xl">Agent Registry</h2>
            <p className="text-sm text-[var(--muted)] mt-1">Clean summary only, full actions run through chat.</p>
          </div>
          <button
            onClick={() => setPage('chat')}
            className="px-3.5 py-2 rounded-xl text-sm font-semibold"
            style={{ background: 'var(--accent)', color: '#1d2207' }}
          >
            Open Chat
          </button>
        </div>

        <div className="mt-4 space-y-3">
          {agents.map((agent) => (
            <div key={agent.name} className="soft-card p-4">
              <div className="flex items-center justify-between">
                <div className="title-font text-lg">{agent.name}</div>
                <span className="text-xs px-2 py-1 rounded-lg" style={{ background: 'rgba(255,255,255,0.08)' }}>
                  {agent.state}
                </span>
              </div>
              <div className="text-sm text-[var(--muted)] mt-2">{agent.role}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
