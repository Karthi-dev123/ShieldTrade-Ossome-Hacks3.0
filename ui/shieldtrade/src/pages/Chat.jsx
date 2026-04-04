import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  agentProfiles,
  bars,
  policyRules,
  recommendationSnapshot,
  riskDecisionSnapshot,
  seedQuotes,
  symbols,
} from '../data/backendState';

const AGENT_COLORS = {
  ANALYST: '#82b9ff',
  RISK: '#ffd67b',
  TRADER: '#d7f14a',
};

const WORKFLOW = ['User', 'Analyst', 'Risk Manager', 'Trader', 'Alpaca'];

const INITIAL_MESSAGES = [
  { id: 'm1', role: 'agent', agent: 'ANALYST', text: 'Analysis queue ready. Select a symbol to begin.', ts: shortTime() },
  { id: 'm2', role: 'agent', agent: 'RISK', text: 'Policy engine linked. Waiting for recommendation.', ts: shortTime() },
];

export default function Chat() {
  const [activeAgent, setActiveAgent] = useState('ANALYST');
  const [agentStatus, setAgentStatus] = useState({ ANALYST: 'Idle', RISK: 'Idle', TRADER: 'Idle' });
  const [messages, setMessages] = useState(INITIAL_MESSAGES);
  const [input, setInput] = useState('deploy NVDA with 500');

  const [symbol, setSymbol] = useState('NVDA');
  const [timeframe, setTimeframe] = useState('1D');
  const [chartType, setChartType] = useState('line');
  const [livePrice, setLivePrice] = useState(seedQuotes.NVDA);

  const [recommendation, setRecommendation] = useState({ ...recommendationSnapshot });
  const [simulationMode, setSimulationMode] = useState(true);

  const [issuedAt, setIssuedAt] = useState(new Date(riskDecisionSnapshot.timestamp).getTime());
  const [ttlSeconds, setTtlSeconds] = useState(riskDecisionSnapshot.expires_in_seconds);

  const [executionState, setExecutionState] = useState('Pending');
  const [workflowIndex, setWorkflowIndex] = useState(0);
  const [toasts, setToasts] = useState([]);

  const chartSeries = bars[symbol]?.[timeframe] ?? [];
  const currentPrice = Number(livePrice.toFixed(2));

  useEffect(() => {
    const interval = setInterval(() => {
      setLivePrice((prev) => {
        const drift = (Math.random() - 0.5) * 0.8;
        return Math.max(1, prev + drift);
      });
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    setLivePrice(seedQuotes[symbol] ?? 100);
    setRecommendation((prev) => ({
      ...prev,
      symbol,
      price_target: Number((seedQuotes[symbol] * 1.05).toFixed(2)),
      qty: symbol === 'TSLA' ? 8 : 12,
    }));
  }, [symbol]);

  useEffect(() => {
    const timer = setInterval(() => {
      setTtlSeconds((v) => v);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const secondsLeft = useMemo(() => {
    const now = Date.now();
    const elapsed = Math.floor((now - issuedAt) / 1000);
    return Math.max(0, ttlSeconds - elapsed);
  }, [issuedAt, ttlSeconds]);

  const estimatedCost = recommendation.qty * currentPrice;

  const checks = useMemo(() => {
    const tickerApproved = policyRules.allowedTickers.includes(recommendation.symbol);
    const sizeOk = estimatedCost <= policyRules.maxSingleOrder;
    const sharesOk = recommendation.qty <= policyRules.maxPositionSize;
    const marketHours = true;

    return [
      { name: 'Ticker Approved', pass: tickerApproved, detail: recommendation.symbol },
      { name: 'Order Size', pass: sizeOk, detail: `$${estimatedCost.toFixed(2)} <= $${policyRules.maxSingleOrder}` },
      { name: 'Position Limit', pass: sharesOk, detail: `${recommendation.qty} <= ${policyRules.maxPositionSize}` },
      { name: 'Market Hours', pass: marketHours, detail: 'Check disabled in dev policy' },
    ];
  }, [estimatedCost, recommendation.qty, recommendation.symbol]);

  const riskAllowed = checks.every((c) => c.pass);
  const delegationValid = riskAllowed && secondsLeft > 0;
  const riskLabel = estimatedCost > 2200 ? 'High' : estimatedCost > 1400 ? 'Medium' : 'Low';

  function addToast(type, message) {
    const id = Math.random().toString(36).slice(2, 8);
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 3200);
  }

  function addMessage(role, text, agent = null) {
    setMessages((prev) => [...prev, { id: Math.random().toString(36), role, text, agent, ts: shortTime() }]);
  }

  async function runWorkflow(command) {
    const text = command.toLowerCase();
    addMessage('user', command);
    setInput('');

    if (!text.includes('deploy') && !text.includes('buy') && !text.includes('sell')) {
      setActiveAgent('ANALYST');
      setWorkflowIndex(1);
      addMessage('agent', 'Use a deploy/buy/sell command to start full multi-agent flow.', 'ANALYST');
      return;
    }

    setAgentStatus({ ANALYST: 'Processing', RISK: 'Idle', TRADER: 'Idle' });
    setActiveAgent('ANALYST');
    setWorkflowIndex(1);
    await pause(400);
    addMessage('agent', `Recommendation prepared for ${recommendation.symbol}: ${recommendation.action} ${recommendation.qty}.`, 'ANALYST');

    setAgentStatus({ ANALYST: 'Completed', RISK: 'Processing', TRADER: 'Idle' });
    setActiveAgent('RISK');
    setWorkflowIndex(2);
    await pause(500);

    if (!riskAllowed) {
      addMessage('agent', 'Policy check failed. Delegation rejected.', 'RISK');
      addToast('error', 'Trade blocked: policy violation detected.');
      setExecutionState('Failed');
      setAgentStatus({ ANALYST: 'Completed', RISK: 'Completed', TRADER: 'Idle' });
      return;
    }

    addMessage('agent', 'Policy checks passed. Delegation token issued.', 'RISK');
    setIssuedAt(Date.now());

    setAgentStatus({ ANALYST: 'Completed', RISK: 'Completed', TRADER: 'Processing' });
    setActiveAgent('TRADER');
    setWorkflowIndex(3);
    await pause(500);

    if (!riskAllowed) {
      addToast('warn', 'Delegation expired before execution.');
      addMessage('agent', 'Delegation token expired. Execution halted.', 'TRADER');
      setExecutionState('Failed');
      setAgentStatus({ ANALYST: 'Completed', RISK: 'Completed', TRADER: 'Completed' });
      return;
    }

    if (simulationMode) {
      setExecutionState('Executed');
      setWorkflowIndex(4);
      addMessage('agent', 'Simulation mode: order marked executed on paper account.', 'TRADER');
      addToast('success', 'Trade executed successfully in simulation mode.');
    } else {
      setExecutionState('Pending');
      addMessage('agent', 'Execution queued. Awaiting broker confirmation.', 'TRADER');
      addToast('warn', 'Execution queued. Waiting for broker response.');
    }

    setAgentStatus({ ANALYST: 'Completed', RISK: 'Completed', TRADER: 'Completed' });
  }

  async function executeTrade() {
    if (!delegationValid) {
      addToast('error', 'Trade blocked: no valid delegation token.');
      setExecutionState('Failed');
      return;
    }

    setExecutionState('Pending');
    addToast('success', 'Execution started via ArmorIQ -> Alpaca.');

    try {
      const response = await fetch('http://localhost:5000/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: recommendation.symbol,
          qty: recommendation.qty,
          amount_usd: estimatedCost
        })
      });
      const data = await response.json();
      
      if (data.status === 'success') {
        setExecutionState('Executed');
        setWorkflowIndex(4);
        addToast('success', `Trade executed: ${data.order.order_id}`);
        addMessage('agent', `Alpaca order successful! ArmorIQ Check ID: ${data.validation.audit_id}`, 'TRADER');
      } else {
        setExecutionState('Failed');
        addToast('error', `Trade failed: ${data.message}`);
        addMessage('agent', `Execution blocked: ${data.message}`, 'TRADER');
      }
    } catch (e) {
      setExecutionState('Failed');
      addToast('error', `Backend error: ${e.message}`);
    }
  }

  const activeMeta = agentProfiles[activeAgent];

  return (
    <div className="page-wrap">
      <div className="h-full min-h-0 overflow-y-auto pr-1">
        <div className="grid grid-cols-12 gap-3">
          <Panel className="col-span-12 xl:col-span-7" title="Multi-Agent Interaction Panel" subtitle="Chat is the primary control surface">
            <div className="flex flex-wrap gap-2 mb-3">
              {Object.entries(agentProfiles).map(([key, val]) => (
                <button
                  key={key}
                  onClick={() => setActiveAgent(key)}
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold border"
                  style={
                    activeAgent === key
                      ? { background: `${AGENT_COLORS[key]}22`, borderColor: `${AGENT_COLORS[key]}88`, color: AGENT_COLORS[key] }
                      : { background: 'rgba(255,255,255,0.06)', borderColor: 'rgba(255,255,255,0.14)' }
                  }
                >
                  {val.icon} {val.label}
                </button>
              ))}
            </div>

            <div className="soft-card p-3 mb-3">
              <div className="text-xs text-[var(--muted)]">Current Active Agent</div>
              <div className="text-sm mt-1 font-semibold" style={{ color: AGENT_COLORS[activeAgent] }}>
                {activeMeta.icon} {activeMeta.label}
              </div>
              <div className="text-xs text-[var(--muted)] mt-1">{activeMeta.role}</div>
              <div className="mt-2 flex gap-2 flex-wrap">
                {Object.entries(agentStatus).map(([k, status]) => (
                  <span key={k} className="text-[11px] px-2 py-1 rounded-lg border" style={{ borderColor: 'rgba(255,255,255,0.16)', background: 'rgba(255,255,255,0.05)' }}>
                    {agentProfiles[k].label}: {status}
                  </span>
                ))}
              </div>
            </div>

            <div className="min-h-[210px] max-h-[300px] overflow-y-auto space-y-2 pr-1">
              {messages.map((m) => (
                <motion.div
                  key={m.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`rounded-xl px-3 py-2 text-sm ${m.role === 'user' ? 'ml-auto max-w-[80%]' : 'max-w-[86%]'}`}
                  style={{ background: m.role === 'user' ? 'rgba(255,255,255,0.14)' : 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.14)' }}
                >
                  {m.agent && <div className="text-xs mb-1" style={{ color: AGENT_COLORS[m.agent] }}>{agentProfiles[m.agent]?.label}</div>}
                  <div>{m.text}</div>
                  <div className="text-[11px] text-[var(--muted)] mt-1">{m.ts}</div>
                </motion.div>
              ))}
            </div>

            <div className="mt-3 flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && runWorkflow(input)}
                placeholder="Type deploy command..."
                className="flex-1 bg-transparent border rounded-lg px-3 py-2 text-sm outline-none"
                style={{ borderColor: 'rgba(255,255,255,0.18)', background: 'rgba(255,255,255,0.05)' }}
              />
              <button onClick={() => runWorkflow(input)} className="px-4 py-2 rounded-lg text-sm font-semibold" style={{ background: 'var(--accent)', color: '#192103' }}>
                Run
              </button>
            </div>
          </Panel>

          <Panel className="col-span-12 xl:col-span-5" title="Live Trading & Market Data" subtitle="Quote, bars, symbol and timeframe controls">
            <div className="flex flex-wrap gap-2 mb-3">
              <select value={symbol} onChange={(e) => setSymbol(e.target.value)} className="px-3 py-1.5 rounded-lg text-sm" style={{ background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.16)' }}>
                {symbols.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
              {['1D', '1W', '1M'].map((tf) => (
                <button
                  key={tf}
                  onClick={() => setTimeframe(tf)}
                  className="px-2.5 py-1.5 rounded-lg text-xs border"
                  style={timeframe === tf ? { background: 'rgba(130,185,255,0.2)', borderColor: 'rgba(130,185,255,0.6)' } : { background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.15)' }}
                >
                  {tf}
                </button>
              ))}
              {['line', 'candle'].map((ct) => (
                <button
                  key={ct}
                  onClick={() => setChartType(ct)}
                  className="px-2.5 py-1.5 rounded-lg text-xs border"
                  style={chartType === ct ? { background: 'rgba(215,241,74,0.2)', borderColor: 'rgba(215,241,74,0.55)' } : { background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.15)' }}
                >
                  {ct}
                </button>
              ))}
            </div>

            <div className="soft-card p-3 mb-3">
              <div className="text-xs text-[var(--muted)]">Live Price</div>
              <div className="text-2xl title-font mt-1">${currentPrice.toFixed(2)}</div>
              <div className="text-xs text-[var(--muted)] mt-1">Symbol: {symbol} | Timeframe: {timeframe}</div>
            </div>

            <Chart series={chartSeries} type={chartType} />
          </Panel>

          <Panel className="col-span-12 xl:col-span-4" title="Risk Validation" subtitle="Deterministic policy engine checks">
            <div className="space-y-2">
              {checks.map((c) => (
                <div key={c.name} className="flex items-center justify-between text-sm soft-card px-2.5 py-2">
                  <div>
                    <div>{c.pass ? '[PASS]' : '[FAIL]'} {c.name}</div>
                    <div className="text-[11px] text-[var(--muted)]">{c.detail}</div>
                  </div>
                  <span className="text-xs font-semibold" style={{ color: c.pass ? '#71f0a5' : '#ff9090' }}>{c.pass ? 'PASS' : 'FAIL'}</span>
                </div>
              ))}
            </div>

            <div className="mt-3 soft-card p-2.5">
              <div className="text-xs text-[var(--muted)]">Final Decision</div>
              <div className="text-lg title-font mt-1" style={{ color: riskAllowed ? '#79f0aa' : '#ff8c8c' }}>{riskAllowed ? 'ALLOW' : 'BLOCK'}</div>
              <div className="text-[11px] text-[var(--muted)] mt-1">Intent verification: {riskAllowed ? 'Action verified by policy engine' : 'Action denied by policy engine'}</div>
            </div>

            <RiskMeter label={riskLabel} />
          </Panel>

          <Panel className="col-span-12 xl:col-span-4" title="Delegation Token Viewer" subtitle="From /output/risk-decisions/*.json">
            <KV label="Status" value={delegationValid ? 'APPROVED' : 'REJECTED'} accent={delegationValid ? '#79f0aa' : '#ff8c8c'} />
            <KV label="Symbol" value={recommendation.symbol} />
            <KV label="Max Quantity" value={String(recommendation.qty)} />
            <KV label="Expiry" value={`${secondsLeft}s`} accent={secondsLeft < 60 ? '#ffb17d' : '#e7f0ff'} />
            <div className="text-xs mt-2 text-[var(--muted)]">Token: {riskDecisionSnapshot.delegation_token.slice(0, 8)}...{riskDecisionSnapshot.delegation_token.slice(-6)}</div>
            {secondsLeft < 60 && <div className="mt-2 text-xs" style={{ color: '#ffb17d' }}>Warning: token nearing expiry.</div>}
            {secondsLeft === 0 && <div className="mt-2 text-xs" style={{ color: '#ff8c8c' }}>Token expired. Re-run Risk Manager.</div>}
          </Panel>

          <Panel className="col-span-12 xl:col-span-4" title="Trade Execution" subtitle="Enabled only with valid delegation">
            <div className="soft-card p-2.5 text-sm">
              <div className="flex justify-between"><span>Symbol</span><span>{recommendation.symbol}</span></div>
              <div className="flex justify-between mt-1"><span>Quantity</span><span>{recommendation.qty}</span></div>
              <div className="flex justify-between mt-1"><span>Price</span><span>${currentPrice.toFixed(2)}</span></div>
            </div>

            <div className="mt-3">
              <button
                onClick={executeTrade}
                disabled={!delegationValid}
                className="w-full py-2 rounded-lg text-sm font-semibold disabled:opacity-45 disabled:cursor-not-allowed"
                style={{ background: delegationValid ? 'var(--accent)' : 'rgba(255,255,255,0.12)', color: delegationValid ? '#182001' : '#d1d7e3' }}
              >
                Execute Trade
              </button>
            </div>

            <div className="mt-3 soft-card p-2.5 text-sm">
              <div className="text-xs text-[var(--muted)]">Execution Status</div>
              <div className="mt-1 font-semibold">{executionState}</div>
              {!delegationValid && <div className="text-[11px] mt-1 text-[var(--muted)]">Button disabled: no valid delegation.</div>}
            </div>

            <label className="mt-3 flex items-center gap-2 text-xs">
              <input type="checkbox" checked={simulationMode} onChange={(e) => setSimulationMode(e.target.checked)} />
              Simulation Mode
            </label>
          </Panel>

          <Panel className="col-span-12" title="AI Workflow Visualization" subtitle="User to Analyst to Risk Manager to Trader to Alpaca">
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
              {WORKFLOW.map((step, i) => (
                <div
                  key={step}
                  className="soft-card p-2.5 text-center text-xs"
                  style={i <= workflowIndex ? { borderColor: 'rgba(215,241,74,0.42)', background: 'rgba(215,241,74,0.09)' } : undefined}
                >
                  <div className="font-semibold">{step}</div>
                  <div className="text-[11px] text-[var(--muted)] mt-1">{i < workflowIndex ? 'Completed' : i === workflowIndex ? 'Current' : 'Pending'}</div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>

      <div className="fixed right-5 top-5 z-50 space-y-2">
        <AnimatePresence>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              className="px-3 py-2 rounded-lg text-sm border"
              style={{
                background: 'rgba(16,22,33,0.95)',
                borderColor: toast.type === 'error' ? 'rgba(255,130,130,0.6)' : toast.type === 'warn' ? 'rgba(255,188,122,0.6)' : 'rgba(121,240,170,0.6)',
              }}
            >
              [{toast.type.toUpperCase()}] {toast.message}
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}

function Panel({ title, subtitle, className, children }) {
  return (
    <section className={`glass-card p-4 ${className}`}>
      <div className="mb-3">
        <h3 className="title-font text-base">{title}</h3>
        <div className="text-xs text-[var(--muted)] mt-1">{subtitle}</div>
      </div>
      {children}
    </section>
  );
}

function KV({ label, value, accent }) {
  return (
    <div className="flex items-center justify-between text-sm soft-card px-2.5 py-2 mb-2">
      <span className="text-[var(--muted)]">{label}</span>
      <span style={accent ? { color: accent, fontWeight: 700 } : undefined}>{value}</span>
    </div>
  );
}

function Chart({ series, type }) {
  if (!series.length) return <div className="soft-card p-3 text-sm">No chart data</div>;

  const width = 420;
  const height = 140;
  const min = Math.min(...series);
  const max = Math.max(...series);
  const range = max - min || 1;

  const points = series
    .map((v, i) => {
      const x = (i / (series.length - 1 || 1)) * (width - 20) + 10;
      const y = height - ((v - min) / range) * (height - 20) - 10;
      return `${x},${y}`;
    })
    .join(' ');

  return (
    <div className="soft-card p-3">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-[150px]">
        <defs>
          <linearGradient id="lineGrad" x1="0" x2="1" y1="0" y2="0">
            <stop offset="0%" stopColor="#82b9ff" />
            <stop offset="100%" stopColor="#d7f14a" />
          </linearGradient>
        </defs>
        <line x1="10" y1={height - 10} x2={width - 10} y2={height - 10} stroke="rgba(255,255,255,0.18)" />

        {type === 'line' ? (
          <>
            <polyline fill="none" stroke="url(#lineGrad)" strokeWidth="3" points={points} strokeLinecap="round" strokeLinejoin="round" />
            {series.map((v, i) => {
              const x = (i / (series.length - 1 || 1)) * (width - 20) + 10;
              const y = height - ((v - min) / range) * (height - 20) - 10;
              return <circle key={i} cx={x} cy={y} r="2.2" fill="#dff78b" />;
            })}
          </>
        ) : (
          series.map((v, i) => {
            const x = (i / (series.length - 1 || 1)) * (width - 30) + 15;
            const y = height - ((v - min) / range) * (height - 20) - 10;
            const open = i === 0 ? v : series[i - 1];
            const openY = height - ((open - min) / range) * (height - 20) - 10;
            const top = Math.min(y, openY);
            const h = Math.abs(y - openY) || 2;
            const up = v >= open;

            return (
              <g key={i}>
                <line x1={x} y1={Math.min(y, openY) - 6} x2={x} y2={Math.max(y, openY) + 6} stroke="rgba(255,255,255,0.45)" />
                <rect x={x - 4} y={top} width="8" height={h} rx="2" fill={up ? 'rgba(121,240,170,0.9)' : 'rgba(255,140,140,0.9)'} />
              </g>
            );
          })
        )}
      </svg>
    </div>
  );
}

function RiskMeter({ label }) {
  const pct = label === 'Low' ? 28 : label === 'Medium' ? 58 : 84;
  const color = label === 'Low' ? '#79f0aa' : label === 'Medium' ? '#ffcf73' : '#ff8d8d';

  return (
    <div className="mt-3 soft-card p-2.5">
      <div className="text-xs text-[var(--muted)]">Risk Meter</div>
      <div className="mt-2 h-2 rounded-full" style={{ background: 'rgba(255,255,255,0.12)' }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, background: color }} />
      </div>
      <div className="text-xs mt-1" style={{ color }}>{label}</div>
    </div>
  );
}

function shortTime() {
  return new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function pause(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
