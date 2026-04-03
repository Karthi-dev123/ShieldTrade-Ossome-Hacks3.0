# ShieldTrade — M3 Phase (Policy & Enforcement)

This branch contains the complete M3 deliverable for the ArmorIQ x OpenClaw hackathon: a declarative policy model and a deterministic enforcement engine for trade validation.

## Branch Scope

- Phase owner: M3 (Policy & Enforcement)
- Branch: feature/policy-engine
- Purpose: enforce financial constraints in code, not prompt instructions

## What Is Implemented

1. Declarative policy model in YAML
	- Defines agent role permissions
	- Defines trading constraints (ticker, size, daily cap, market hours)
	- Defines data safety constraints (PII, credential access, exfiltration)
	- Defines delegation constraints (approval, expiry, quantity/symbol match)

2. Policy enforcement engine in Python
	- Loads YAML policy at runtime
	- Evaluates trade requests and returns structured PASS/FAIL checks
	- Evaluates role-tool permission checks
	- Evaluates delegation token checks
	- Supports CLI commands required by the team guide

3. M3 validation suite
	- Includes a self-test script for all required test scenarios
	- Verifies positive and negative cases for trade, role, and delegation checks

## Files Added for M3

- config/shieldtrade-policies.yaml
- scripts/policy_engine.py
- scripts/m3_selftest.py
- scripts/alpaca_realtime_check.py
- requirements.txt

## Installation

From this branch folder:

```bash
# ShieldTrade — M3 Phase (Policy & Enforcement)

This branch contains the complete M3 deliverable for the hackathon policy layer and Phase 3 integration checks.

## Branch Scope

- Phase owner: M3 (Policy & Enforcement)
- Branch: feature/policy-engine
- Goal: deterministic policy checks, audit logging, and blocked-path validation

## Repository Structure (M3)

```text
config/
	shieldtrade-policies.yaml
scripts/
	policy_engine.py
	m3_selftest.py
	alpaca_realtime_check.py
	gateway_validation.py
	supabase_logger.py
tests/
	test_policy_engine.py
output/
	reports/
		gateway-validation.json
	risk-decisions/
	trade-logs/
requirements.txt
```

## Installation

```bash
python -m pip install -r requirements.txt
```

## Environment Setup

Create `.env` in repository root:

```dotenv
GROQ_API_KEY=...
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ARMORIQ_API_KEY=...
GEMINI_API_KEY1=...
GEMINI_API_KEY2=...
GEMINI_API_KEY3=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
ANTHROPIC_API_KEY=...
```

## Policy Engine Commands

```bash
python scripts/policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
python scripts/policy_engine.py check-role analyst place_order
python scripts/policy_engine.py check-role trader place_order
python scripts/policy_engine.py check-delegation '{"status":"APPROVED","to_agent":"trader","approved_action":{"symbol":"AAPL","max_quantity":10},"expires_at":"2099-12-31T23:59:59Z"}' '{"symbol":"AAPL","qty":10}'
python scripts/policy_engine.py validate-all '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
```

## Supabase Audit DB Integration

- `scripts/policy_engine.py` writes audit events to Supabase table `audit_log`.
- `scripts/supabase_logger.py` is a non-blocking helper used by policy command paths.
- Logging failure does not block policy enforcement decisions.

## Policy Testing

Run policy tests:

```bash
python -m pytest tests -q
```

Included coverage:
- blocked `check_share_count` scenario (`qty` over limit)
- boundary `check_share_count` scenario (`qty` at limit)

## Gateway Validation (Phase 3)

Run blocked-path validation:

```bash
python scripts/gateway_validation.py
```

This executes 4 blocked CLI scenarios:
- unapproved ticker
- over order-size limit
- over share-count limit
- PII payload

Validation output:
- `output/reports/gateway-validation.json`
- includes `alpaca_drop_confirmed` evidence

## M3 Self-Test

```bash
python scripts/m3_selftest.py
```

Expected final line:

```text
ALL_PASS=True
```

## Security

- Never commit `.env`.
- Rotate any key that has been exposed in logs or chat.
