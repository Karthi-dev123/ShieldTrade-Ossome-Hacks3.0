# CLAUDE.md

## ShieldTrade Operating Context (Read First)

ShieldTrade is a multi-agent financial advisory system built on OpenClaw with deterministic policy enforcement and Alpaca paper-trading execution.

Primary objective:
- Demonstrate safe autonomous finance workflows where every action is bounded by explicit policy and delegation, not only prompt instructions.

Current runtime architecture:
- Local LLM backend: Ollama (no cloud dependency for inference)
- Local proxy: scripts/proxy.js (OpenAI-compatible surface)
- Gateway: OpenClaw local gateway using config/openclaw.json
- Policy layer: scripts/policy_engine.py + config/shieldtrade-policies.yaml
- Trading layer: scripts/alpaca_bridge.py (paper account only)
- Audit/logging: scripts/supabase_logger.py + output artifacts

## Current Source of Truth

Use these files as canonical references:
- **Handoff schemas + CLI contracts: docs/contracts.md**
- Runtime config: config/openclaw.json
- Policy model: config/shieldtrade-policies.yaml
- LLM proxy: scripts/proxy.js
- Startup orchestration: scripts/start-all.py
- Trading bridge: scripts/alpaca_bridge.py
- Policy enforcement: scripts/policy_engine.py
- **E2E pipeline (artifacts): scripts/orchestrate_pipeline.py**
- Agent skills:
  - skills/shieldtrade-analyst/SKILL.md
  - skills/shieldtrade-risk-manager/SKILL.md
  - skills/shieldtrade-trader/SKILL.md
- Tests:
  - tests/test_policy_engine.py
  - tests/test_m2_policy_guards.py

Non-canonical historical references:
- project-docs/shieldtrade-team-guide.md (old baseline, partially outdated)
- project-docs/shieldtrade-solution-proposal.md (vision + narrative)

## Implementation status (sync with code)

Updated as milestones land; compare to Phase 1–5 in this file.

| Area | Status | Notes |
|------|--------|--------|
| **Contracts / schema freeze** | Done | `docs/contracts.md` matches `policy_engine.py` + `alpaca_bridge.py` CLI and delegation shape |
| **Skills vs CLI** | Done | `skills/shieldtrade-*/SKILL.md` aligned to `docs/contracts.md` (CLI + JSON shapes) |
| **E2E orchestrator** | Done (MVP) | `python scripts/orchestrate_pipeline.py …` writes report → delegation → execution log; use `--dry-run` without Alpaca order; risk-stage policy check does not record daily spend (only trader `validate_trade` does when live) |
| **Delegation vs order caps** | Done | `check_delegation()` enforces shares ≤ max_shares and amount_usd ≤ max_usd + YAML ceiling; `build_delegation()` caps at issuance against `max_shares_per_delegation` / `max_usd_per_delegation` from YAML |
| **Earnings blackout** | Done | `check_earnings_blackout()` reads static event list from YAML; fail-closed when list missing/malformed; wired into `validate_trade()`; `enabled: false` by default |
| **Daily spend timezone** | Done | `_today_key()` uses `America/New_York` — daily spend bucket matches ET trading day |
| **ArmorIQ intent tokens** | Done | `scripts/armoriq_stub.py` issues HMAC-SHA256 signed tokens; `cmd_order()` attaches token to every paper order; no cloud dependency |
| **Proxy streaming sentinel** | Done | `proxy.js` injects `data: [DONE]\n\n` when Ollama stream closes without it — fixes OpenClaw agent "stream ended" errors |
| **Tests** | Done (50 tests) | `test_policy_engine.py` (23 unit), `test_orchestrate_pipeline.py` (9 integration), `test_m2_policy_guards.py` (3 CLI contract), `test_armoriq_stub.py` (7 stub unit), `test_security_scenarios.py` (8 security: prompt injection, scope escalation, data exfiltration ×2, PII detection ×3, end-to-end) |
| **Security enforcement (GAP 9)** | Done | `check_pii_in_tool_args()` enforces YAML PII patterns; `check_data_safety()` updated with clearer messaging; `check-pii` + `check-data-safety` CLI commands added; security segment added to `docs/demo-script.md` |
| **Demo docs** | Done | `docs/demo-script.md` — 2-minute judge script with commands, expected outputs, and troubleshooting |
| **Troubleshooting** | Done | `docs/troubleshooting.md` — startup, gateway token, policy blocks, daily spend, test failures, health check sequence |
| **README** | Done | Quick-start updated to match actual commands (`start-all.py`, `orchestrate_pipeline.py`, `pytest`) |

## Environment and Model Assumptions

Expected local .env values:
- OLLAMA_BASE_URL=http://localhost:11434
- OLLAMA_MODEL=qwen3:30b-a3b
- OLLAMA_API_KEY=ollama

Required runtime ports:
- 4000 -> local proxy
- 18789 -> OpenClaw gateway

Known-good health checks:
- curl http://localhost:4000/v1/models
- curl -X POST http://localhost:4000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"local-ollama","messages":[{"role":"user","content":"Reply with OK"}],"stream":false}'
- OPENCLAW_CONFIG_PATH="$PWD/config/openclaw.json" OPENCLAW_GATEWAY_TOKEN="<token-from-config>" openclaw health

## What Is Already Working

- Local Ollama integration through the proxy is active.
- Proxy /v1/models and /v1/chat/completions respond.
- OpenClaw gateway starts in local mode with token auth.
- start-all script reuses existing running services on ports 4000 and 18789.
- Policy engine and Alpaca bridge exist with test coverage.

## Known Gaps and Risks

- Agent skills reference `docs/contracts.md`; if CLIs change, update both contracts and SKILL.md together.
- Deterministic pipeline exists via `scripts/orchestrate_pipeline.py`; prefer it over any legacy shell scripts for judge-style verification.
- Earnings blackout events list in `shieldtrade-policies.yaml` is static (hardcoded dates). It is not automatically updated from a live earnings calendar. Update the list manually each quarter or wire a fetch job.
- `openclaw agent` streaming is now guarded by the `[DONE]` sentinel in `proxy.js`, but very long LLM responses (>Ollama's context window) may still truncate silently — test with short prompts first.

## Hard Product Constraints

- Paper trading only. Never use live Alpaca endpoints.
- Enforce allow-list tickers and order limits from policy.
- Trader must never execute without valid delegation token.
- Delegation must enforce ticker, quantity, max_usd, issuer, target, expiry.
- All enforcement should fail closed.
- Keep output machine-readable JSON where possible.

## Deliverables (Target State)

Core deliverables:
- D1: Contract-aligned multi-agent workflow (analyst/risk/trader) with deterministic handoffs.
- D2: Real executable E2E pipeline (not only mocked terminal narrative).
- D3: Robust enforcement checks for role, policy, delegation, and data safety.
- D4: Reliable demo commands with clear expected outputs.
- D5: Updated docs that exactly match running behavior.

Evidence deliverables:
- E1: Passing unit + integration tests for happy path and blocked scenarios.
- E2: Artifact files generated by each stage:
  - output/reports/*.json
  - output/risk-decisions/*.json
  - output/trade-logs/*.json
- E3: Logs that show ALLOW/BLOCK reasoning deterministically.

## Recommended Implementation Plan

### Phase 1: Contract Freeze and Alignment

Goals:
- Define one canonical schema for:
  - analyst recommendation
  - risk delegation
  - trade execution log
- Align skills and CLI usage to this schema.

Tasks:
- Add docs/contracts.md with field-level schemas and examples. **Done** (`docs/contracts.md`).
- Update all SKILL.md files to use current script command signatures. **Done**
- Ensure policy_engine check-trade/check-delegation signatures are explicit and stable. **Documented in contracts.md** (code unchanged).

Exit criteria:
- No ambiguity in field naming or command usage.
- Skills and scripts reference same contracts. **Met** for current code (see `docs/contracts.md`).

### Phase 2: Deterministic Workflow Implementation

Goals:
- Build real orchestration path with machine-readable handoffs.

Tasks:
- Create script runners (or one orchestrator) for:
  - analyst stage -> writes recommendation artifact
  - risk stage -> validates and writes delegation or rejection
  - trader stage -> validates delegation and executes order/logs
- Guarantee downstream stage reads only upstream artifacts.

**MVP:** `scripts/orchestrate_pipeline.py` (see Command Playbook). Risk uses in-process `validate_trade` with `record_spend_if_allow=False`; trader records spend on `ALLOW` unless `--dry-run`.

Exit criteria:
- One command executes true pipeline with artifacts generated in output directories. **Met** for `--dry-run` and live (with Alpaca env).
- Blocked decisions stop downstream actions. **Met** (rejection JSON under `output/risk-decisions/`).

### Phase 3: Enforcement Hardening

Goals:
- Make bypasses impossible through script-layer checks.

Tasks:
- Add explicit preflight checks in trader execution.
- Validate delegation issuer/target/ticker/quantity/max_usd/expiry before order.
- Ensure daily spend and order limits are atomically enforced.

Exit criteria:
- All known abuse paths are blocked with deterministic reasons.

### Phase 4: Test and Demo Reliability

Goals:
- Make behavior reproducible for judges.

Tasks:
- Add integration tests for:
  - happy path
  - unapproved ticker
  - oversized order
  - expired delegation
  - quantity > delegated max
  - no delegation token
- Replace mocked demo script content with real command-backed checks where feasible.

Exit criteria:
- Tests pass and demo outputs are reproducible.

### Phase 5: Documentation and Presentation Sync

Goals:
- Ensure docs reflect the exact runtime truth.

Tasks:
- Update README quick-start for local Ollama + real E2E path.
- Add docs/demo-script.md with 2-minute and 3-minute judge scripts.
- Add docs/troubleshooting.md for common startup and gateway token issues.

Exit criteria:
- New team member can run and verify in minutes without guesswork.

## Suggested Immediate Next Tasks (Priority Order)

- P0: ~~Create and agree contracts.md (schema freeze)~~ → **Done:** `docs/contracts.md`
- P0: ~~Align SKILL.md commands with `docs/contracts.md` and actual CLIs~~ → **Done**
- P1: ~~Implement real orchestration script for analyst/risk/trader handoff~~ → **MVP done:** `scripts/orchestrate_pipeline.py`
- P1: ~~Add integration tests for blocked/allow scenarios~~ → **Done:** 9 integration tests in `tests/test_orchestrate_pipeline.py`
- P1: ~~Enforce delegation caps in policy engine (Phase 3 hardening)~~ → **Done:** `check_delegation()` enforces YAML ceiling + request caps; `build_delegation()` caps at issuance
- P1: ~~Improve openclaw agent streaming compatibility~~ → **Done:** `proxy.js` injects `data: [DONE]\n\n` sentinel
- P1: ~~Earnings blackout check~~ → **Done:** `check_earnings_blackout()` in `policy_engine.py`
- P1: ~~Daily spend timezone fix~~ → **Done:** `_today_key()` uses `America/New_York`
- P1: ~~ArmorIQ intent token stub~~ → **Done:** `scripts/armoriq_stub.py` + wired into `cmd_order()`
- P2: ~~Update README and demo docs to match actual behavior~~ → **Done:** `README.md` + `docs/demo-script.md` + `docs/troubleshooting.md`

## Definition of Done

A change is done only if:
- It has tests (or explicit rationale why not).
- It updates docs when behavior changes.
- It preserves fail-closed safety behavior.
- It is reproducible with explicit commands.
- It does not rely on hidden local assumptions.

## Command Playbook (Quick)

Start services:
- python scripts/start-all.py

Verify model and inference:
- curl http://localhost:4000/v1/models
- curl -X POST http://localhost:4000/v1/chat/completions -H "Content-Type: application/json" -d '{"model":"local-ollama","messages":[{"role":"user","content":"Reply with OK"}],"stream":false}'

Verify gateway:
- OPENCLAW_CONFIG_PATH="$PWD/config/openclaw.json" OPENCLAW_GATEWAY_TOKEN="<token-from-config>" openclaw health

Run tests:
- python -m pytest tests -q

Run deterministic pipeline (no Alpaca order; uses assumed price; good for CI / quick check):
- python scripts/orchestrate_pipeline.py AAPL --shares 5 --assume-price 100 --dry-run

Live paper order (requires Alpaca + ARMORIQ env per `alpaca_bridge.py`; respects market-hours policy):
- python scripts/orchestrate_pipeline.py AAPL --shares 5

## Notes for Claude Code

When editing:
- Prefer minimal, contract-driven changes.
- Keep JSON outputs stable for downstream scripts/tests.
- Preserve security-first defaults (deny by default).
- Do not introduce cloud LLM dependencies unless explicitly requested.
- Treat project-docs as guidance; prefer runtime files as source of truth.
