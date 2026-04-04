# ShieldTrade — Architecture

## System Overview

ShieldTrade is a multi-agent financial advisory platform where three AI agents collaborate to execute paper trades. The system enforces strict security boundaries using ArmorIQ's intent-based cryptographic verification and a deterministic YAML policy engine.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      OpenClaw Gateway                       │
│                    (Node.js / TypeScript)                    │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Analyst     │  │ Risk Manager │  │    Trader     │     │
│  │   Agent       │  │    Agent     │  │    Agent      │     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │             │
│  ┌──────┴──────────────────┴──────────────────┴──────────┐  │
│  │           ArmorIQ Intent Verification Engine           │  │
│  │       (Policy YAML → Cryptographic Intent Tokens)     │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────┬──────────────────────────────────┘
                           │
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
    ┌────────────┐  ┌────────────┐  ┌────────────┐
    │  Python     │  │  Supabase  │  │  Alpaca    │
    │  Policy &   │  │  Audit DB  │  │  Paper API │
    │  Bridge     │  │  (Postgres)│  │  (sandbox) │
    └────────────┘  └────────────┘  └────────────┘
```

---

## Components

### 1. OpenClaw Gateway

The OpenClaw framework (v2026.3.28) provides the multi-agent orchestration layer. It manages agent lifecycle, message routing, and tool invocation.

- **Port**: 18789 (local mode, loopback only)
- **Authentication**: Token-based gateway auth
- **Configuration**: `config/openclaw.json`

### 2. LLM Proxy Layer

To handle LLM rate limits, a local Express.js proxy server (`scripts/proxy.js`) intercepts OpenClaw's outbound LLM requests and applies key rotation.

- **Port**: 4000
- **Target Model**: `gemini-3-flash-preview`
- **Fallback**: Ollama (set `USE_OLLAMA=true`)

### 3. Agent Definitions

Each agent is defined as an OpenClaw skill in the `skills/` directory:

| Agent | Skill Path | Responsibility |
|---|---|---|
| Analyst | `skills/shieldtrade-analyst/` | Market research, recommendations |
| Risk Manager | `skills/shieldtrade-risk-manager/` | Policy validation, delegation tokens |
| Trader | `skills/shieldtrade-trader/` | Order execution via Alpaca |

### 4. Python Bridge Layer

All external API calls and policy enforcement run in Python, isolated from the Node.js gateway:

| Script | Purpose |
|---|---|
| `scripts/policy_engine.py` | Deterministic YAML policy enforcement |
| `scripts/alpaca_bridge.py` | Alpaca paper trading API client |
| `scripts/supabase_logger.py` | Fire-and-forget audit persistence |

### 5. External Services

| Service | Role | Endpoint |
|---|---|---|
| **Alpaca** | Paper trade execution | `paper-api.alpaca.markets` |
| **Supabase** | Audit log persistence | Project-specific URL |
| **ArmorIQ** | Intent verification | `customer-iap.armoriq.ai` |

---

## Agent Access Matrix

| Agent | Read Access | Write Access |
|---|---|---|
| **Analyst** | `/data/market/*`, `/data/earnings/*` | `/output/reports/*` |
| **Risk Manager** | `/output/reports/*` | `/output/risk-decisions/*` |
| **Trader** | `/output/risk-decisions/*` | `/output/trade-logs/*` |

Each agent's file access is declared in `config/openclaw.json` and enforced by ArmorIQ at the intent token level.

---

## Data Flow

### Happy Path (Trade Approved)

```
1. Analyst → fetches market data from Alpaca
           → writes recommendation to /output/reports/{TICKER}-recommendation.json

2. Risk Manager → reads recommendation
               → validates against config/shieldtrade-policies.yaml
               → issues delegation token to /output/risk-decisions/delegation-{TICKER}.json

3. Trader → reads delegation token
         → validates ArmorIQ signature + TTL
         → executes order via Alpaca paper API
         → logs to /output/trade-logs/ and Supabase
```

### Blocked Path (Policy Violation)

```
1. Any Agent → attempts action outside scope
2. Policy Engine → evaluates against YAML rules
3. Decision → BLOCK (ticker not approved, over limit, expired token, etc.)
4. Result → logged to Supabase audit_log, action is blocked
```

---

## Security Layers

1. **ArmorIQ Intent Tokens** — Cryptographic proof of authorized action
2. **Policy YAML** — Declarative, deterministic rules (no LLM interpretation)
3. **Delegation Scoping** — Trader can only act within Risk Manager's approved bounds
4. **File-Level Isolation** — Each agent can only write to its own directories
5. **Network Restriction** — Only `paper-api.alpaca.markets` and `data.alpaca.markets` allowed
6. **Fail-Closed** — If ArmorIQ is unreachable, all actions block

---

## Credential Safety

- No credentials in source code
- `.env` is gitignored
- Blocked paths: `~/.openclaw/credentials`, `*.env`, `*.key`, `*.pem`
