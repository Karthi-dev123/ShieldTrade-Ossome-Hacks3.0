const positions = [
  { symbol: 'NVDA', side: 'Long', status: 'Open' },
  { symbol: 'AAPL', side: 'Long', status: 'Open' },
  { symbol: 'MSFT', side: 'Long', status: 'Open' },
];

export default function Portfolio() {
  return (
    <div className="page-wrap">
      <div className="glass-card p-5 h-full overflow-y-auto">
        <h2 className="title-font text-xl">Portfolio Snapshot</h2>
        <p className="text-sm text-[var(--muted)] mt-1">Minimal visibility mode. Detailed analytics intentionally hidden.</p>

        <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="soft-card p-3">
            <div className="text-xs text-[var(--muted)]">Account Mode</div>
            <div className="mt-1">Paper Trading</div>
          </div>
          <div className="soft-card p-3">
            <div className="text-xs text-[var(--muted)]">Open Positions</div>
            <div className="mt-1">{positions.length} active</div>
          </div>
          <div className="soft-card p-3">
            <div className="text-xs text-[var(--muted)]">Execution Status</div>
            <div className="mt-1">Healthy</div>
          </div>
        </div>

        <div className="mt-4 space-y-2">
          {positions.map((p) => (
            <div key={p.symbol} className="soft-card p-3 flex items-center justify-between">
              <div>
                <div className="title-font text-base">{p.symbol}</div>
                <div className="text-xs text-[var(--muted)]">{p.side} position</div>
              </div>
              <span className="text-xs px-2 py-1 rounded-lg" style={{ background: 'rgba(255,255,255,0.08)' }}>
                {p.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
