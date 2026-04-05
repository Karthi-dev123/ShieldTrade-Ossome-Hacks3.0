# ShieldTrade — Architecture

## Design Philosophy

Intent must be **enforced**, not inferred.

ShieldTrade implements a layered enforcement stack where every financial action passes through:
1. A **declarative YAML policy model** (rules live in config, not code)
2. A **typed Pydantic intent model** (every request is schema-validated before any check runs)
3. A **cryptographic intent token** (HMAC-SHA256 signed by ArmorIQ stub before each paper order)
4. The **Alpaca paper-trading API** (no real money ever touched)

OpenClaw provides the agent runtime and skills infrastructure. Enforcement is handled by the local Python stack — this is an intentional architectural decision to eliminate cloud dependencies during inference.

---

## Runtime Stack

```
┌─────────────────────────────────────────────────────────────────┐
│                        OpenClaw Gateway                          │
│                    (port 18789, local mode)                       │
│                                                                   │
│  ┌─────────────┐   ┌──────────────────┐   ┌─────────────────┐  │
│  │  Analyst     │   │  Risk Manager    │   │    Trader        │  │
│  │  Agent       │   │  Agent           │   │    Agent         │  │
│  │  (SKILL.md)  │   │  (SKILL.md)      │   │    (SKILL.md)    │  │
│  └──────┬───────┘   └────────┬─────────┘   └────────┬────────┘  │
└─────────┼────────────────────┼─────────────────────-┼────────────┘
          │  CLI handoffs       │  (JSON artifacts)    │
          ▼                     ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│              Local Python Enforcement Layer                       │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  scripts/policy_engine.py                                  │  │
│  │                                                            │  │
│  │  TradeIntent (Pydantic)   ←── schema-validates request     │  │
│  │  ShieldTradePolicy (Pydantic) ←── validates YAML at load   │  │
│  │                                                            │  │
│  │  check_role_permission()  ← agent_roles from YAML          │  │
│  │  check_ticker()           ← approved_tickers from YAML     │  │
│  │  check_order_size()       ← order_limits from YAML         │  │
│  │  check_daily_limit()      ← daily_aggregate_max_usd        │  │
│  │  check_market_hours()     ← time_restrictions from YAML    │  │
│  │  check_earnings_blackout()← blackout events from YAML      │  │
│  │  check_delegation()       ← delegation caps from YAML      │  │
│  │  check_data_safety()      ← allowed_domains from YAML      │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  scripts/armoriq_stub.py                                   │  │
│  │  HMAC-SHA256 intent token → attached to every paper order  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  scripts/alpaca_bridge.py                                  │  │
│  │  Paper-trading execution (Alpaca paper API only)           │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  config/shieldtrade-policies.yaml  ←── single source of truth   │
│  (all limits, tickers, roles, delegation caps declared here)     │
└─────────────────────────────────────────────────────────────────┘
```

### LLM Routing (inference only)

OpenClaw does not communicate directly with an LLM API. Requests are proxied through a local shim:

```
OpenClaw Gateway → scripts/proxy.js (port 4000) → Ollama (OLLAMA_BASE_URL)
```

`proxy.js` injects the `data: [DONE]\n\n` SSE sentinel when Ollama closes a stream without it, preventing OpenClaw agent "stream ended" errors.

---

## Why Enforcement is Local (not an OpenClaw Plugin)

The PS allows use of ArmorClaw as an intent enforcement plugin, but also permits custom enforcement layers. ShieldTrade implements enforcement locally for three reasons:

1. **No cloud dependency** — Ollama + proxy.js + policy_engine.py run entirely offline. Enforcement cannot be bypassed by a cloud outage.
2. **Determinism** — The YAML policy is a static file in the repo. Every check is reproducible and auditable without an API call.
3. **Transparency** — Judges can read `config/shieldtrade-policies.yaml` and `scripts/policy_engine.py` to see exactly what is enforced and why.

`config/openclaw.json` lists only the `google` plugin. **This is intentional** — ArmorIQ enforcement runs in-process via `armoriq_stub.py`, not as an OpenClaw plugin.

---

## Data Flow

### Happy Path (Successful Trade)

```
1. Analyst stage
   → fetches/assumes market price
   → writes output/reports/{TICKER}-recommendation.json

2. Risk stage
   → reads recommendation
   → calls validate_trade(request, policy, record_spend_if_allow=False)
   → if ALLOW: builds & writes output/risk-decisions/delegation-{TICKER}-{id}.json

3. Trader stage
   → reads delegation token
   → calls validate_trade(request+delegation, policy, record_spend_if_allow=True)
   → if ALLOW: armoriq_stub signs intent token
               alpaca_bridge places paper order with token attached
               writes output/trade-logs/execution-{TICKER}-{ISO}.json
               records spend in output/trade-logs/daily-spend.json
```

### Blocked Path (Policy Violation)

```
1. Any stage → requests action outside policy scope
2. validate_trade() runs all deterministic checks
3. Any FAIL → decision = BLOCK, blocked_reasons populated
4. Downstream stages are skipped
5. Rejection JSON written to output/risk-decisions/ or output/trade-logs/
```

---

## Agent Directory Boundaries

### Read/Write Access Matrix

| Agent | Read Access | Write Access |
|---|---|---|
| **Analyst** | `/data/market/*`, `/data/earnings/*` | `/output/reports/*` |
| **Risk Manager** | `/output/reports/*`, `/data/portfolio/*` | `/output/risk-decisions/*` |
| **Trader** | `/output/risk-decisions/*` | `/output/trade-logs/*` |

File-level isolation is declared in `config/shieldtrade-policies.yaml` under `agent_roles.*.file_access`. Skills reference these paths; the orchestrator respects them by design.

---

## Security Model

### Enforcement Layers (outermost → innermost)

| Layer | Mechanism | Where declared |
|-------|-----------|----------------|
| Role permission | `check_role_permission()` | `agent_roles.*.allowed_tools` in YAML |
| Market hours | `check_market_hours()` | `trading.time_restrictions.market_hours_only` |
| Ticker allow-list | `check_ticker()` | `trading.approved_tickers.symbols` |
| Earnings blackout | `check_earnings_blackout()` | `trading.time_restrictions.earnings_blackout` |
| Order size cap | `check_order_size()` | `trading.order_limits.per_order_max_usd` |
| Share count cap | `check_share_count()` | `trading.order_limits.per_order_max_shares` |
| Daily spend cap | `check_daily_limit()` | `trading.order_limits.daily_aggregate_max_usd` |
| Network exfiltration | `check_data_safety()` | `data_safety.no_external_exfiltration.allowed_domains` |
| Delegation scope | `check_delegation()` | `delegation.trader_delegation.*` |
| Intent token | ArmorIQ HMAC-SHA256 | `scripts/armoriq_stub.py` |

All checks are **fail-closed**: missing or malformed policy sections block rather than allow.

### Credential Safety

- No credentials in source code.
- `.env` is gitignored.
- Blocked paths in policy: `~/.openclaw/credentials`, `*.env`, `*.key`, `*.pem`, `*.secret`.

---

## Directory Structure

```
shieldtrade/
├── config/
│   ├── openclaw.json              # OpenClaw gateway + model config
│   └── shieldtrade-policies.yaml  # Declarative policy (single source of truth)
│
├── scripts/
│   ├── policy_engine.py           # Enforcement engine (Pydantic models + checks)
│   ├── armoriq_stub.py            # HMAC-SHA256 intent token issuance
│   ├── alpaca_bridge.py           # Paper-trading execution
│   ├── orchestrate_pipeline.py    # E2E analyst → risk → trader orchestrator
│   ├── proxy.js                   # OpenAI-compatible proxy to Ollama
│   └── start-all.py               # Service startup (proxy + gateway)
│
├── skills/
│   ├── shieldtrade-analyst/SKILL.md
│   ├── shieldtrade-risk-manager/SKILL.md
│   └── shieldtrade-trader/SKILL.md
│
├── output/                        # Agent artifacts (gitignored except .gitkeep)
│   ├── reports/
│   ├── risk-decisions/
│   └── trade-logs/
│
├── tests/
│   ├── test_policy_engine.py      # 23 unit tests
│   ├── test_orchestrate_pipeline.py # 9 integration tests
│   ├── test_m2_policy_guards.py   # 3 CLI contract tests
│   └── test_armoriq_stub.py       # 7 ArmorIQ stub tests
│
└── docs/
    ├── architecture.md            # This file
    ├── contracts.md               # Schema freeze — handoff JSON shapes + CLI
    ├── submission.md              # Judge-facing: intent model, policy, enforcement
    ├── demo-script.md             # 2-minute judge demo with commands
    └── troubleshooting.md         # Startup and runtime troubleshooting
```
