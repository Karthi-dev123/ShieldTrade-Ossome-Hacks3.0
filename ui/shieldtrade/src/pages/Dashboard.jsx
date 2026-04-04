import { recommendationSnapshot, riskDecisionSnapshot, seedQuotes, tradeLogSnapshot } from '../data/backendState';

export default function Dashboard({ setPage }) {
  const currentPrice = seedQuotes[recommendationSnapshot.symbol] ?? recommendationSnapshot.price_target;
  const estimatedCost = currentPrice * recommendationSnapshot.qty;

  return (
    <div className="page-wrap">
      <div className="h-full min-h-0 overflow-y-auto pr-1">
        <div className="grid grid-cols-12 gap-3">
          <section className="glass-card p-5 col-span-12 xl:col-span-7">
            <div className="mb-3">
              <h2 className="title-font text-xl">Analyst Recommendation</h2>
              <p className="text-sm text-[var(--muted)] mt-1">AI output visualization from `/output/reports/*.json`.</p>
            </div>

            <div className="grid grid-cols-2 gap-2 text-sm">
              <InfoCard label="Symbol" value={recommendationSnapshot.symbol} />
              <InfoCard label="Action" value={recommendationSnapshot.action} accent={recommendationSnapshot.action === 'BUY' ? '#7cf2ab' : '#ff9a9a'} />
              <InfoCard label="Quantity" value={`${recommendationSnapshot.qty}`} />
              <InfoCard label="Confidence" value={`${Math.round(recommendationSnapshot.confidence * 100)}%`} />
              <div className="soft-card p-2.5 col-span-2">
                <div className="text-xs text-[var(--muted)]">Reasoning</div>
                <div className="mt-1 text-sm">{recommendationSnapshot.reasoning}</div>
              </div>
              <InfoCard label="Current Price" value={`$${currentPrice.toFixed(2)}`} />
              <InfoCard label="Estimated Cost" value={`$${estimatedCost.toFixed(2)}`} />
            </div>
          </section>

          <section className="glass-card p-5 col-span-12 xl:col-span-5">
            <div className="mb-3">
              <h3 className="title-font text-base">Quick System Snapshot</h3>
              <div className="text-xs text-[var(--muted)] mt-1">Concise overview without clutter.</div>
            </div>

            <div className="space-y-2">
              <InfoCard label="Delegation" value={riskDecisionSnapshot.approved ? 'Approved' : 'Rejected'} accent={riskDecisionSnapshot.approved ? '#7cf2ab' : '#ff9a9a'} />
              <InfoCard label="Latest Trade" value={`${tradeLogSnapshot.ticker} ${tradeLogSnapshot.action}`} />
              <InfoCard label="Execution Status" value={tradeLogSnapshot.order_result.status.replace('OrderStatus.', '')} />
              <InfoCard label="Amount" value={`$${tradeLogSnapshot.amount_usd.toFixed(2)}`} />
            </div>

            <button
              onClick={() => setPage('chat')}
              className="mt-4 px-4 py-2 rounded-xl text-sm font-semibold"
              style={{ background: 'var(--accent)', color: '#1d2207' }}
            >
              Open Command Chat
            </button>
          </section>
        </div>
      </div>
    </div>
  );
}

function InfoCard({ label, value, accent }) {
  return (
    <div className="soft-card p-2.5">
      <div className="text-xs text-[var(--muted)]">{label}</div>
      <div className="mt-1" style={accent ? { color: accent, fontWeight: 700 } : undefined}>{value}</div>
    </div>
  );
}
