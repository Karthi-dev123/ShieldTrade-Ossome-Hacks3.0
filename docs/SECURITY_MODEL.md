# ShieldTrade — Security Model

This document describes the three pillars of ShieldTrade's security architecture: the **Intent Model**, the **Policy Model**, and the **Enforcement Mechanism**.

---

## 1. Intent Model

### What Is an Intent?

An **intent** is a structured declaration of what an agent plans to do _before_ it does it. ShieldTrade uses ArmorIQ's intent-based security model to ensure every agent action is pre-declared, cryptographically signed, and verifiable.

### How It Works

```
Agent decides to act
       │
       ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ capture_plan │────▶│ get_intent   │────▶│   invoke     │
│              │     │   _token     │     │   (action)   │
│ "I want to   │     │              │     │              │
│  fetch data  │     │ Signed token │     │ Token +      │
│  and analyze"│     │ with plan    │     │ Merkle proof │
│              │     │ hash         │     │ verified     │
└──────────────┘     └──────────────┘     └──────────────┘
```

1. **Plan Capture** — The agent declares intended actions (e.g., `fetch_data`, `place_order`). The plan is sent to ArmorIQ API for canonicalization.
2. **Token Generation** — ArmorIQ signs the canonical plan hash with Ed25519, producing an intent token bound to the agent's identity, allowed actions, and an expiration time.
3. **Action Verification** — When the agent invokes a tool, ArmorIQ Proxy verifies the token signature, checks the Merkle proof (is this action in the plan?), and enforces policy constraints.

### Intent Token Structure

```json
{
  "token_id": "itk_abc123...",
  "plan_hash": "sha256:...",
  "agent_id": "shieldtrade-trader",
  "issued_at": "2026-04-04T08:00:00Z",
  "expires_at": "2026-04-04T08:05:00Z",
  "signature": "ed25519:...",
  "allowed_actions": ["place_order"],
  "constraints": {
    "max_usd": 2000,
    "approved_tickers": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"]
  }
}
```

### Key Properties

| Property | Description |
|---|---|
| **Immutable** | Once signed, the plan cannot be modified |
| **Time-Bound** | Tokens expire after 5 minutes (configurable) |
| **Agent-Scoped** | Token is bound to a specific agent identity |
| **Non-Reusable** | Each token can only be used for its declared actions |

---

## 2. Policy Model

### What Are Policies?

Policies are **declarative, deterministic rules** defined in YAML (`config/shieldtrade-policies.yaml`). They are evaluated by the policy engine without any LLM interpretation — the engine is pure Python logic that reads the YAML and returns ALLOW or BLOCK.

### Policy Categories

#### 2.1 Agent Role Permissions

Each agent has explicit allow/deny lists for tools and file access:

```yaml
agent_roles:
  analyst:
    allowed_tools: [market_data_fetch, write_report, recommend_trade]
    denied_tools: [place_order, get_account, shell, web_fetch]
    file_access:
      read: [/data/market/*, /data/earnings/*]
      write: [/output/reports/*]
```

**Rule**: If a tool is not in `allowed_tools`, the action is BLOCKED.

#### 2.2 Trading Constraints

```yaml
trading:
  order_limits:
    per_order_max_usd: 2000
    daily_aggregate_max_usd: 1000000
    per_order_max_shares: 100
  approved_tickers:
    symbols: [AAPL, MSFT, GOOGL, AMZN, NVDA]
  time_restrictions:
    market_hours_only:
      enabled: true
      start: "09:30"
      end: "16:00"
      timezone: America/New_York
```

**Rules**:
- Orders exceeding `per_order_max_usd` are BLOCKED
- Tickers not in `approved_tickers` are BLOCKED
- Orders outside market hours are BLOCKED

#### 2.3 Delegation Rules

```yaml
delegation:
  trader_delegation:
    required: true
    require_risk_approval: true
    expiry_minutes: 5
    from_agent: risk_manager
    to_agent: trader
```

**Rules**:
- Trader MUST have a delegation token from Risk Manager
- Token must be issued within the last 5 minutes
- Token must specify the exact ticker, max USD, and max shares

#### 2.4 Data Safety

```yaml
data_safety:
  no_external_exfiltration:
    allowed_domains: [paper-api.alpaca.markets, data.alpaca.markets]
    blocked_tools: [web_fetch, curl, wget]
```

**Rule**: Network calls to any domain not in `allowed_domains` are BLOCKED.

---

## 3. Enforcement Mechanism

### How Enforcement Works

The enforcement layer is implemented in `scripts/policy_engine.py`. It is deterministic — the same input always produces the same output. There is no LLM in the enforcement loop.

### Enforcement Pipeline

```
Trade Request
      │
      ▼
┌─────────────────┐
│ 1. Role Check   │ ── Is the agent allowed to use this tool?
└────────┬────────┘
         │
┌────────▼────────┐
│ 2. Market Hours │ ── Is the market currently open?
└────────┬────────┘
         │
┌────────▼────────┐
│ 3. Ticker Check │ ── Is this ticker in the approved list?
└────────┬────────┘
         │
┌────────▼────────┐
│ 4. Size Limits  │ ── Does this order exceed per-order or daily caps?
└────────┬────────┘
         │
┌────────▼────────┐
│ 5. Network      │ ── Is the target domain allowed?
└────────┬────────┘
         │
┌────────▼────────┐
│ 6. Delegation   │ ── Does the trader have a valid, unexpired token?
└────────┬────────┘
         │
         ▼
   ┌───────────┐
   │  DECISION  │
   │ ALLOW or   │
   │ BLOCK      │
   └─────┬─────┘
         │
         ▼
┌────────────────┐
│ 7. Audit Log   │ ── Persist to Supabase (policy_checks table)
└────────────────┘
```

### Decision Logic

The `validate_trade()` function runs all applicable checks and aggregates results:

```python
def validate_trade(request, policy):
    checks = []
    checks.append(check_role_permission(agent, tool, policy))
    checks.append(check_market_hours(policy))
    checks.append(check_ticker(ticker, policy))
    checks.append(check_share_count(shares, policy))
    checks.append(check_order_size(amount_usd, policy))
    checks.append(check_daily_limit(amount_usd, policy))
    checks.append(check_data_safety(domain, policy))
    checks.append(check_delegation(delegation, policy))

    failed = [c for c in checks if c["result"] == "FAIL"]
    decision = "BLOCK" if failed else "ALLOW"
    # ... log to Supabase ...
    return {"decision": decision, "checks": checks, "blocked_reasons": [...]}
```

**Key principle**: If _any_ check fails, the entire request is BLOCKED. This is fail-closed by design.

### Audit Persistence

Every policy decision is logged to Supabase via `scripts/supabase_logger.py`:

```
┌──────────────────────────────────────────────┐
│             Supabase (Postgres)              │
├──────────────────────────────────────────────┤
│ Table: policy_checks                         │
│   - decision (ALLOW/BLOCK)                   │
│   - agent, tool, ticker                      │
│   - checks (JSONB array of pass/fail)        │
│   - blocked_reasons (text array)             │
│   - timestamp                                │
├──────────────────────────────────────────────┤
│ Table: trade_events                          │
│   - order_id, symbol, qty, side              │
│   - status, submitted_at                     │
│   - policy_check_id (FK to policy_checks)    │
└──────────────────────────────────────────────┘
```

The `policy_check_id` in `trade_events` links each executed trade back to the specific policy check that authorized it, providing a complete audit chain.

---

## Summary

| Layer | Component | Type |
|---|---|---|
| **Intent Model** | ArmorIQ tokens | Cryptographic (Ed25519 + Merkle) |
| **Policy Model** | YAML rules | Declarative, deterministic |
| **Enforcement** | `policy_engine.py` | Pure Python, no LLM |
| **Audit** | Supabase | Persistent, linked |
| **Fail Mode** | Fail-closed | BLOCK on any failure |
