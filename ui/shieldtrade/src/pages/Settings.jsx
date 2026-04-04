import { useState } from 'react';
import { policyRules, rawPolicyYaml, recommendationSnapshot, riskDecisionSnapshot, tradeLogSnapshot } from '../data/backendState';

const timelineSeed = [
  { id: 's1', stage: 'Analyst', action: 'Generated recommendation JSON payload', ts: recommendationSnapshot.timestamp },
  { id: 's2', stage: 'Risk Manager', action: 'Issued delegation token after checks', ts: riskDecisionSnapshot.timestamp },
  { id: 's3', stage: 'Trader', action: 'Submitted paper order for execution', ts: tradeLogSnapshot.timestamp },
];

export default function Settings() {
  const [showRaw, setShowRaw] = useState(false);

  return (
    <div className="page-wrap">
      <div className="h-full min-h-0 overflow-y-auto pr-1">
        <div className="grid grid-cols-12 gap-3">
          <section className="glass-card p-4 col-span-12 xl:col-span-6">
            <div className="mb-3">
              <h3 className="title-font text-base">Logs & Transparency</h3>
              <div className="text-xs text-[var(--muted)] mt-1">Auditable timeline: Analyst to Risk to Trader</div>
            </div>

            <div className="h-[360px] overflow-y-auto pr-1 space-y-2">
              {timelineSeed.map((item) => (
                <div key={item.id} className="soft-card p-2.5 text-sm">
                  <div className="flex justify-between">
                    <span className="font-semibold">{item.stage}</span>
                    <span className="text-[11px] text-[var(--muted)]">{isoToShort(item.ts)}</span>
                  </div>
                  <div className="text-[13px] mt-1">{item.action}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="glass-card p-4 col-span-12 xl:col-span-6">
            <div className="mb-3">
              <h3 className="title-font text-base">Policy Rules Viewer</h3>
              <div className="text-xs text-[var(--muted)] mt-1">Simple cards + raw YAML mode</div>
            </div>

            <div className="flex gap-2 mb-3">
              <button onClick={() => setShowRaw(false)} className="px-2.5 py-1.5 text-xs rounded-lg border" style={!showRaw ? activeBtnStyle('#82b9ff') : inactiveBtnStyle()}>Simple</button>
              <button onClick={() => setShowRaw(true)} className="px-2.5 py-1.5 text-xs rounded-lg border" style={showRaw ? activeBtnStyle('#82b9ff') : inactiveBtnStyle()}>Advanced YAML</button>
            </div>

            {!showRaw ? (
              <div className="grid grid-cols-2 gap-2 text-sm">
                <RuleCard label="Order Limit" value={`$${policyRules.maxSingleOrder}`} />
                <RuleCard label="Daily Spend" value={`$${policyRules.maxDailySpend}`} />
                <RuleCard label="Max Position" value={`${policyRules.maxPositionSize}`} />
                <RuleCard label="Paper Only" value={policyRules.paperOnly ? 'Yes' : 'No'} />
                <div className="soft-card p-2.5 col-span-2">
                  <div className="text-xs text-[var(--muted)]">Approved Tickers</div>
                  <div className="mt-1">{policyRules.allowedTickers.join(', ')}</div>
                </div>
              </div>
            ) : (
              <pre className="soft-card p-3 text-[11px] leading-relaxed h-[360px] overflow-auto whitespace-pre-wrap">{rawPolicyYaml}</pre>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}

function RuleCard({ label, value }) {
  return (
    <div className="soft-card p-2.5">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-1">{value}</div>
    </div>
  );
}

function activeBtnStyle(color) {
  return { background: `${color}22`, borderColor: `${color}66`, color };
}

function inactiveBtnStyle() {
  return { background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.15)' };
}

function isoToShort(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} ${d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`;
}
