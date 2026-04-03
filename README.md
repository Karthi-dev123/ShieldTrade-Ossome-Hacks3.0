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
- requirements.txt

## Installation

From this branch folder:

```bash
python -m pip install -r requirements.txt
```

## CLI Usage

### 1) Validate a trade

```bash
python scripts/policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
```

### 2) Check role permission

```bash
python scripts/policy_engine.py check-role analyst place_order
python scripts/policy_engine.py check-role trader place_order
```

### 3) Check delegation constraints

```bash
python scripts/policy_engine.py check-delegation \
  '{"status":"APPROVED","to_agent":"trader","approved_action":{"symbol":"AAPL","max_quantity":10},"expires_at":"2099-12-31T23:59:59Z"}' \
  '{"symbol":"AAPL","qty":10}'
```

### 4) Full policy validation

```bash
python scripts/policy_engine.py validate-all '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
```

## Run M3 Test Suite

```bash
python scripts/m3_selftest.py
```

Expected final line:

```text
ALL_PASS=True
```

## Enforcement Outcomes

- ALLOW only when all checks pass
- BLOCK when any check fails
- Structured JSON output includes:
  - decision (ALLOW/BLOCK)
  - all_passed
  - failed_checks
  - per-check pass/fail details

## Notes

- The market-hours check depends on timezone data.
- requirements.txt includes tzdata for Windows/Python environments where IANA timezone data is missing.
- This branch is intentionally isolated to M3 scope and does not include M1/M2/M4 integration work.
