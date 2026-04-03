# ShieldTrade — Team Implementation Guide
### Phase-Wise Build Plan for All 4 Members

---

## Team Roles

| Code | Role | Person | Owns |
|------|------|--------|------|
| **M1** | Infrastructure Lead | — | OpenClaw + ArmorClaw setup, Git repo, gateway config, environment |
| **M2** | Alpaca Integration Lead | — | Trading bridge script, market data tools, Alpaca account |
| **M3** | Policy & Enforcement Lead | — | Policy YAML, enforcement logic, delegation mechanism, validation scripts |
| **M4** | Agent Skills & Demo Lead | — | All SKILL.md files, agent orchestration, logging format, demo video, docs |

---

## Dependency Map (Who Blocks Whom)

```
M1 (OpenClaw setup) ──────► Everyone needs this first
      │
      ├── M2 (Alpaca bridge) ──► M4 needs this to test skills
      │
      ├── M3 (Policy engine) ──► M4 needs this for enforcement testing
      │
      └── M4 (Skills + Demo) ──► Needs M1 + M2 + M3 done
```

**Critical path**: M1 must finish Phase 1 before anyone can integrate.
M2 and M3 can work in parallel after M1 finishes.
M4 writes skill files immediately but can only test after M1 + M2 are done.

---

## Phase 0: Setup (ALL MEMBERS — Before Hackathon Day)

**Every single team member** must complete ALL of these steps before the hackathon starts. No exceptions. If someone shows up without this done, you lose an hour.

### 0.1 Install Prerequisites (Everyone)

```bash
# Check Node.js (need 18+)
node --version

# If not installed:
# macOS: brew install node
# Ubuntu: curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt-get install -y nodejs
# Windows: download from https://nodejs.org

# Check pnpm (OpenClaw uses pnpm)
pnpm --version

# If not installed:
npm install -g pnpm

# Check Python (need 3.10+)
python3 --version

# If not installed:
# macOS: brew install python
# Ubuntu: sudo apt install python3 python3-pip

# Check Git
git --version
```

### 0.2 Create GitHub Repo (M1 Does This, Everyone Clones)

**M1 creates the repo**:
1. Go to github.com → New Repository
2. Name: `shieldtrade` (or your team's preferred name)
3. Make it Private
4. Add README, .gitignore (Node), MIT License
5. Add all team members as collaborators (Settings → Collaborators)

**Everyone clones**:
```bash
git clone https://github.com/YOUR-TEAM/shieldtrade.git
cd shieldtrade
```

### 0.3 Set Up Branch Strategy (Everyone)

```bash
# Everyone works on their own branch
# M1:
git checkout -b infra/openclaw-setup

# M2:
git checkout -b feature/alpaca-bridge

# M3:
git checkout -b feature/policy-engine

# M4:
git checkout -b feature/agent-skills
```

Merge into `main` only when your phase checkpoint passes. Use Pull Requests so everyone can see what's being merged.

### 0.4 Create Initial Folder Structure (M1 Does This, Pushes to Main)

M1 creates these folders and pushes to `main`. Everyone pulls.

```bash
mkdir -p scripts skills/shieldtrade-analyst skills/shieldtrade-risk-manager skills/shieldtrade-trader config docs output/reports output/risk-decisions output/trade-logs

# Create .gitignore
cat > .gitignore << 'EOF'
node_modules/
dist/
.env
output/reports/*
output/risk-decisions/*
output/trade-logs/*
!output/reports/.gitkeep
!output/risk-decisions/.gitkeep
!output/trade-logs/.gitkeep
*.log
.openclaw/
__pycache__/
EOF

# Create placeholder files so git tracks empty dirs
touch output/reports/.gitkeep
touch output/risk-decisions/.gitkeep
touch output/trade-logs/.gitkeep

# Create .env.example (never commit real keys)
cat > .env.example << 'EOF'
ALPACA_API_KEY=your_paper_trading_key_here
ALPACA_SECRET_KEY=your_paper_trading_secret_here
ARMORIQ_API_KEY=ak_live_your_key_here
ANTHROPIC_API_KEY=your_claude_api_key_here
EOF

git add -A
git commit -m "initial project structure"
git push origin main
```

### 0.5 Create Alpaca Account (M2 Does This, Shares Keys Securely)

1. Go to https://app.alpaca.markets/signup
2. Sign up with team email
3. Select Paper Trading
4. Generate API Key + Secret Key
5. Share keys with team via secure channel (NOT in git, NOT in group chat)
6. Everyone saves keys in their local `.env` file

### 0.6 Get ArmorIQ API Key (M1 Does This)

1. Check if hackathon organizers are distributing keys
2. If not, go to https://armoriq.io → sign up → get API key
3. Share with team securely

### 0.7 Verification Checkpoint (Everyone)

Before hackathon day, every member must confirm:
- [ ] Node.js 18+ installed
- [ ] pnpm installed
- [ ] Python 3.10+ installed
- [ ] Git configured with GitHub access
- [ ] Repo cloned and can push to their branch
- [ ] `.env` file created locally with Alpaca keys
- [ ] ArmorIQ API key received

---

## Phase 1: Independent Component Building

**Duration**: ~2.5 hours
**Mode**: Everyone works on their branch independently.
**Sync point**: End of Phase 1 — everyone merges to main and verifies.

---

### MEMBER 1 (M1): OpenClaw + ArmorClaw Setup

**Your goal**: Get OpenClaw gateway running with ArmorClaw plugin installed and configured. When you're done, every team member should be able to connect to the gateway and run a basic command.

#### Step 1.1: Install OpenClaw with ArmorIQ Integration (~40 min)

```bash
cd shieldtrade
git checkout infra/openclaw-setup

# Option A: Clone ArmorIQ's pre-integrated fork (RECOMMENDED)
git clone https://github.com/armoriq/aiq-openclaw.git openclaw-runtime
cd openclaw-runtime

# Install dependencies
pnpm install

# Build the project
pnpm build
```

**If pnpm install fails** (common issues):
```bash
# Clear cache and retry
pnpm store prune
rm -rf node_modules
pnpm install

# If permission issues on Linux:
sudo chown -R $USER:$USER .
pnpm install
```

**Verify the build worked**:
```bash
# You should see compiled JS in dist/
ls dist/
# Should show: gateway/, plugins/, logging/ etc.
```

#### Step 1.2: Configure the Gateway (~20 min)

Create the configuration file. This is the central config that ALL team members depend on.

```bash
cd ../  # back to shieldtrade root
```

Create `config/openclaw.json`:
```json
{
  "name": "ShieldTrade",
  "llm": {
    "provider": "anthropic",
    "model": "claude-sonnet-4-20250514",
    "apiKey": "${ANTHROPIC_API_KEY}"
  },
  "plugins": {
    "entries": {
      "armoriq": {
        "enabled": true,
        "apiKey": "${ARMORIQ_API_KEY}",
        "userId": "shieldtrade-user",
        "agentId": "shieldtrade-agent",
        "contextId": "financial-advisory"
      }
    }
  },
  "skills": {
    "directories": ["../skills"]
  }
}
```

**Important**: The `${...}` values are loaded from environment variables. Never hardcode API keys.

#### Step 1.3: Create the Gateway Start Script (~10 min)

Create `scripts/start-gateway.sh`:
```bash
#!/bin/bash
# ShieldTrade Gateway Launcher
# Loads environment variables and starts OpenClaw gateway

set -e

# Load environment variables
if [ -f ../.env ]; then
    export $(cat ../.env | grep -v '^#' | xargs)
fi

# Check required vars
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set in .env"
    exit 1
fi

if [ -z "$ALPACA_API_KEY" ]; then
    echo "ERROR: ALPACA_API_KEY not set in .env"
    exit 1
fi

echo "Starting ShieldTrade Gateway..."
echo "ArmorIQ: ${ARMORIQ_API_KEY:+configured}"
echo "Alpaca:  ${ALPACA_API_KEY:+configured}"

cd ../openclaw-runtime

# Start the gateway
node dist/gateway/index.js --config ../config/openclaw.json
```

```bash
chmod +x scripts/start-gateway.sh
```

#### Step 1.4: Verify ArmorClaw Plugin Loads (~15 min)

Start the gateway and check logs:
```bash
cd scripts
./start-gateway.sh
```

**What to look for in logs**:
```
✓ Gateway started on ws://127.0.0.1:18789
✓ Plugin loaded: armoriq
✓ ArmorIQ connected to IAP
```

**If ArmorClaw doesn't load**:
```bash
# Check if the plugin directory exists
ls openclaw-runtime/extensions/armoriq/

# Check the plugin config
cat openclaw-runtime/openclaw.plugin.json

# Try manual plugin install
cd openclaw-runtime
openclaw plugins install @openclaw/armoriq
```

#### Step 1.5: Test Basic Interaction (~15 min)

Open a new terminal and connect via WebChat or CLI:
```bash
# If webchat is available:
# Open http://localhost:18789 in browser

# Or via CLI:
cd openclaw-runtime
openclaw chat
```

Send a test message:
```
You: Hello, are you running?
Agent: [should respond via your configured LLM]
```

#### M1 Phase 1 Checkpoint

**You PASS Phase 1 when**:
- [ ] OpenClaw gateway starts without errors
- [ ] ArmorClaw plugin loads (visible in logs)
- [ ] You can send a message and get a response
- [ ] Gateway is accessible to other team members on the same network (or localhost)

```bash
# Commit and push
git add -A
git commit -m "feat(infra): OpenClaw gateway with ArmorClaw plugin"
git push origin infra/openclaw-setup
```

**Notify the team**: "Gateway is running. You can now test against it."

---

### MEMBER 2 (M2): Alpaca Trading Bridge

**Your goal**: Build a Python script that OpenClaw agents can call to interact with Alpaca paper trading. When you're done, every command (quote, bars, account, positions, order) should work and return clean JSON.

#### Step 2.1: Set Up Python Environment (~10 min)

```bash
cd shieldtrade
git checkout feature/alpaca-bridge

# Create virtual environment
python3 -m venv venv
echo "venv/" >> .gitignore

# Activate it
source venv/bin/activate   # macOS/Linux
# or: venv\Scripts\activate  # Windows

# Install Alpaca SDK
pip install alpaca-py python-dotenv

# Save dependencies
pip freeze > requirements.txt
```

#### Step 2.2: Build the Alpaca Bridge Script (~45 min)

Create `scripts/alpaca_bridge.py`:

```python
#!/usr/bin/env python3
"""
ShieldTrade — Alpaca Paper Trading Bridge
==========================================
This script is the ONLY interface between OpenClaw agents and Alpaca.
Agents call this script via shell commands. All responses are JSON.

Usage:
  python3 alpaca_bridge.py account
  python3 alpaca_bridge.py positions
  python3 alpaca_bridge.py quote AAPL
  python3 alpaca_bridge.py bars AAPL 1Day 30
  python3 alpaca_bridge.py order AAPL 10 buy
  python3 alpaca_bridge.py order AAPL 5 sell
"""

import sys
import json
import os
from datetime import datetime

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# ── Initialize clients ──────────────────────────────────────────

API_KEY = os.environ.get("ALPACA_API_KEY")
SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")

if not API_KEY or not SECRET_KEY:
    print(json.dumps({
        "error": "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in environment"
    }))
    sys.exit(1)

trade_client = TradingClient(API_KEY, SECRET_KEY, paper=True)
data_client = StockHistoricalDataClient(API_KEY, SECRET_KEY)


# ── Command implementations ─────────────────────────────────────

def cmd_account():
    """Return account summary."""
    acct = trade_client.get_account()
    return {
        "status": str(acct.status),
        "buying_power": str(acct.buying_power),
        "cash": str(acct.cash),
        "portfolio_value": str(acct.portfolio_value),
        "equity": str(acct.equity),
        "currency": "USD",
        "paper": True
    }


def cmd_positions():
    """Return all open positions."""
    positions = trade_client.get_all_positions()
    if not positions:
        return {"positions": [], "count": 0}
    return {
        "positions": [{
            "symbol": p.symbol,
            "qty": str(p.qty),
            "side": str(p.side),
            "market_value": str(p.market_value),
            "avg_entry_price": str(p.avg_entry_price),
            "current_price": str(p.current_price),
            "unrealized_pl": str(p.unrealized_pl),
            "unrealized_plpc": str(p.unrealized_plpc),
        } for p in positions],
        "count": len(positions)
    }


def cmd_quote(symbol):
    """Get latest quote for a symbol."""
    symbol = symbol.upper().strip()
    request = StockLatestQuoteRequest(symbol_or_symbols=symbol)
    quotes = data_client.get_stock_latest_quote(request)
    q = quotes[symbol]
    return {
        "symbol": symbol,
        "ask_price": str(q.ask_price),
        "bid_price": str(q.bid_price),
        "ask_size": q.ask_size,
        "bid_size": q.bid_size,
        "timestamp": str(q.timestamp)
    }


def cmd_bars(symbol, timeframe="1Day", limit=30):
    """Get historical OHLCV bars."""
    symbol = symbol.upper().strip()
    tf_map = {
        "1Min": TimeFrame.Minute,
        "5Min": TimeFrame(5, "Min"),
        "1Hour": TimeFrame.Hour,
        "1Day": TimeFrame.Day,
    }
    tf = tf_map.get(timeframe, TimeFrame.Day)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        limit=int(limit)
    )
    bars_data = data_client.get_stock_bars(request)
    bars_list = bars_data.get(symbol, [])
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(bars_list),
        "bars": [{
            "timestamp": str(b.timestamp),
            "open": float(b.open),
            "high": float(b.high),
            "low": float(b.low),
            "close": float(b.close),
            "volume": int(b.volume)
        } for b in bars_list]
    }


def cmd_order(symbol, qty, side):
    """Place a market order. Returns order confirmation."""
    symbol = symbol.upper().strip()
    side = side.lower().strip()

    if side not in ("buy", "sell"):
        return {"error": f"Invalid side '{side}'. Must be 'buy' or 'sell'."}

    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=float(qty),
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY
    )
    order = trade_client.submit_order(order_data=order_data)
    return {
        "order_id": str(order.id),
        "client_order_id": str(order.client_order_id),
        "symbol": order.symbol,
        "qty": str(order.qty),
        "side": str(order.side),
        "type": str(order.type),
        "status": str(order.status),
        "submitted_at": str(order.submitted_at),
        "paper": True
    }


# ── CLI dispatcher ──────────────────────────────────────────────

COMMANDS = {
    "account": (cmd_account, 0),
    "positions": (cmd_positions, 0),
    "quote": (cmd_quote, 1),      # requires: symbol
    "bars": (cmd_bars, 1),         # requires: symbol; optional: timeframe, limit
    "order": (cmd_order, 3),       # requires: symbol, qty, side
}


def print_usage():
    print(json.dumps({
        "error": "Invalid usage",
        "commands": {
            "account": "Get account info",
            "positions": "Get open positions",
            "quote <SYMBOL>": "Get latest quote",
            "bars <SYMBOL> [TIMEFRAME] [LIMIT]": "Get historical bars",
            "order <SYMBOL> <QTY> <SIDE>": "Place market order (buy/sell)"
        }
    }, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1].lower()

    if command not in COMMANDS:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        print_usage()
        sys.exit(1)

    func, min_args = COMMANDS[command]
    args = sys.argv[2:]

    if len(args) < min_args:
        print(json.dumps({
            "error": f"'{command}' requires at least {min_args} argument(s), got {len(args)}"
        }))
        sys.exit(1)

    try:
        result = func(*args)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({
            "error": str(e),
            "command": command,
            "args": args,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }))
        sys.exit(1)
```

```bash
chmod +x scripts/alpaca_bridge.py
```

#### Step 2.3: Test Every Command (~20 min)

Run these one by one. **Every single one must work before you move on.**

```bash
source venv/bin/activate

# Test 1: Account info
python3 scripts/alpaca_bridge.py account
# Expected: JSON with status, buying_power, cash, equity
# ✓ PASS if you see buying_power ~100000

# Test 2: Get a quote
python3 scripts/alpaca_bridge.py quote AAPL
# Expected: JSON with ask_price, bid_price
# ✓ PASS if prices look reasonable (not zero, not null)

# Test 3: Get historical bars
python3 scripts/alpaca_bridge.py bars AAPL 1Day 5
# Expected: JSON with 5 bars, each having open/high/low/close/volume
# ✓ PASS if you see 5 bars with real prices

# Test 4: Get positions (should be empty initially)
python3 scripts/alpaca_bridge.py positions
# Expected: {"positions": [], "count": 0}
# ✓ PASS if count is 0

# Test 5: Place a test order (THIS IS THE BIG ONE)
python3 scripts/alpaca_bridge.py order AAPL 1 buy
# Expected: JSON with order_id, status = "accepted" or "new"
# ✓ PASS if order_id is returned

# Test 6: Verify the position exists now
python3 scripts/alpaca_bridge.py positions
# Expected: 1 position for AAPL
# ✓ PASS if AAPL appears with qty=1

# Test 7: Sell it back
python3 scripts/alpaca_bridge.py order AAPL 1 sell
# ✓ PASS if order succeeds

# Test 8: Error handling — invalid symbol
python3 scripts/alpaca_bridge.py quote INVALIDXYZ
# Expected: JSON with error message
# ✓ PASS if it returns an error, doesn't crash

# Test 9: Error handling — missing args
python3 scripts/alpaca_bridge.py order AAPL
# Expected: Error about missing arguments
# ✓ PASS if it explains what's missing
```

**All 9 tests must pass.** If any fail, fix before moving on.

#### M2 Phase 1 Checkpoint

**You PASS Phase 1 when**:
- [ ] All 9 test commands produce correct JSON output
- [ ] Buy order actually appears in Alpaca dashboard (check https://app.alpaca.markets)
- [ ] Error cases return JSON errors (not Python tracebacks)
- [ ] Script works when called from any directory (paths are correct)

```bash
git add scripts/alpaca_bridge.py requirements.txt
git commit -m "feat(alpaca): complete trading bridge with all commands tested"
git push origin feature/alpaca-bridge
```

**Notify the team**: "Alpaca bridge is ready. All commands tested. You can call `python3 scripts/alpaca_bridge.py <command>`."

---

### MEMBER 3 (M3): Policy & Enforcement Engine

**Your goal**: Build the declarative policy model (YAML) and the validation scripts that enforce financial constraints. When you're done, there's a script that takes a trade request and returns PASS/FAIL for every policy check.

#### Step 3.1: Create the Policy YAML File (~30 min)

This is the heart of the submission. Judges specifically look for structured, declarative policies — not hardcoded if-else.

Create `config/shieldtrade-policies.yaml`:

```yaml
# ═══════════════════════════════════════════════════════════
# ShieldTrade Policy Model — Declarative Financial Constraints
# ═══════════════════════════════════════════════════════════
#
# This file defines ALL enforcement rules for the ShieldTrade
# multi-agent system. Policies are evaluated at runtime by the
# enforcement engine. They are NOT prompt-level instructions.
#
# Structure:
#   agent_roles   → per-agent tool permissions
#   trading       → financial constraint rules
#   data_safety   → data protection rules
#   delegation    → bounded delegation rules
# ═══════════════════════════════════════════════════════════

metadata:
  version: "1.0.0"
  system: "ShieldTrade"
  description: "Intent-enforced multi-agent financial advisory policies"
  created_by: "Team Avengers"
  enforcement: "deterministic"    # not probabilistic, not LLM-based

# ─── Agent Role Definitions ────────────────────────────────

agent_roles:
  analyst:
    description: "Researches equities and generates recommendations"
    allowed_tools:
      - market_data_fetch
      - write_report
      - recommend_trade
    denied_tools:
      - place_order
      - get_account
      - shell
      - web_fetch
    file_access:
      read:
        - "/data/market/*"
        - "/data/earnings/*"
      write:
        - "/output/reports/*"

  risk_manager:
    description: "Validates recommendations against portfolio constraints"
    allowed_tools:
      - read_portfolio
      - check_limits
      - approve_trade
      - reject_trade
    denied_tools:
      - place_order
      - market_data_fetch
      - shell
    file_access:
      read:
        - "/output/reports/*"
        - "/data/portfolio/*"
      write:
        - "/output/risk-decisions/*"

  trader:
    description: "Executes approved trades within delegated scope only"
    allowed_tools:
      - place_order
      - get_positions
      - get_account
    denied_tools:
      - market_data_fetch
      - write_report
      - shell
      - web_fetch
    requires_delegation: true
    file_access:
      read:
        - "/output/risk-decisions/*"
      write:
        - "/output/trade-logs/*"

# ─── Trading Constraints ───────────────────────────────────

trading:
  order_limits:
    per_order_max_usd: 2000
    daily_aggregate_max_usd: 10000
    per_order_max_shares: 100
    enforcement: "block_and_log"

  approved_tickers:
    symbols:
      - AAPL
      - MSFT
      - GOOGL
      - AMZN
      - NVDA
    enforcement: "block_and_log"

  time_restrictions:
    market_hours_only:
      enabled: true
      start: "09:30"
      end: "16:00"
      timezone: "America/New_York"
      enforcement: "block_and_log"

    earnings_blackout:
      enabled: false   # enable when needed
      window_before_minutes: 30
      window_after_minutes: 30
      enforcement: "block_and_log"

  portfolio_limits:
    max_single_position_pct: 30    # no single stock > 30% of portfolio
    min_cash_reserve_pct: 10       # keep at least 10% in cash
    enforcement: "block_and_log"

# ─── Data Safety Rules ─────────────────────────────────────

data_safety:
  no_pii_in_tool_args:
    description: "Block tool calls containing PII patterns"
    patterns:
      - "\\d{3}-\\d{2}-\\d{4}"     # SSN
      - "\\d{16}"                   # credit card
      - "\\d{9}"                    # account number
    enforcement: "block_and_log"

  no_credential_access:
    description: "Block access to credential files"
    blocked_paths:
      - "~/.openclaw/credentials"
      - "*.env"
      - "*.key"
      - "*.pem"
      - "*.secret"
    enforcement: "block_and_log"

  no_external_exfiltration:
    description: "Block outbound data to unauthorized endpoints"
    allowed_domains:
      - "paper-api.alpaca.markets"
      - "data.alpaca.markets"
    blocked_tools:
      - web_fetch
      - curl
      - wget
    enforcement: "block_and_log"

# ─── Delegation Rules ──────────────────────────────────────

delegation:
  trader_delegation:
    required: true
    max_shares_per_delegation: 100
    max_usd_per_delegation: 2000
    expiry_minutes: 5
    must_match_recommendation: true
    no_sub_delegation: true
    from_agent: "risk_manager"
    to_agent: "trader"
    enforcement: "block_and_log"
```

#### Step 3.2: Build the Policy Enforcement Script (~60 min)

This is the programmatic enforcement engine. It reads the YAML policy and evaluates trade requests against it.

Create `scripts/policy_engine.py`:

```python
#!/usr/bin/env python3
"""
ShieldTrade — Policy Enforcement Engine
========================================
Evaluates trade requests against the declarative YAML policy model.
Returns structured PASS/FAIL results for every constraint.

Usage:
  python3 policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":152.0}'
  python3 policy_engine.py check-role analyst place_order
  python3 policy_engine.py check-delegation '{"delegation_json..."}' '{"request_json..."}'
  python3 policy_engine.py validate-all '{"trade_json"}' analyst
"""

import sys
import json
import yaml
import os
import re
from datetime import datetime, timezone, timedelta

# ── Load policy file ────────────────────────────────────────

POLICY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "config", "shieldtrade-policies.yaml"
)

with open(POLICY_PATH, "r") as f:
    POLICY = yaml.safe_load(f)

# Track daily spending (in-memory for hackathon, would be DB in production)
DAILY_SPEND_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "output", "trade-logs", "daily-spend.json"
)


def get_daily_spend():
    """Get today's total spend from the log file."""
    try:
        with open(DAILY_SPEND_FILE, "r") as f:
            data = json.load(f)
            if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                return data.get("total_usd", 0)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return 0


def update_daily_spend(amount):
    """Add to today's spend total."""
    current = get_daily_spend()
    data = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "total_usd": current + amount
    }
    os.makedirs(os.path.dirname(DAILY_SPEND_FILE), exist_ok=True)
    with open(DAILY_SPEND_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Check functions ─────────────────────────────────────────

def check_ticker(symbol):
    """Check if symbol is in approved ticker list."""
    approved = POLICY["trading"]["approved_tickers"]["symbols"]
    passed = symbol.upper() in approved
    return {
        "check": "ticker_approved",
        "passed": passed,
        "detail": f"{symbol} {'is' if passed else 'is NOT'} in approved list {approved}"
    }


def check_order_size(qty, price):
    """Check if order value is within per-order limit."""
    limit = POLICY["trading"]["order_limits"]["per_order_max_usd"]
    total = qty * price
    passed = total <= limit
    return {
        "check": "order_size_limit",
        "passed": passed,
        "detail": f"${total:.2f} {'<=' if passed else '>'} ${limit} limit"
    }


def check_share_count(qty):
    """Check if share count is within per-order limit."""
    limit = POLICY["trading"]["order_limits"]["per_order_max_shares"]
    passed = qty <= limit
    return {
        "check": "share_count_limit",
        "passed": passed,
        "detail": f"{qty} shares {'<=' if passed else '>'} {limit} limit"
    }


def check_daily_limit(additional_usd):
    """Check if daily aggregate would be exceeded."""
    limit = POLICY["trading"]["order_limits"]["daily_aggregate_max_usd"]
    current = get_daily_spend()
    new_total = current + additional_usd
    passed = new_total <= limit
    return {
        "check": "daily_aggregate_limit",
        "passed": passed,
        "detail": f"Daily total ${new_total:.2f} (${current:.2f} + ${additional_usd:.2f}) {'<=' if passed else '>'} ${limit} limit"
    }


def check_market_hours():
    """Check if current time is within market hours (ET)."""
    config = POLICY["trading"]["time_restrictions"]["market_hours_only"]
    if not config.get("enabled", True):
        return {"check": "market_hours", "passed": True, "detail": "Check disabled"}

    # Get current ET time
    from zoneinfo import ZoneInfo
    now_et = datetime.now(ZoneInfo("America/New_York"))
    current_time = now_et.strftime("%H:%M")

    start = config["start"]
    end = config["end"]
    passed = start <= current_time <= end

    return {
        "check": "market_hours",
        "passed": passed,
        "detail": f"Current time {current_time} ET {'within' if passed else 'outside'} {start}-{end}"
    }


def check_role_permission(agent_role, tool_name):
    """Check if an agent role is allowed to use a specific tool."""
    role_config = POLICY["agent_roles"].get(agent_role)
    if not role_config:
        return {
            "check": "role_permission",
            "passed": False,
            "detail": f"Unknown agent role: {agent_role}"
        }

    denied = role_config.get("denied_tools", [])
    allowed = role_config.get("allowed_tools", [])

    if tool_name in denied:
        return {
            "check": "role_permission",
            "passed": False,
            "detail": f"Tool '{tool_name}' is in {agent_role}'s denied_tools list"
        }

    if tool_name in allowed:
        return {
            "check": "role_permission",
            "passed": True,
            "detail": f"Tool '{tool_name}' is in {agent_role}'s allowed_tools list"
        }

    return {
        "check": "role_permission",
        "passed": False,
        "detail": f"Tool '{tool_name}' not found in {agent_role}'s allowed_tools"
    }


def check_delegation(delegation, request):
    """Validate a delegation token against a trade request."""
    checks = []

    # Status check
    status_ok = delegation.get("status") == "APPROVED"
    checks.append({
        "check": "delegation_status",
        "passed": status_ok,
        "detail": f"Status: {delegation.get('status')}"
    })

    # Expiry check
    try:
        expires = datetime.fromisoformat(
            delegation["expires_at"].replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)
        not_expired = now < expires
    except (KeyError, ValueError):
        not_expired = False
    checks.append({
        "check": "delegation_not_expired",
        "passed": not_expired,
        "detail": f"Expires: {delegation.get('expires_at', 'missing')}"
    })

    # Symbol match
    approved_action = delegation.get("approved_action", {})
    symbol_match = (
        request.get("symbol", "").upper() ==
        approved_action.get("symbol", "").upper()
    )
    checks.append({
        "check": "delegation_symbol_match",
        "passed": symbol_match,
        "detail": f"Requested {request.get('symbol')} vs delegated {approved_action.get('symbol')}"
    })

    # Quantity check
    req_qty = float(request.get("qty", 0))
    max_qty = float(approved_action.get("max_quantity", 0))
    qty_ok = req_qty <= max_qty
    checks.append({
        "check": "delegation_quantity_limit",
        "passed": qty_ok,
        "detail": f"Requested {req_qty} <= max {max_qty}: {'yes' if qty_ok else 'NO'}"
    })

    # Target agent check
    to_agent_ok = delegation.get("to_agent") == "trader"
    checks.append({
        "check": "delegation_target_agent",
        "passed": to_agent_ok,
        "detail": f"to_agent: {delegation.get('to_agent')}"
    })

    all_pass = all(c["passed"] for c in checks)
    return {
        "all_passed": all_pass,
        "checks": checks
    }


def check_data_safety(tool_args_string):
    """Check tool arguments for PII patterns."""
    patterns = POLICY["data_safety"]["no_pii_in_tool_args"]["patterns"]
    found = []
    for pattern in patterns:
        if re.search(pattern, tool_args_string):
            found.append(pattern)

    passed = len(found) == 0
    return {
        "check": "data_safety_pii",
        "passed": passed,
        "detail": f"PII patterns {'not found' if passed else 'FOUND: ' + str(found)}"
    }


# ── Composite validators ────────────────────────────────────

def validate_trade(trade, agent_role="trader"):
    """Run ALL policy checks against a proposed trade."""
    symbol = trade.get("symbol", "").upper()
    qty = float(trade.get("qty", 0))
    price = float(trade.get("price", 0))
    side = trade.get("side", "buy")
    total_usd = qty * price

    results = {
        "trade": {"symbol": symbol, "qty": qty, "price": price,
                  "side": side, "estimated_cost": total_usd},
        "agent": agent_role,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": []
    }

    # Run each check
    results["checks"].append(check_role_permission(agent_role, "place_order"))
    results["checks"].append(check_ticker(symbol))
    results["checks"].append(check_order_size(qty, price))
    results["checks"].append(check_share_count(qty))
    results["checks"].append(check_daily_limit(total_usd))
    results["checks"].append(check_market_hours())
    results["checks"].append(check_data_safety(json.dumps(trade)))

    results["all_passed"] = all(c["passed"] for c in results["checks"])
    results["decision"] = "ALLOW" if results["all_passed"] else "BLOCK"
    results["failed_checks"] = [
        c["check"] for c in results["checks"] if not c["passed"]
    ]

    return results


# ── CLI dispatcher ──────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: policy_engine.py <command> [args]",
            "commands": {
                "check-trade": "Validate a trade: '{\"symbol\":\"AAPL\",\"qty\":10,\"side\":\"buy\",\"price\":150}'",
                "check-role": "Check role permission: <role> <tool>",
                "check-delegation": "Validate delegation: '<delegation_json>' '<request_json>'",
                "validate-all": "Full validation: '<trade_json>' <agent_role>"
            }
        }, indent=2))
        sys.exit(1)

    cmd = sys.argv[1]

    try:
        if cmd == "check-trade":
            trade = json.loads(sys.argv[2])
            role = sys.argv[3] if len(sys.argv) > 3 else "trader"
            result = validate_trade(trade, role)

        elif cmd == "check-role":
            role = sys.argv[2]
            tool = sys.argv[3]
            result = check_role_permission(role, tool)

        elif cmd == "check-delegation":
            delegation = json.loads(sys.argv[2])
            request = json.loads(sys.argv[3])
            result = check_delegation(delegation, request)

        elif cmd == "validate-all":
            trade = json.loads(sys.argv[2])
            role = sys.argv[3] if len(sys.argv) > 3 else "trader"
            result = validate_trade(trade, role)

        else:
            result = {"error": f"Unknown command: {cmd}"}

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
```

```bash
chmod +x scripts/policy_engine.py
pip install pyyaml
```

#### Step 3.3: Test Every Policy Check (~30 min)

Run each test. **Every one must produce the correct result.**

```bash
# Test 1: Valid trade (should PASS all checks)
python3 scripts/policy_engine.py check-trade \
  '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
# ✓ PASS if all_passed = true, decision = ALLOW

# Test 2: Unapproved ticker (should FAIL)
python3 scripts/policy_engine.py check-trade \
  '{"symbol":"TSLA","qty":5,"side":"buy","price":250}' trader
# ✓ PASS if all_passed = false, ticker_approved = failed

# Test 3: Exceeds per-order limit (should FAIL)
python3 scripts/policy_engine.py check-trade \
  '{"symbol":"NVDA","qty":50,"side":"buy","price":130}' trader
# ✓ PASS if all_passed = false ($6500 > $2000)

# Test 4: Analyst trying to place order (should FAIL role check)
python3 scripts/policy_engine.py check-role analyst place_order
# ✓ PASS if passed = false

# Test 5: Trader trying to place order (should PASS role check)
python3 scripts/policy_engine.py check-role trader place_order
# ✓ PASS if passed = true

# Test 6: Risk manager trying to fetch market data (should FAIL)
python3 scripts/policy_engine.py check-role risk_manager market_data_fetch
# ✓ PASS if passed = false

# Test 7: Delegation — valid (should PASS)
python3 scripts/policy_engine.py check-delegation \
  '{"status":"APPROVED","to_agent":"trader","approved_action":{"symbol":"AAPL","max_quantity":10},"expires_at":"2099-12-31T23:59:59Z"}' \
  '{"symbol":"AAPL","qty":10}'
# ✓ PASS if all_passed = true

# Test 8: Delegation — exceeds quantity (should FAIL)
python3 scripts/policy_engine.py check-delegation \
  '{"status":"APPROVED","to_agent":"trader","approved_action":{"symbol":"AAPL","max_quantity":10},"expires_at":"2099-12-31T23:59:59Z"}' \
  '{"symbol":"AAPL","qty":50}'
# ✓ PASS if delegation_quantity_limit = failed

# Test 9: Delegation — wrong symbol (should FAIL)
python3 scripts/policy_engine.py check-delegation \
  '{"status":"APPROVED","to_agent":"trader","approved_action":{"symbol":"AAPL","max_quantity":10},"expires_at":"2099-12-31T23:59:59Z"}' \
  '{"symbol":"MSFT","qty":5}'
# ✓ PASS if delegation_symbol_match = failed

# Test 10: Delegation — expired (should FAIL)
python3 scripts/policy_engine.py check-delegation \
  '{"status":"APPROVED","to_agent":"trader","approved_action":{"symbol":"AAPL","max_quantity":10},"expires_at":"2020-01-01T00:00:00Z"}' \
  '{"symbol":"AAPL","qty":5}'
# ✓ PASS if delegation_not_expired = failed
```

**All 10 tests must pass.** Fix any failures before moving on.

#### M3 Phase 1 Checkpoint

**You PASS Phase 1 when**:
- [ ] Policy YAML file is complete and valid (parseable by Python yaml.safe_load)
- [ ] Policy engine correctly evaluates all 10 test cases
- [ ] Role permission checks work for all 3 agent roles
- [ ] Delegation validation catches expired, wrong-symbol, and over-quantity cases
- [ ] Trade size, ticker, and market hours checks all function

```bash
pip freeze > requirements.txt  # update if new packages added
git add config/shieldtrade-policies.yaml scripts/policy_engine.py requirements.txt
git commit -m "feat(policy): declarative YAML policy model + enforcement engine"
git push origin feature/policy-engine
```

**Notify the team**: "Policy engine ready. You can validate any trade with `python3 scripts/policy_engine.py check-trade '{...}'`."

---

### MEMBER 4 (M4): Agent Skills & Orchestration

**Your goal**: Write all three SKILL.md files that define agent behavior, plus the decision logging format. These are the files OpenClaw reads to know what each agent can do. You can write these immediately — they're Markdown files that don't need the gateway running.

#### Step 4.1: Create the Analyst Skill (~30 min)

Create `skills/shieldtrade-analyst/SKILL.md`:

```markdown
---
name: shieldtrade-analyst
description: >
  ShieldTrade financial research analyst. Researches equities using Alpaca
  market data, analyzes price trends, and generates trade recommendations.
  Use when the user asks to research a stock, get market analysis, or
  evaluate whether to buy/sell a specific ticker. This agent CANNOT place
  trades — it only produces recommendations for the Risk Manager to validate.
---

# ShieldTrade Analyst Agent

## Your Role
You are the **Analyst** in the ShieldTrade multi-agent advisory system.
Your job is to research equities and produce structured trade recommendations
that the Risk Manager will evaluate.

You are an expert at reading price data, identifying trends, and making
clear, reasoned recommendations.

## Tools Available

### Get current price
```bash
python3 scripts/alpaca_bridge.py quote AAPL
```
Returns: ask_price, bid_price, timestamp

### Get historical prices
```bash
python3 scripts/alpaca_bridge.py bars AAPL 1Day 30
```
Returns: array of OHLCV bars (open, high, low, close, volume)
Timeframes: 1Min, 1Hour, 1Day

## Approved Research Universe
You may ONLY research these symbols: **AAPL, MSFT, GOOGL, AMZN, NVDA**
If the user asks about any other symbol, explain it is outside your
approved universe and decline.

## Analysis Workflow

Follow these steps IN ORDER for every research request:

### Step 1 — Fetch data
Get the latest quote AND 30-day historical bars for the requested symbol.

### Step 2 — Analyze
Look at:
- Recent price trend (up, down, sideways)
- Current price relative to 30-day range
- Volume trends (increasing or decreasing)
- Simple moving averages (calculate from the bars)

### Step 3 — Generate recommendation
Produce a recommendation in this EXACT JSON format and save it:

```bash
cat > /output/reports/SYMBOL-recommendation.json << 'RECEOF'
{
  "agent": "analyst",
  "symbol": "AAPL",
  "action": "BUY",
  "quantity": 10,
  "estimated_cost": 1520.00,
  "current_price": 152.00,
  "reasoning": "AAPL is trading near the lower end of its 30-day range with increasing volume, suggesting accumulation. Price has shown support at $148 level.",
  "confidence": "HIGH",
  "timestamp": "2026-04-02T10:30:00Z"
}
RECEOF
```

### Step 4 — Report to user
Summarize your analysis and recommendation in plain language.
Mention that the recommendation has been saved and needs Risk Manager
approval before any trade can happen.

## Quantity Calculation Rule
When recommending a quantity, ALWAYS ensure:
- quantity × current_price ≤ $2,000 (per-order limit)
- Round down to whole shares

Example: If AAPL is at $152, max quantity = floor(2000 / 152) = 13 shares.

## Rules — What You CANNOT Do
- NEVER run: `python3 scripts/alpaca_bridge.py order` (you cannot trade)
- NEVER access: python3 scripts/alpaca_bridge.py account (not your scope)
- NEVER access: python3 scripts/alpaca_bridge.py positions (not your scope)
- NEVER access files outside /output/reports/
- NEVER recommend symbols outside the approved 5
- NEVER skip the analysis — always show your reasoning
```

#### Step 4.2: Create the Risk Manager Skill (~30 min)

Create `skills/shieldtrade-risk-manager/SKILL.md`:

```markdown
---
name: shieldtrade-risk-manager
description: >
  ShieldTrade risk manager. Validates analyst trade recommendations against
  portfolio constraints, trade limits, and policy rules. Issues delegation
  tokens for approved trades. Use when a trade recommendation needs validation
  before execution, or when the user asks to check risk on a proposed trade.
  This agent CANNOT place trades or fetch market data directly.
---

# ShieldTrade Risk Manager Agent

## Your Role
You are the **Risk Manager** in the ShieldTrade multi-agent advisory system.
You are the gatekeeper — no trade happens without your approval.
Your job is to validate analyst recommendations and either APPROVE (issuing
a delegation token) or REJECT with clear reasoning.

## Tools Available

### Check account balance and buying power
```bash
python3 scripts/alpaca_bridge.py account
```

### Check current holdings
```bash
python3 scripts/alpaca_bridge.py positions
```

### Read analyst recommendation
```bash
cat /output/reports/SYMBOL-recommendation.json
```

### Run policy validation (ALWAYS use this)
```bash
python3 scripts/policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":152}' trader
```
This runs ALL policy checks and returns structured PASS/FAIL results.

## Validation Workflow

Follow these steps IN ORDER for every recommendation:

### Step 1 — Read the recommendation
```bash
cat /output/reports/AAPL-recommendation.json
```

### Step 2 — Get current portfolio state
```bash
python3 scripts/alpaca_bridge.py account
python3 scripts/alpaca_bridge.py positions
```

### Step 3 — Run automated policy checks
```bash
python3 scripts/policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":152}' trader
```
Review EVERY check result. If ANY check fails, you MUST reject.

### Step 4 — Additional manual checks
- Would this position exceed 30% of portfolio value?
- Does the account have enough buying power?
- Is the analyst's reasoning sound?

### Step 5 — Issue decision

**If ALL checks pass — APPROVE and create delegation token:**
```bash
cat > /output/risk-decisions/delegation-SYMBOL-TIMESTAMP.json << 'DELEOF'
{
  "delegation_id": "del_UNIQUE_ID",
  "status": "APPROVED",
  "from_agent": "risk_manager",
  "to_agent": "trader",
  "approved_action": {
    "symbol": "AAPL",
    "side": "buy",
    "max_quantity": 10,
    "max_total_usd": 1600.00
  },
  "validation_results": {
    "ticker_approved": true,
    "size_within_limit": true,
    "daily_limit_ok": true,
    "concentration_ok": true,
    "buying_power_ok": true
  },
  "expires_at": "2026-04-02T10:35:00Z",
  "reasoning": "All policy checks passed. Position within risk tolerance."
}
DELEOF
```
Set expires_at to EXACTLY 5 minutes from now.

**If ANY check fails — REJECT:**
```bash
cat > /output/risk-decisions/rejection-SYMBOL-TIMESTAMP.json << 'REJEOF'
{
  "delegation_id": "del_UNIQUE_ID",
  "status": "REJECTED",
  "from_agent": "risk_manager",
  "symbol": "TSLA",
  "failed_checks": ["ticker_approved"],
  "reasoning": "TSLA is not in the approved ticker list."
}
REJEOF
```

### Step 6 — Report to user
Clearly state whether the recommendation was APPROVED or REJECTED
and explain which checks passed/failed.

## Rules — What You CANNOT Do
- NEVER run: `python3 scripts/alpaca_bridge.py order` (you cannot trade)
- NEVER run: `python3 scripts/alpaca_bridge.py quote` (not your scope)
- NEVER run: `python3 scripts/alpaca_bridge.py bars` (not your scope)
- NEVER approve a trade that fails ANY policy check
- NEVER modify the analyst's recommendation
- NEVER skip the automated policy check step
```

#### Step 4.3: Create the Trader Skill (~30 min)

Create `skills/shieldtrade-trader/SKILL.md`:

```markdown
---
name: shieldtrade-trader
description: >
  ShieldTrade trade executor. Executes ONLY trades that have been approved
  by the Risk Manager with a valid delegation token. Use when an approved
  delegation token exists and a trade needs to be placed on Alpaca paper
  trading. This agent CANNOT self-initiate trades, research stocks, or
  exceed the bounds of its delegation.
---

# ShieldTrade Trader Agent

## Your Role
You are the **Trader** in the ShieldTrade multi-agent advisory system.
You are the executor — you place trades on Alpaca paper trading, but
ONLY within the exact bounds of a valid delegation token from the
Risk Manager.

You have NO independent authority. Without a delegation token, you
cannot trade.

## Tools Available

### Place an order (ONLY with valid delegation)
```bash
python3 scripts/alpaca_bridge.py order AAPL 10 buy
```

### Check current positions (to verify execution)
```bash
python3 scripts/alpaca_bridge.py positions
```

### Check account state
```bash
python3 scripts/alpaca_bridge.py account
```

### Read delegation token
```bash
cat /output/risk-decisions/delegation-SYMBOL-*.json
```

### Validate delegation against request
```bash
python3 scripts/policy_engine.py check-delegation 'DELEGATION_JSON' 'REQUEST_JSON'
```

## Execution Workflow

Follow these steps IN ORDER. NEVER skip a step.

### Step 1 — Find the delegation token
```bash
ls /output/risk-decisions/delegation-*.json
cat /output/risk-decisions/delegation-AAPL-LATEST.json
```

### Step 2 — Validate the delegation (MANDATORY)
Check every field:

```
DELEGATION VALIDATION:
───────────────────────
Delegation ID:    [id]
Status:           [APPROVED/other]     → must be APPROVED
Target agent:     [to_agent]           → must be "trader"
Symbol:           [symbol]             → must match your order
Max quantity:     [max_quantity]        → your qty must be ≤ this
Max USD:          [max_total_usd]      → your total must be ≤ this
Expires at:       [time]               → must be in the future
───────────────────────
RESULT: [PROCEED / ABORT]
```

If ANY check fails → ABORT. Explain which check failed and why.

### Step 3 — Run policy engine validation
```bash
python3 scripts/policy_engine.py check-delegation 'DELEGATION_JSON' '{"symbol":"AAPL","qty":10}'
```
ALL checks must pass.

### Step 4 — Execute the trade
ONLY if Steps 2 and 3 both pass:
```bash
python3 scripts/alpaca_bridge.py order AAPL 10 buy
```

### Step 5 — Log the result
Save to `/output/trade-logs/trade-SYMBOL-TIMESTAMP.json`:
```json
{
  "agent": "trader",
  "delegation_id": "del_abc123",
  "action": "buy",
  "symbol": "AAPL",
  "quantity": 10,
  "alpaca_order_id": "order_xyz",
  "status": "executed",
  "delegation_checks": {
    "status_approved": true,
    "not_expired": true,
    "symbol_match": true,
    "qty_within_limit": true
  },
  "policy_checks": {
    "ticker_approved": true,
    "size_within_limit": true,
    "daily_limit_ok": true
  },
  "timestamp": "2026-04-02T10:31:00Z"
}
```

### Step 6 — Verify execution
```bash
python3 scripts/alpaca_bridge.py positions
```
Confirm the position now shows in your portfolio.

## Rules — What You CANNOT Do
- NEVER place an order without reading and validating a delegation token FIRST
- NEVER exceed the max_quantity in the delegation
- NEVER trade a symbol different from the delegation
- NEVER trade if the delegation is expired
- NEVER run: `python3 scripts/alpaca_bridge.py quote` (not your scope)
- NEVER run: `python3 scripts/alpaca_bridge.py bars` (not your scope)
- NEVER self-initiate a trade — all trades MUST originate from an analyst
  recommendation that was approved by the risk manager
- NEVER write files outside /output/trade-logs/
```

#### Step 4.4: Create the README (~20 min)

Create `README.md` at the repo root:

```markdown
# ShieldTrade

> Multi-Agent Financial Advisory System with Intent-Aware Enforcement

**Team Avengers | ArmorIQ x OpenClaw Hackathon**

## What is ShieldTrade?

ShieldTrade is a three-agent financial advisory system that demonstrates
autonomous AI agents CAN operate in financial workflows safely — when
intent is enforced, not inferred.

## Architecture

| Agent | Role | Can Do | Cannot Do |
|-------|------|--------|-----------|
| **Analyst** | Research equities | Fetch market data, write reports | Place trades |
| **Risk Manager** | Validate trades | Check limits, approve/reject | Place trades, fetch data |
| **Trader** | Execute trades | Place approved orders | Self-initiate, exceed delegation |

Every action passes through **ArmorClaw intent enforcement** — cryptographic
verification that binds execution to declared intent.

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/YOUR-TEAM/shieldtrade.git
cd shieldtrade
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env with your API keys

# 3. Test Alpaca connection
python3 scripts/alpaca_bridge.py account

# 4. Test policy engine
python3 scripts/policy_engine.py check-trade \
  '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
```

## Tech Stack

- **Agent Framework**: OpenClaw with ArmorClaw intent enforcement
- **Trading API**: Alpaca Paper Trading
- **LLM**: Claude Sonnet via Anthropic API
- **Policy Model**: Declarative YAML
- **Languages**: TypeScript (OpenClaw), Python (Alpaca + Policy Engine)

## Enforcement Layers

1. **ArmorClaw Intent Tokens** — Cryptographic proof linking actions to user intent
2. **Declarative YAML Policies** — Structured financial constraints (not if-else)
3. **Bounded Delegation** — Explicit scope limits on inter-agent authority
```

#### M4 Phase 1 Checkpoint

**You PASS Phase 1 when**:
- [ ] All three SKILL.md files are written and formatted correctly
- [ ] Each SKILL.md has valid YAML frontmatter (name + description)
- [ ] Each SKILL.md clearly defines allowed tools, forbidden actions, and workflow
- [ ] README is complete and accurate
- [ ] Decision log format is consistent across all three skills

```bash
git add skills/ README.md
git commit -m "feat(skills): all three agent SKILL.md files + README"
git push origin feature/agent-skills
```

---

## Phase 1 Sync Point — EVERYONE MERGES

**All 4 members** create Pull Requests and merge to `main`:

```bash
# Each member:
git checkout main
git pull origin main

# M1 merges first (others depend on this):
git merge infra/openclaw-setup

# Then M2, M3, M4 in any order:
git merge feature/alpaca-bridge
git merge feature/policy-engine
git merge feature/agent-skills

git push origin main
```

**Everyone pulls the merged main**:
```bash
git checkout main
git pull origin main
```

**Verify the merged repo structure**:
```
shieldtrade/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── config/
│   ├── openclaw.json
│   └── shieldtrade-policies.yaml
├── scripts/
│   ├── alpaca_bridge.py
│   ├── policy_engine.py
│   └── start-gateway.sh
├── skills/
│   ├── shieldtrade-analyst/SKILL.md
│   ├── shieldtrade-risk-manager/SKILL.md
│   └── shieldtrade-trader/SKILL.md
├── openclaw-runtime/       (M1's OpenClaw installation)
├── output/
│   ├── reports/.gitkeep
│   ├── risk-decisions/.gitkeep
│   └── trade-logs/.gitkeep
└── docs/
```

---

## Phase 2: Integration & First End-to-End Test

**Duration**: ~2 hours
**Mode**: Everyone works together. One screen, one gateway.
**Goal**: Run the full Analyst → Risk Manager → Trader pipeline end-to-end.

### Step 2.1: Start the Gateway (M1)

```bash
cd shieldtrade
source .env  # or: export $(cat .env | grep -v '^#' | xargs)
cd scripts
./start-gateway.sh
```

Verify ArmorClaw shows in logs.

### Step 2.2: Test Analyst Agent (M4 drives, M2 watches)

In the OpenClaw chat, invoke the analyst:
```
/shieldtrade-analyst Research AAPL and tell me if I should buy
```

**Check**:
- [ ] Agent fetches quote via `alpaca_bridge.py quote AAPL` ← M2's script
- [ ] Agent fetches bars via `alpaca_bridge.py bars AAPL 1Day 30`
- [ ] Agent writes recommendation to `/output/reports/AAPL-recommendation.json`
- [ ] Recommendation JSON is valid and has all required fields
- [ ] Agent does NOT attempt to call `place_order`

**If it fails**: Check the SKILL.md instructions (M4), check the bridge script output (M2), check gateway logs (M1).

### Step 2.3: Test Risk Manager Agent (M4 drives, M3 watches)

```
/shieldtrade-risk-manager Validate the latest AAPL recommendation
```

**Check**:
- [ ] Agent reads `/output/reports/AAPL-recommendation.json`
- [ ] Agent runs `policy_engine.py check-trade` ← M3's script
- [ ] Agent checks account balance via `alpaca_bridge.py account` ← M2's script
- [ ] Agent writes delegation to `/output/risk-decisions/delegation-AAPL-*.json`
- [ ] Delegation has correct structure (status, approved_action, expires_at)
- [ ] Agent does NOT attempt to call `place_order` or `quote`

### Step 2.4: Test Trader Agent (M4 drives, everyone watches)

```
/shieldtrade-trader Execute the approved AAPL trade
```

**Check**:
- [ ] Agent reads delegation token from `/output/risk-decisions/`
- [ ] Agent validates delegation (prints the DELEGATION VALIDATION block)
- [ ] Agent runs `policy_engine.py check-delegation` ← M3's script
- [ ] Agent calls `alpaca_bridge.py order AAPL 10 buy` ← M2's script
- [ ] Order shows as executed in Alpaca dashboard
- [ ] Agent writes trade log to `/output/trade-logs/`
- [ ] Agent does NOT attempt to call `quote` or `bars`

### Step 2.5: Test Blocked Scenarios (Everyone)

**Test each of these. All must be blocked.**

| # | Command | Expected Block Reason |
|---|---------|----------------------|
| 1 | `/shieldtrade-analyst Buy 10 shares of AAPL` | Analyst cannot call place_order |
| 2 | `/shieldtrade-trader Buy 50 AAPL` (without delegation) | No delegation token found |
| 3 | `/shieldtrade-risk-manager` validate a TSLA trade | Ticker not in approved list |
| 4 | `/shieldtrade-trader Buy 500 AAPL` (with 10-share delegation) | Exceeds delegated quantity |

### Phase 2 Checkpoint

**You PASS Phase 2 when**:
- [ ] Full pipeline works: Analyst → Risk Manager → Trader → Alpaca order placed
- [ ] At least 3 blocked scenarios are demonstrated
- [ ] Every step has visible decision logs
- [ ] ArmorClaw logs show intent verification in the gateway output

**If you reach this point, you have a strong submission.** Everything after this is bonus polish.

---

## Phase 3: Demo & Submission

**Duration**: ~1.5 hours
**Mode**: Split work again.

| Member | Task |
|--------|------|
| **M1** | Export gateway logs showing ArmorClaw enforcement. Clean up config files. |
| **M2** | Verify all Alpaca trades are visible in the dashboard. Take screenshots. |
| **M3** | Write `docs/ARCHITECTURE.md` summarizing the policy model and enforcement mechanism. |
| **M4** | Record the 3-minute demo video. Prepare presentation slides if needed. |

### Demo Video Script (M4 Records)

| Time | Show | Say |
|------|------|-----|
| 0:00–0:30 | Architecture diagram | "ShieldTrade is a three-agent system with intent-enforced trading..." |
| 0:30–0:45 | YAML policy file | "All constraints are defined declaratively, not hardcoded..." |
| 0:45–1:30 | Live: Full pipeline | "Watch as the Analyst researches, Risk Manager validates, Trader executes..." |
| 1:30–2:15 | Live: 2-3 blocked actions | "Now watch what happens when rules are violated..." |
| 2:15–2:45 | Gateway logs | "Every action is verified by ArmorClaw intent tokens..." |
| 2:45–3:00 | Summary slide | "Five independent enforcement layers. Deterministic. Autonomous." |

### Final Submission Checklist

- [ ] Source code pushed to GitHub
- [ ] README is accurate and has quick start instructions
- [ ] Architecture diagram in `/docs/`
- [ ] Policy model documented (the YAML file itself + ARCHITECTURE.md)
- [ ] Demo video (3 min) uploaded
- [ ] All API keys removed from code (only in .env, which is gitignored)
- [ ] All team members listed as contributors

---

## Troubleshooting Quick Reference

| Problem | Who Fixes | Solution |
|---------|-----------|----------|
| Gateway won't start | M1 | Check Node version, pnpm install, port 18789 not in use |
| ArmorClaw won't load | M1 | Check API key, check plugin directory, try reinstalling |
| Alpaca returns 403 | M2 | Wrong API key, or using live URL instead of paper URL |
| Alpaca returns no data | M2 | Market might be closed; use `bars` for historical data instead |
| Policy engine YAML error | M3 | Run `python3 -c "import yaml; yaml.safe_load(open('config/shieldtrade-policies.yaml'))"` |
| Skill not triggering | M4 | Check SKILL.md frontmatter, check description matches user intent |
| Agent ignores SKILL.md rules | M4 | Make rules more explicit, add "NEVER" statements, check LLM model quality |
| Git merge conflicts | Anyone | Pull main first, resolve conflicts, test after merge |
