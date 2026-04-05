# ShieldTrade — Submission Document

## System Overview

ShieldTrade is a multi-agent financial advisory system built on OpenClaw that demonstrates **intent-aware execution** in an autonomous financial workflow.

Three specialized agents (Analyst, Risk Manager, Trader) collaborate through deterministic, machine-readable handoffs. Every financial action is validated against a declarative policy model before execution. No action bypasses the enforcement layer.

---

## 1. Intent Model

An **intent** captures what an agent is trying to do, with whom, on what instrument, at what scale, and under what authority.

### `TradeIntent` (Pydantic model — `scripts/policy_engine.py`)

```python
class TradeIntent(BaseModel):
    agent: str          # WHO is acting (analyst / risk_manager / trader)
    tool: str           # WHAT they want to do (place_order / approve_trade / …)
    ticker: str         # ON WHAT instrument
    shares: int         # AT WHAT scale (share count)
    amount_usd: float   # AT WHAT scale (notional USD)
    domain: str         # WHERE the request targets (API host)
    delegation: Optional[DelegationToken]  # UNDER WHAT AUTHORITY
```

Every call to `validate_trade()` coerces the incoming request into a `TradeIntent` before any check runs. A malformed or missing field raises a Pydantic `ValidationError` — enforcement fails closed.

### `DelegationToken` (Pydantic model — `scripts/policy_engine.py`)

```python
class DelegationToken(BaseModel):
    issued_by: str     # Must be "risk_manager"
    issued_to: str     # Must be "trader"
    ticker: str        # Scope-limited to one symbol
    max_usd: float     # Spending cap for this delegation
    max_shares: int    # Share cap for this delegation
    issued_at: str     # Issuance timestamp (TTL validated against expiry_minutes)
    token_id: str      # Unique audit ID
```

The Trader agent cannot execute any order without a valid `DelegationToken`. The token must come from `risk_manager`, target `trader`, match the requested ticker, and not be expired.

---

## 2. Policy Model

All rules are declared in `config/shieldtrade-policies.yaml`. The YAML is validated against a Pydantic `ShieldTradePolicy` schema at startup — a misconfigured policy file fails loudly before any agent runs.

### `ShieldTradePolicy` schema hierarchy

```
ShieldTradePolicy
├── metadata          version, system, enforcement mode
├── agent_roles       per-agent allowed_tools, denied_tools, file_access
├── trading
│   ├── order_limits  per_order_max_usd, per_order_max_shares, daily_aggregate_max_usd
│   ├── approved_tickers  symbols allow-list
│   └── time_restrictions
│       ├── market_hours_only  enabled, start/end, timezone
│       └── earnings_blackout  enabled, window_before/after_minutes, events[]
├── delegation
│   └── trader_delegation
│       ├── expiry_minutes
│       ├── max_shares_per_delegation  (YAML ceiling; token cannot exceed this)
│       └── max_usd_per_delegation     (YAML ceiling; token cannot exceed this)
└── data_safety
    └── no_external_exfiltration  allowed_domains, blocked_domains
```

### Current policy limits (from YAML)

| Constraint | Value |
|------------|-------|
| Approved tickers | AAPL, MSFT, GOOGL, AMZN, NVDA |
| Per-order max USD | $2,000 |
| Per-order max shares | 100 |
| Daily aggregate max USD | $10,000 |
| Delegation max shares | 100 (YAML ceiling) |
| Delegation max USD | $2,000 (YAML ceiling) |
| Delegation TTL | 5 minutes |
| Market hours | 09:30–16:00 ET, weekdays only |
| Earnings blackout | Configurable per ticker (disabled by default) |
| Allowed API domains | `paper-api.alpaca.markets`, `data.alpaca.markets` |

---

## 3. Enforcement Mechanism

### Architecture

```
TradeIntent (Pydantic)
       │
       ▼
validate_trade()  ← policy_engine.py
       │
       ├── check_role_permission()   agent_roles from YAML
       ├── check_market_hours()      time_restrictions from YAML
       ├── check_ticker()            approved_tickers from YAML
       ├── check_earnings_blackout() blackout events from YAML
       ├── check_share_count()       per_order_max_shares
       ├── check_order_size()        per_order_max_usd
       ├── check_daily_limit()       daily_aggregate_max_usd
       ├── check_data_safety()       allowed_domains
       └── check_delegation()        delegation caps + TTL expiry
              │
              ▼
         ALLOW / BLOCK  (JSON output with per-check audit trail)
              │
         ALLOW only ──► armoriq_stub.sign_intent()  (HMAC-SHA256 token)
                               │
                               ▼
                         alpaca_bridge.cmd_order()  (paper order)
```

### Enforcement properties

- **Fail-closed**: Any missing or malformed policy section blocks the action.
- **Deterministic**: Same request + same policy = same decision, always.
- **Auditable**: Every `validate_trade()` call emits a JSON result with one `{check, result, detail}` entry per check and a `blocked_reasons` list.
- **No human-in-the-loop**: Enforcement is programmatic and autonomous.

### Delegation enforcement (bonus scenario)

ShieldTrade implements the full bounded delegation scenario:

1. **Risk Manager** validates the analyst's recommendation against policy, then issues a `DelegationToken` with ticker scope, share cap, USD cap, and TTL.
2. `build_delegation()` caps the token at issuance against the YAML ceiling (`max_shares_per_delegation` / `max_usd_per_delegation`) — an over-scoped token is never written to disk.
3. **Trader** presents the token to `check_delegation()`, which enforces:
   - Issuer must be `risk_manager`
   - Target must be `trader`
   - Token age must be within TTL (`expiry_minutes`)
   - Token `max_shares` must not exceed YAML ceiling
   - Token `max_usd` must not exceed YAML ceiling
   - Requested shares must not exceed token `max_shares`
   - Requested amount must not exceed token `max_usd`
4. Any violation blocks the order.

### ArmorIQ intent tokens

`scripts/armoriq_stub.py` implements a local ArmorIQ-compatible intent token issuer. Before each paper order, `cmd_order()` calls `sign_intent()`, which produces an HMAC-SHA256 token encoding the ticker, quantity, side, and timestamp. The token is attached to the order metadata and logged in the execution artifact.

---

## 4. Demo Commands

### Happy path (dry-run, no Alpaca credentials needed)

```bash
python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run
```

Expected: `"ok": true, "dry_run": true` with artifacts under `output/`.

### Blocked: unapproved ticker

```bash
python scripts/orchestrate_pipeline.py TSLA --shares 5 --assume-price 100 --dry-run
```

Expected: `"ok": false, "stopped_at": "risk"`, BLOCK due to ticker not in allow-list.

### Blocked: order exceeds per-order cap

```bash
python scripts/orchestrate_pipeline.py AAPL --shares 60 --assume-price 100 --dry-run
```

Expected: `"ok": false, "stopped_at": "risk"`, BLOCK due to `$6000 > $2000 per_order_max_usd`.

### Run test suite (41 tests)

```bash
python -m pytest tests -q
```

---

## 5. OpenClaw Integration

- OpenClaw gateway runs in local mode (`config/openclaw.json`) with token auth.
- Three agent skills (`skills/shieldtrade-*/SKILL.md`) define each agent's behavior, tool usage, and handoff contracts.
- `scripts/proxy.js` provides an OpenAI-compatible surface for Ollama, with a streaming sentinel fix for OpenClaw compatibility.
- The deterministic pipeline (`orchestrate_pipeline.py`) can run independently of the LLM for CI and judge verification.
