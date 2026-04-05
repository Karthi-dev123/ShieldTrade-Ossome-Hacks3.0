# ShieldTrade Demo Script (2-Minute Judge Version)

## What you're seeing

ShieldTrade is a multi-agent financial advisory system where every trade action is bounded by deterministic policy — not prompt instructions. Three agents (Analyst, Risk Manager, Trader) hand off through signed JSON artifacts and a policy engine that fails closed.

---

## Pre-flight (30 seconds)

```bash
# 1. Install dependencies (one-time)
pip install -r requirements.txt
npm install

# 2. Start services (Ollama proxy + OpenClaw gateway)
python scripts/start-all.py

# 3. Verify proxy is up
curl http://localhost:4000/v1/models
```

---

## Segment 1: Happy Path — Allowed Trade (30 seconds)

Run the full Analyst → Risk Manager → Trader pipeline in dry-run mode (no Alpaca account needed):

```bash
python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run
```

**Expected output (truncated):**
```json
{
  "ok": true,
  "dry_run": true,
  "report_path": "output/reports/AAPL-recommendation.json",
  "delegation_path": "output/risk-decisions/delegation-AAPL-del_aapl_<id>.json",
  "execution_log_path": "output/trade-logs/execution-AAPL-<ts>.json",
  "risk_policy": { "decision": "ALLOW", ... },
  "trader_policy": { "decision": "ALLOW", ... }
}
```

Show the artifacts:
```bash
cat output/reports/AAPL-recommendation.json
cat output/risk-decisions/delegation-AAPL-*.json
cat output/trade-logs/execution-AAPL-*.json
```

---

## Segment 2: Policy Enforcement — Blocked Trades (30 seconds)

**Block 1: Unapproved ticker (TSLA not in allow-list)**
```bash
python scripts/orchestrate_pipeline.py TSLA --shares 5 --assume-price 100 --dry-run
```
Expected: `"ok": false, "stopped_at": "risk"` — rejection JSON written to `output/risk-decisions/`.

**Block 2: Oversized order (60 shares × $100 = $6000 > $2000 per-order cap)**
```bash
python scripts/orchestrate_pipeline.py AAPL --shares 60 --assume-price 100 --dry-run
```
Expected: `"ok": false, "stopped_at": "risk"` with `order_size` check FAIL.

---

## Segment 3: Security Enforcement — Prompt Injection & Data Exfiltration (45 seconds)

These scenarios show that the policy engine blocks the attacks documented in the PS: prompt injection via untrusted content, unauthorized tool execution, credential/data exfiltration, and scope escalation. Each check fires deterministically — no LLM reasoning involved.

### 3a — Prompt injection → denied tool call

**Attack:** A malicious payload embedded in a market data feed tells the analyst agent to execute a shell command.

```bash
python scripts/policy_engine.py check-role analyst shell
```

Expected output:
```json
{
  "check": "role_permission",
  "result": "FAIL",
  "detail": "Agent 'analyst' is denied tool 'shell'",
  "enforcement": "autonomous",
  "policy_ref": "agent_roles.analyst.denied_tools"
}
```

`policy_ref` points to the exact YAML section that declared the rule — `agent_roles.analyst.denied_tools` in `config/shieldtrade-policies.yaml`. The block is not hardcoded; change the YAML and the behavior changes. `enforcement: autonomous` confirms no human approval step exists.

### 3b — Cross-agent scope escalation

**Attack:** A compromised trader agent tries to write a research report (analyst-only tool), escalating its own scope.

```bash
python scripts/policy_engine.py check-role trader write_report
```

Expected output:
```json
{
  "check": "role_permission",
  "result": "FAIL",
  "detail": "Agent 'trader' is denied tool 'write_report'",
  "enforcement": "autonomous",
  "policy_ref": "agent_roles.trader.denied_tools"
}
```

### 3c — Data exfiltration via unauthorized API endpoint

**Attack:** An injected prompt silently re-routes a paper order from `paper-api.alpaca.markets` to `api.alpaca.markets` (the live money endpoint).

```bash
python scripts/policy_engine.py check-data-safety api.alpaca.markets
```

Expected output:
```json
{
  "check": "data_safety",
  "result": "FAIL",
  "detail": "Domain 'api.alpaca.markets' not in allowed list — exfiltration blocked",
  "enforcement": "autonomous",
  "policy_ref": "data_safety.no_external_exfiltration.allowed_domains"
}
```

`policy_ref` traces the block to `data_safety.no_external_exfiltration.allowed_domains` in the YAML. Only `paper-api.alpaca.markets` and `data.alpaca.markets` are in the allow-list — every other host is rejected (fail-closed). No code change needed to add a domain; edit the YAML.

### 3d — PII injection in tool arguments

**Attack:** A compromised market data feed embeds a Social Security Number in the analyst's tool query, attempting to exfiltrate account data.

```bash
python scripts/policy_engine.py check-pii "Fetch earnings for account holder 123-45-6789"
```

Expected output:
```json
{
  "check": "pii_in_tool_args",
  "result": "FAIL",
  "detail": "PII detected in tool arguments (matched pattern: '\\d{3}-\\d{2}-\\d{4}') — call blocked",
  "enforcement": "autonomous",
  "policy_ref": "data_safety.no_pii_in_tool_args.patterns"
}
```

PII regex patterns (SSN `\d{3}-\d{2}-\d{4}`, credit card `\d{16}`, 9-digit account `\d{9}`) are declared entirely in `config/shieldtrade-policies.yaml` under `data_safety.no_pii_in_tool_args.patterns`. Add a new pattern to the YAML — no code change required. The check fires automatically on every `validate_trade()` call that includes `tool_args`.

### 3e — Full end-to-end: exfiltration attempt inside validate_trade

Shows that the domain check fires even inside a complete trade request:

```bash
python scripts/policy_engine.py check-trade trader place_order AAPL 5 500 api.alpaca.markets
```

Expected: `"decision": "BLOCK"` with `data_safety` check showing `"result": "FAIL"` in the `checks` array.

---

## Segment 4: Test Suite — Reproducible Evidence (30 seconds)

```bash
python -m pytest tests -q
```

Expected: **50 passed** — covers:
- Policy unit tests (ticker, order size, daily limit, delegation TTL, YAML ceiling, earnings blackout, ET timezone)
- Integration tests (happy path, unapproved ticker, oversized order, expired delegation, quantity > cap, missing delegation, live order, delegation issuance caps)
- CLI contract tests (alpaca_bridge input validation)
- ArmorIQ stub tests (issue, verify, tamper detection, missing key)
- **Security scenario tests** (prompt injection shell call, cross-agent scope escalation, data exfiltration domain block, PII in tool args, end-to-end exfiltration via validate_trade)

---

## Key Architecture Points (for Q&A)

| Point | Evidence |
|-------|----------|
| Fail-closed policy | All checks must PASS; any FAIL → BLOCK (see `policy_engine.validate_trade()`) |
| Delegation cap enforcement | `build_delegation()` caps at YAML ceiling; `check_delegation()` verifies token caps + request vs caps + TTL |
| Earnings blackout | `check_earnings_blackout()` reads static event list; fails closed if list missing while enabled |
| ArmorIQ intent tokens | Every paper order carries an HMAC-SHA256 signed token from `armoriq_stub.py`; wired into `cmd_order()` |
| Paper trading only | `TradingClient(paper=True)` hardcoded in `alpaca_bridge.py` |
| No cloud LLM dependency | Inference via local Ollama; pipeline runs fully offline |
| Artifact-driven handoffs | Each stage writes/reads JSON; no direct function calls between agents |
| Atomic daily spend (ET) | Filelock-guarded `daily-spend.json`; bucket keyed by `America/New_York` date; only recorded on ALLOW |
| Prompt injection defense | `check_role_permission()` blocks denied tools regardless of LLM output; `check_pii_in_tool_args()` scans tool arguments for PII patterns from YAML |
| Data exfiltration defense | `check_data_safety()` enforces domain allow-list (fail-closed); live API domain and unknown hosts are blocked |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Port 4000 not responding | `python scripts/start-all.py` (reuses running processes) |
| `openclaw: command not found` | `npm install -g @openclaw/cli` or use the npm script |
| `OLLAMA_BASE_URL` not set | Copy `.env.example` → `.env` and set values |
| Market hours block (live mode) | Expected; run between 09:30–16:00 ET Mon–Fri or use `--dry-run` |
| Alpaca keys missing (live mode) | Set `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env` |
