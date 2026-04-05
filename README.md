# ShieldTrade - Ossome Hacks 3.0 Submission

ShieldTrade is a highly secure multi-agent financial advisory system operating on the OpenClaw framework. It features deterministic declarative policies, AI-driven advisory workflows, and completely secure trading intent execution via ArmorClaw and Alpaca bridges.

## Features at a Glance

- **Multi-Agent Advisory**: Specialized roles (Analyst, Risk Manager, Trader) collaborating seamlessly.
- **Deterministic Policy Engine**: Highly secure, declarative YAML-based trading limits and rules.
- **Auditable & Traceable**: Full integration with Postgres via Supabase.
- **Zero-Trust Trading**: Forced execution constraints with ArmorClaw API intent tokens and robust validations.

---

## Quick Start / Evaluation Guide

### 1. Prerequisites
- Python 3.10+
- A valid `.env` file at the root of the project (copy `.env.example` and insert credentials).
- A running local Ollama server with the model from `OLLAMA_MODEL` pulled (for OpenClaw agent commands; not required for the deterministic pipeline below).

> **Note on Local LLM Routing**: OpenClaw requests are proxied through `scripts/proxy.js` on port 4000 and forwarded to your local Ollama server (`OLLAMA_BASE_URL`).

### 2. Install dependencies

```bash
pip install -r requirements.txt
npm install          # for scripts/proxy.js
```

### 3. Start background services (Ollama proxy + OpenClaw gateway)

```bash
python scripts/start-all.py
```

### 4. Run the deterministic E2E pipeline (no Alpaca account needed)

This executes the full Analyst → Risk Manager → Trader pipeline and writes JSON artifacts under `output/`.

```bash
python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run
```

Expected output: `"ok": true, "dry_run": true` with artifact paths for report, delegation token, and execution log.

### 5. Verify policy enforcement

```bash
# Should be blocked: TSLA is not in the approved-ticker allow-list
python scripts/orchestrate_pipeline.py TSLA --shares 5 --assume-price 100 --dry-run

# Should be blocked: $6000 notional exceeds $2000 per-order cap
python scripts/orchestrate_pipeline.py AAPL --shares 60 --assume-price 100 --dry-run
```

### 6. Run the test suite

```bash
python -m pytest tests -q
```

All 41 tests should pass (23 unit + 9 integration + 3 CLI contract + 7 ArmorIQ stub).

### 7. Live paper order (requires Alpaca credentials in `.env`)

```bash
python scripts/orchestrate_pipeline.py AAPL --shares 5
```

Respects market-hours policy; will block outside 09:30–16:00 ET on weekdays.

---

---

## Enforcement Architecture

### How enforcement works (and why it's local, not a cloud plugin)

Policy enforcement in ShieldTrade is handled by the **local Python stack**, not an OpenClaw cloud plugin. This is an intentional design decision:

| Component | Role |
|-----------|------|
| `config/shieldtrade-policies.yaml` | Single source of truth — all limits, tickers, roles, and delegation caps declared declaratively |
| `scripts/policy_engine.py` | Deterministic enforcement engine — validates every `TradeIntent` against `ShieldTradePolicy` (both are Pydantic-typed models) |
| `scripts/armoriq_stub.py` | Issues HMAC-SHA256 signed intent tokens; attached to every paper order |
| `scripts/alpaca_bridge.py` | Paper-trading execution only; no real money |

**Why not an OpenClaw plugin?** `config/openclaw.json` lists only the `google` plugin — there is no ArmorIQ cloud plugin entry. This is intentional: running enforcement in-process means (a) no cloud dependency, (b) every check is reproducible from the YAML file alone, and (c) the enforcement path is fully auditable without an external API call.

### Structured intent and policy models

The PS requires "structured and interpretable" intent and policy models — not simple if-else checks. ShieldTrade satisfies this with Pydantic:

- **`TradeIntent`** — Pydantic model capturing agent, tool, ticker, size, domain, and delegation for every request
- **`DelegationToken`** — Pydantic model for scoped authority tokens (issuer, target, ticker, caps, TTL)
- **`ShieldTradePolicy`** — Pydantic schema for the full YAML policy document; YAML is validated against this schema at startup

See `scripts/policy_engine.py` (top of file) for the full model definitions.

---

## Technical Guarantee
This repository has been sanitized and follows strict security and architecture guidelines. All sensitive keys, build caching, `__pycache__`, `node_modules`, and environment configurations have been permanently excluded from tracking to ensure a zero-leak footprint.

All architectural rules (e.g. `America/New_York` timezone checks) apply dynamically and deterministically.
