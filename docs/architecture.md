# ShieldTrade — Architecture

## System Overview

### LLM Proxy Layer
To bypass provider strict rate limits, OpenClaw does not communicate directly with the LLM API. Instead, requests are routed through a local interception layer:

* **Proxy Server:** `scripts/proxy.js` (Express.js server running on port 4000)
* **Target Model:** `gemini-3-flash-preview`
* **Function:** Intercepts requests from OpenClaw aimed at the Google GenAI SDK, applies key rotation, and proxies the requests to Google's API to ensure the agent instruction footprint can be processed without rate limit failures.

```
┌─────────────────────────────────────────────────────────┐
│                    OpenClaw Gateway                      │
│                  (Node.js / TypeScript)                   │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Analyst     │  │ Risk Manager │  │    Trader     │  │
│  │   Agent       │  │    Agent     │  │    Agent      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         │                  │                  │          │
│  ┌──────┴──────────────────┴──────────────────┴───────┐ │
│  │              ArmorClaw Intent Engine                 │ │
│  │         (Policy YAML → Cryptographic Tokens)        │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
   ┌────────────┐  ┌────────────┐  ┌────────────┐
   │  Python     │  │  Supabase  │  │  Alpaca    │
   │  Scripts    │  │  Audit DB  │  │  Paper API │
   │ (bridge/    │  │            │  │            │
   │  policy)    │  │            │  │            │
   └────────────┘  └────────────┘  └────────────┘
```

## Agent Directory Boundaries

### Read/Write Access Matrix

| Agent | Read Access | Write Access |
|---|---|---|
| **Analyst** | `/data/market/*`, `/data/earnings/*` | `/output/reports/*`, `/output/thoughts/analyst.jsonl` |
| **Risk Manager** | `/output/reports/*` | `/output/risk-decisions/*`, `/output/thoughts/risk-manager.jsonl` |
| **Trader** | `/output/risk-decisions/*` | `/output/trade-logs/*`, `/output/thoughts/trader.jsonl` |

### Boundary Enforcement
- ArmorClaw enforces file access at the intent token level
- Each agent's `writeAccess` is declared in `config/openclaw.json`
- Policy violations are logged to `audit_log` in Supabase and blocked deterministically

## Directory Structure

```
shieldtrade/
├── config/                          # OpenClaw + ArmorClaw configuration
│   ├── openclaw.json
│   └── shieldtrade-policies.yaml
│
├── scripts/                         # Python ONLY
│   ├── alpaca_bridge.py
│   └── policy_engine.py
│
├── skills/                          # OpenClaw agent skill definitions
│   ├── shieldtrade-analyst/
│   ├── shieldtrade-risk-manager/
│   └── shieldtrade-trader/
│
├── output/                          # Agent output (gitignored except .gitkeep)
│   ├── reports/
│   ├── risk-decisions/
│   ├── trade-logs/
│   └── thoughts/
│
├── data/
│   ├── market/
│   └── earnings/
│
├── tests/
│   └── test_policy_engine.py
│
├── docs/                            # All documentation lives here
│   ├── instructions.md              # How to use these docs
│   ├── requirements.md              # Stack, versions, constraints
│   ├── architecture.md              # This file
│   ├── memory.md                    # Session tracking
│   ├── armoriqdocs.md               # ArmorIQ SDK reference
│   └── AGENTS.md                    # Agent architecture reference (movable)
│
├── .gitignore
└── .env.example
```

## Data Flow

### Happy Path (Successful Trade)
```
1. Analyst → fetches market data → writes recommendation to /output/reports/
2. Risk Manager → reads recommendation → validates against policy → writes delegation token to /output/risk-decisions/
3. Trader → reads delegation token → validates scope/expiry → places order via Alpaca paper API → logs to /output/trade-logs/
```

### Blocked Path (Policy Violation)
```
1. Any Agent → attempts action outside scope
2. ArmorClaw → evaluates intent against policy YAML
3. Policy Engine → deterministic FAIL (ticker not in list, over limit, expired token, etc.)
4. Action → BLOCKED, logged to audit_log and /output/trade-logs/
```

## Security Model

### Layers
1. **ArmorClaw Intent Tokens** — Cryptographic proof of authorized action
2. **Policy YAML** — Declarative, deterministic rules (no LLM interpretation)
3. **Delegation Scoping** — Trader can only act within Risk Manager's approved bounds
4. **File-Level Isolation** — Each agent can only write to its own directories
5. **Network Restriction** — Only `paper-api.alpaca.markets` and `data.alpaca.markets` allowed
6. **Fail-Closed** — If ArmorClaw is unreachable, everything blocks

### Credential Safety
- No credentials in source code
- `.env` is gitignored
- Blocked paths: `~/.openclaw/credentials`, `*.env`, `*.key`, `*.pem`
