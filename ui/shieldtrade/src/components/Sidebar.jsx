import { motion } from 'framer-motion';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: DashboardIcon },
  { id: 'chat', label: 'Command Chat', icon: ChatIcon },
  { id: 'agents', label: 'Agents', icon: AgentIcon },
  { id: 'portfolio', label: 'Portfolio', icon: WalletIcon },
  { id: 'risk', label: 'Risk', icon: ShieldIcon },
  { id: 'settings', label: 'Settings', icon: GearIcon },
];

export default function Sidebar({ page, setPage }) {
  return (
    <aside className="glass-card w-[250px] min-w-[250px] p-4 flex flex-col gap-4 max-[900px]:w-full max-[900px]:min-w-0 max-[900px]:flex-row max-[900px]:items-center max-[900px]:overflow-x-auto">
      <div className="soft-card px-3 py-3 flex items-center gap-3 min-w-[220px] max-[900px]:min-w-[180px]">
        <div className="w-9 h-9 rounded-xl flex items-center justify-center" style={{ background: 'var(--accent-soft)', border: '1px solid rgba(215, 241, 74, 0.3)' }}>
          <ShieldIcon color="var(--accent)" />
        </div>
        <div>
          <div className="title-font text-xl leading-none">ShieldTrade</div>
          <div className="text-xs text-[var(--muted)]">Secure agent desk</div>
        </div>
      </div>

      <div className="flex-1 flex flex-col gap-2 max-[900px]:flex-row max-[900px]:items-center">
        {NAV.map((item) => (
          <motion.button
            key={item.id}
            onClick={() => setPage(item.id)}
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            className="w-full max-[900px]:w-auto flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors"
            style={
              page === item.id
                ? {
                    background: 'var(--accent-soft)',
                    border: '1px solid rgba(215, 241, 74, 0.36)',
                    color: 'var(--accent)',
                  }
                : {
                    background: 'rgba(255,255,255,0.04)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    color: 'var(--text)',
                  }
            }
          >
            <item.icon color={page === item.id ? 'var(--accent)' : 'var(--muted)'} />
            <span className="whitespace-nowrap">{item.label}</span>
          </motion.button>
        ))}
      </div>

      <div className="soft-card px-3 py-2.5 flex items-center gap-2 max-[900px]:hidden">
        <span className="dot-live" />
        <div>
          <div className="text-xs text-[var(--text)]">Paper Account Online</div>
          <div className="text-[11px] text-[var(--muted)]">gateway:18789</div>
        </div>
      </div>
    </aside>
  );
}

function iconWrap(path, color = 'currentColor') {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke={color} strokeWidth="1.6" className="w-4 h-4">
      {path}
    </svg>
  );
}

function DashboardIcon({ color }) {
  return iconWrap(
    <>
      <rect x="3" y="3" width="6" height="6" rx="1.2" />
      <rect x="11" y="3" width="6" height="6" rx="1.2" />
      <rect x="3" y="11" width="6" height="6" rx="1.2" />
      <rect x="11" y="11" width="6" height="6" rx="1.2" />
    </>,
    color,
  );
}

function ChatIcon({ color }) {
  return iconWrap(<path d="M17 14a2 2 0 0 1-2 2H8l-4 3V5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v9Z" />, color);
}

function AgentIcon({ color }) {
  return iconWrap(
    <>
      <circle cx="10" cy="7" r="3" />
      <path d="M4 17a6 6 0 0 1 12 0" />
    </>,
    color,
  );
}

function WalletIcon({ color }) {
  return iconWrap(
    <>
      <rect x="3" y="5" width="14" height="10" rx="2" />
      <path d="M6 5V4a2 2 0 0 1 2-2h6" />
      <circle cx="13.5" cy="10" r="1" />
    </>,
    color,
  );
}

function ShieldIcon({ color }) {
  return iconWrap(<path d="M10 2 4 4.5v4.3c0 3.8 2.5 6.8 6 8.2 3.5-1.4 6-4.4 6-8.2V4.5L10 2Z" />, color);
}

function GearIcon({ color }) {
  return iconWrap(
    <>
      <circle cx="10" cy="10" r="2.5" />
      <path d="M10 3.5v1.4M10 15.1v1.4M3.5 10h1.4M15.1 10h1.4M5.3 5.3l1 1M13.7 13.7l1 1M5.3 14.7l1-1M13.7 6.3l1-1" />
    </>,
    color,
  );
}
