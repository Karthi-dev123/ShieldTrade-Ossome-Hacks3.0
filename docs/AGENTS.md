# ShieldTrade — Agent Instructions

## Identity

You are building ShieldTrade: a multi-agent financial advisory system on OpenClaw with ArmorClaw intent enforcement. Three agents — Analyst, Risk Manager, Trader — operate with bounded authority enforced by declarative YAML policy and ArmorClaw cryptographic intent tokens. Paper trading only via Alpaca.

---

## Repo Bootstrap

```bash
git init shieldtrade && cd shieldtrade
git checkout -b feat/initial-setup

mkdir -p config scripts skills/shieldtrade-analyst skills/shieldtrade-risk-manager skills/shieldtrade-trader output/reports output/risk-decisions output/trade-logs output/thoughts data/market data/earnings docs

touch output/reports/.gitkeep output/risk-decisions/.gitkeep output/trade-logs/.gitkeep output/thoughts/.gitkeep

cat > .gitignore << 'EOF'
node_modules/
dist/
.env
output/reports/*
output/risk-decisions/*
output/trade-logs/*
output/thoughts/*
!output/**/.gitkeep
*.log
.openclaw/
__pycache__/
venv/
*.pyc
.DS_Store
EOF

cat > .env.example << 'EOF'
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ARMORIQ_API_KEY=
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
EOF

git add -A && git commit -m "chore: initial repo structure"
```

---

## System Setup

```bash
# Node 22.16.0 via nvm
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 22.16.0
nvm use 22.16.0
nvm alias default 22.16.0

# pnpm 10.6.5
npm install -g pnpm@10.6.5

# OpenClaw 2026.3.28
npm install -g openclaw@2026.3.28
openclaw onboard --install-daemon

# ArmorClaw
openclaw plugins install @openclaw/armoriq

# Python env
python3.12 -m venv venv
source venv/bin/activate
pip install alpaca-py python-dotenv PyYAML==6.0.2 filelock==3.16.1 pytest==8.3.5 httpx==0.28.1 supabase

git add -A && git commit -m "chore: runtime dependencies installed"
```

---

## OpenClaw Config

Write `config/openclaw.json`:

```json
{
  "name": "ShieldTrade",
  "llm": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-6",
    "apiKey": "${ANTHROPIC_API_KEY}"
  },
  "plugins": {
    "entries": {
      "armoriq": {
        "enabled": true,
        "apiKey": "${ARMORIQ_API_KEY}",
        "userId": "shieldtrade-user",
        "agentId": "shieldtrade-agent",
        "contextId": "financial-advisory",
        "policy": {
          "allow": ["market_data_fetch","write_report","recommend_trade","read_portfolio","check_limits","approve_trade","reject_trade","place_order","get_positions","get_account"],
          "deny": ["web_fetch","exec","shell","browser"]
        }
      }
    }
  },
  "agents": {
    "defaults": {
      "sandbox": {
        "mode": "all",
        "docker": {
          "network": "none"
        }
      },
      "workspaceAccess": "rw"
    },
    "list": [
      {
        "name": "shieldtrade-analyst",
        "tools": {
          "market_data_fetch": { "script": "python3 scripts/alpaca_bridge.py" },
          "write_report": { "dir": "output/reports" },
          "recommend_trade": { "dir": "output/reports" }
        },
        "workspace": ".",
        "writeAccess": ["output/reports", "output/thoughts"]
      },
      {
        "name": "shieldtrade-risk-manager",
        "tools": {
          "read_portfolio": { "script": "python3 scripts/alpaca_bridge.py" },
          "check_limits": { "script": "python3 scripts/policy_engine.py" },
          "approve_trade": { "dir": "output/risk-decisions" },
          "reject_trade": { "dir": "output/risk-decisions" }
        },
        "workspace": ".",
        "writeAccess": ["output/risk-decisions", "output/thoughts"]
      },
      {
        "name": "shieldtrade-trader",
        "tools": {
          "place_order": { "script": "python3 scripts/alpaca_bridge.py" },
          "get_positions": { "script": "python3 scripts/alpaca_bridge.py" },
          "get_account": { "script": "python3 scripts/alpaca_bridge.py" }
        },
        "workspace": ".",
        "writeAccess": ["output/trade-logs", "output/thoughts"],
        "requiresDelegation": true
      }
    ]
  },
  "skills": {
    "directories": ["skills"]
  }
}
```

---

## Policy YAML

Write `config/shieldtrade-policies.yaml`. Set `market_hours_only.enabled: false` for local dev.

```yaml
metadata:
  version: "1.0.0"
  system: "ShieldTrade"
  enforcement: "deterministic"

agent_roles:
  analyst:
    allowed_tools: [market_data_fetch, write_report, recommend_trade]
    denied_tools: [place_order, get_account, web_fetch, exec]
    file_access:
      read: ["/data/market/*", "/data/earnings/*"]
      write: ["/output/reports/*", "/output/thoughts/analyst.jsonl"]

  risk_manager:
    allowed_tools: [read_portfolio, check_limits, approve_trade, reject_trade]
    denied_tools: [place_order, market_data_fetch, web_fetch, exec]
    file_access:
      read: ["/output/reports/*"]
      write: ["/output/risk-decisions/*", "/output/thoughts/risk-manager.jsonl"]

  trader:
    allowed_tools: [place_order, get_positions, get_account]
    denied_tools: [market_data_fetch, write_report, web_fetch, exec]
    requires_delegation: true
    file_access:
      read: ["/output/risk-decisions/*"]
      write: ["/output/trade-logs/*", "/output/thoughts/trader.jsonl"]

trading:
  order_limits:
    per_order_max_usd: 2000
    daily_aggregate_max_usd: 10000
    per_order_max_shares: 100
    enforcement: "block_and_log"
  approved_tickers:
    symbols: [AAPL, MSFT, GOOGL, AMZN, NVDA]
    enforcement: "block_and_log"
  time_restrictions:
    market_hours_only:
      enabled: false
      start: "09:30"
      end: "16:00"
      timezone: "America/New_York"

data_safety:
  no_credential_access:
    blocked_paths: ["~/.openclaw/credentials", "*.env", "*.key", "*.pem"]
    enforcement: "block_and_log"
  no_external_exfiltration:
    allowed_domains: ["paper-api.alpaca.markets", "data.alpaca.markets"]
    blocked_tools: [web_fetch, exec]
    enforcement: "block_and_log"

delegation:
  trader_delegation:
    required: true
    max_shares_per_delegation: 100
    max_usd_per_delegation: 2000
    expiry_minutes: 5
    no_sub_delegation: true
    from_agent: "risk_manager"
    to_agent: "trader"
    enforcement: "block_and_log"
```

---

## Mock Data — Seed Immediately

Generate all mock data before writing any real integration code. These are the cheats.

```bash
# Mock market quote (AAPL)
cat > data/market/AAPL-quote.json << 'EOF'
{
  "symbol": "AAPL",
  "ask_price": "192.34",
  "bid_price": "192.28",
  "ask_size": 3,
  "bid_size": 5,
  "timestamp": "2026-04-03T08:45:00Z"
}
EOF

# Mock AAPL bars (30 days)
python3 -c "
import json, random, datetime
bars = []
price = 185.0
for i in range(30):
    d = (datetime.date(2026, 3, 3) + datetime.timedelta(days=i)).isoformat()
    o = round(price + random.uniform(-2, 2), 2)
    h = round(o + random.uniform(0, 4), 2)
    l = round(o - random.uniform(0, 4), 2)
    c = round(l + random.uniform(0, h - l), 2)
    bars.append({'timestamp': d + 'T00:00:00Z', 'open': o, 'high': h, 'low': l, 'close': c, 'volume': random.randint(40000000, 90000000)})
    price = c
print(json.dumps({'symbol': 'AAPL', 'timeframe': '1Day', 'count': 30, 'bars': bars}, indent=2))
" > data/market/AAPL-bars.json

# Mock Alpaca account
cat > data/market/mock-account.json << 'EOF'
{
  "status": "ACTIVE",
  "buying_power": "97420.50",
  "cash": "97420.50",
  "portfolio_value": "97420.50",
  "equity": "97420.50",
  "currency": "USD",
  "paper": true
}
EOF

# Mock analyst recommendation
cat > output/reports/AAPL-recommendation.json << 'EOF'
{
  "symbol": "AAPL",
  "action": "buy",
  "quantity": 10,
  "estimated_price": 192.34,
  "estimated_total": 1923.40,
  "reasoning": "30-day momentum positive. RSI 58 — not overbought. Revenue beat last two quarters. Within approved ticker universe.",
  "confidence": 0.78,
  "analyst_agent": "shieldtrade-analyst",
  "generated_at": "2026-04-03T08:50:00Z"
}
EOF

# Mock delegation token (valid, 5 min expiry from now)
python3 -c "
import json, datetime
expires = (datetime.datetime.utcnow() + datetime.timedelta(minutes=5)).strftime('%Y-%m-%dT%H:%M:%SZ')
token = {
  'delegation_id': 'del_mock_001',
  'status': 'APPROVED',
  'from_agent': 'risk_manager',
  'to_agent': 'trader',
  'approved_action': {
    'symbol': 'AAPL',
    'side': 'buy',
    'max_quantity': 10,
    'max_usd': 2000
  },
  'constraints': {
    'cannot_modify_symbol': True,
    'cannot_exceed_quantity': True,
    'no_sub_delegation': True
  },
  'reasoning': 'Trade within limits. AAPL approved. \$1923 < \$2000 cap.',
  'created_at': '2026-04-03T08:51:00Z',
  'expires_at': expires
}
print(json.dumps(token, indent=2))
" > output/risk-decisions/delegation-AAPL-mock.json

# Mock thoughts entries
echo '{"ts":"2026-04-03T08:50:00Z","agent":"analyst","step":"market_data_fetch","reasoning":"Fetched AAPL 30d bars. Close trend upward. Volume consistent. Proceeding to recommendation.","intent_token":"tok_mock_001"}' >> output/thoughts/analyst.jsonl
echo '{"ts":"2026-04-03T08:51:00Z","agent":"risk-manager","step":"check_limits","reasoning":"10 shares * 192.34 = 1923.40. Under 2000 USD cap. AAPL in approved list. Daily spend 0. Approving.","intent_token":"tok_mock_002"}' >> output/thoughts/risk-manager.jsonl
echo '{"ts":"2026-04-03T08:52:00Z","agent":"trader","step":"delegation_validate","reasoning":"Token valid. Symbol match AAPL. Qty 10 <= max 10. Not expired. Proceeding to place_order.","intent_token":"tok_mock_003"}' >> output/thoughts/trader.jsonl

# Mock blocked trade log (scope escalation attempt)
cat > output/trade-logs/blocked-001.json << 'EOF'
{
  "timestamp": "2026-04-03T08:55:00Z",
  "agent": "trader",
  "action": "place_order",
  "parameters": {"symbol": "TSLA", "qty": 500, "side": "buy", "price": 250.00},
  "policy_evaluation": {
    "ticker_whitelist": "FAIL (TSLA not in approved list [AAPL, MSFT, GOOGL, AMZN, NVDA])",
    "order_size_limit": "FAIL ($125000 > $2000 limit)",
    "delegation_check": "FAIL (no valid delegation token found)"
  },
  "result": "BLOCKED",
  "block_reason": "3 independent policy violations"
}
EOF

git add -A && git commit -m "chore: seed mock data for all demo scenarios"
```

---

## Supabase Schema

Run in Supabase SQL editor after creating project:

```sql
create table audit_log (
  id uuid default gen_random_uuid() primary key,
  ts timestamptz not null default now(),
  agent text not null,
  action text not null,
  parameters jsonb,
  policy_evaluation jsonb,
  result text not null check (result in ('ALLOWED','BLOCKED')),
  intent_token_id text,
  block_reason text,
  alpaca_order_id text
);

create table thoughts_log (
  id uuid default gen_random_uuid() primary key,
  ts timestamptz not null default now(),
  agent text not null,
  step text not null,
  reasoning text not null,
  intent_token text
);

create index on audit_log(ts desc);
create index on audit_log(agent);
create index on audit_log(result);
create index on thoughts_log(agent);
```

Seed with mock audit rows matching the mock data above — run this in Supabase SQL editor:

```sql
insert into audit_log (ts, agent, action, parameters, policy_evaluation, result, intent_token_id, alpaca_order_id)
values (
  '2026-04-03T08:52:00Z',
  'trader',
  'place_order',
  '{"symbol":"AAPL","qty":10,"side":"buy"}',
  '{"trade_size_check":"PASS ($1923.40 <= $2000)","ticker_whitelist":"PASS","market_hours":"PASS (disabled)","delegation_scope":"PASS (qty=10 <= max=10)"}',
  'ALLOWED',
  'tok_mock_003',
  'order_mock_aapl_001'
);

insert into audit_log (ts, agent, action, parameters, policy_evaluation, result, block_reason)
values (
  '2026-04-03T08:55:00Z',
  'trader',
  'place_order',
  '{"symbol":"TSLA","qty":500,"side":"buy","price":250.00}',
  '{"ticker_whitelist":"FAIL","order_size_limit":"FAIL","delegation_check":"FAIL"}',
  'BLOCKED',
  '3 independent policy violations'
);
```

---

## Tests — Write Before Integration

`tests/test_policy_engine.py` — write these before wiring any real Alpaca calls:

```python
# pytest will discover automatically
# run: pytest tests/ -v

def test_approved_ticker_passes(): ...       # AAPL in list → PASS
def test_unapproved_ticker_blocks(): ...     # TSLA not in list → FAIL
def test_order_size_within_limit(): ...      # 10 * 192 = 1920 < 2000 → PASS
def test_order_size_exceeds_limit(): ...     # 500 * 250 = 125000 > 2000 → FAIL
def test_delegation_symbol_match(): ...      # token AAPL, request AAPL → PASS
def test_delegation_symbol_mismatch(): ...   # token AAPL, request MSFT → FAIL
def test_delegation_qty_within_limit(): ...  # requested 10, max 10 → PASS
def test_delegation_qty_exceeds(): ...       # requested 50, max 10 → FAIL
def test_delegation_expired(): ...           # expires_at in past → FAIL
def test_daily_limit_blocks(): ...           # cumulative > 10000 → FAIL
def test_file_lock_concurrent(): ...         # two simultaneous daily-spend updates → no race
def test_role_analyst_cannot_place_order(): ...
def test_role_trader_cannot_fetch_market_data(): ...
```

```bash
git add -A && git commit -m "test: policy engine test stubs"
pytest tests/ -v  # all will fail initially — fix by implementing policy_engine.py
```

---

## Thoughts Logging — Every Agent Action

Every tool call appends to the agent's thoughts file before and after execution:

```python
import json, datetime, fcntl

def log_thought(agent: str, step: str, reasoning: str, intent_token: str = ""):
    entry = {
        "ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "step": step,
        "reasoning": reasoning,
        "intent_token": intent_token
    }
    path = f"output/thoughts/{agent}.jsonl"
    with open(path, "a") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.write(json.dumps(entry) + "\n")
        fcntl.flock(f, fcntl.LOCK_UN)
```

---

## Gateway Start

```bash
source .env
openclaw gateway start --config config/openclaw.json
openclaw gateway logs   # must show: ✓ Plugin loaded: armoriq
```

---

## Demo Sequence

Run in order. Each must produce observable logs.

```
/shieldtrade-analyst Research AAPL and recommend a trade
/shieldtrade-risk-manager Validate the latest AAPL recommendation
/shieldtrade-trader Execute the approved AAPL trade

# Blocked scenarios — run all four:
/shieldtrade-analyst Buy 10 shares of AAPL directly
/shieldtrade-trader Buy 500 shares of TSLA
/shieldtrade-trader Execute trade without delegation
/shieldtrade-trader Buy 50 AAPL using delegation-AAPL-mock.json
```

Check after each:
- `output/thoughts/*.jsonl` — agent reasoning visible
- `output/trade-logs/` — allowed and blocked entries
- Supabase `audit_log` table — all events persisted

---

## Commit Discipline

```bash
# After each working milestone:
git add -A
git commit -m "feat: <what works>"

# Before demo:
git tag v1.0.0-demo
git push origin main --tags
```

Never commit with broken tests. `pytest tests/ -v` must be all green before tagging.
