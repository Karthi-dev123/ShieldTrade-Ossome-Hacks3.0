# ShieldTrade - M4 Phase Guide (Agent Skills and Demo)

This document captures all M4 responsibilities from the ShieldTrade team guide.

## M4 Scope

- Owner: M4 (Agent Skills and Demo Lead)
- Branch: feature/agent-skills
- Core responsibility: define safe behavior for all three agents, drive integration tests, and prepare demo assets

## Dependencies

- M1 must complete OpenClaw and gateway setup before end-to-end tests
- M2 must provide Alpaca bridge commands used by Analyst and Trader
- M3 must provide policy engine checks used by Risk Manager and Trader

## Phase 1 Deliverables (Skills and Orchestration)

### 1) Create branch

```bash
git checkout main
git pull origin main
git checkout -b feature/agent-skills
```

### 2) Create all three SKILL files

- skills/shieldtrade-analyst/SKILL.md
- skills/shieldtrade-risk-manager/SKILL.md
- skills/shieldtrade-trader/SKILL.md

### 3) Analyst skill must include

- Valid YAML frontmatter (name, description)
- Allowed tools:
  - python3 scripts/alpaca_bridge.py quote SYMBOL
  - python3 scripts/alpaca_bridge.py bars SYMBOL 1Day 30
- Output contract:
  - write recommendation JSON to /output/reports/SYMBOL-recommendation.json
- Hard restrictions:
  - cannot place orders
  - cannot access account/positions
  - cannot operate outside approved symbols

### 4) Risk Manager skill must include

- Valid YAML frontmatter (name, description)
- Allowed tools:
  - python3 scripts/alpaca_bridge.py account
  - python3 scripts/alpaca_bridge.py positions
  - python3 scripts/policy_engine.py check-trade '{...}' trader
- Output contract:
  - write approval or rejection to /output/risk-decisions/
  - approval files include delegation token with expiry
- Hard restrictions:
  - cannot place orders
  - cannot fetch quote/bars
  - cannot approve if any policy check fails

### 5) Trader skill must include

- Valid YAML frontmatter (name, description)
- Allowed tools:
  - read delegation file from /output/risk-decisions/
  - python3 scripts/policy_engine.py check-delegation 'DELEGATION_JSON' 'REQUEST_JSON'
  - python3 scripts/alpaca_bridge.py order SYMBOL QTY SIDE
  - python3 scripts/alpaca_bridge.py positions
- Output contract:
  - write execution log to /output/trade-logs/trade-SYMBOL-TIMESTAMP.json
- Hard restrictions:
  - cannot trade without valid delegation
  - cannot exceed delegated quantity
  - cannot trade wrong symbol
  - cannot trade with expired delegation
  - cannot fetch quote/bars

### 6) Decision logging format

Use consistent JSON logging across agents:

- analyst report in /output/reports/
- risk decision in /output/risk-decisions/
- trader execution log in /output/trade-logs/

Each file should include:

- agent
- symbol
- action (if applicable)
- quantity (if applicable)
- status
- reasoning/check results
- timestamp (ISO-8601 UTC)

### 7) Commit and push M4 work

```bash
git add skills/ README.md README-M4.md
git commit -m "feat(skills): add all three SKILL.md files and M4 guide"
git push origin feature/agent-skills
```

## M4 Phase 1 Checkpoint (Pass Criteria)

- [ ] All 3 SKILL.md files exist and are complete
- [ ] Each skill has valid YAML frontmatter
- [ ] Allowed tools and forbidden actions are explicit
- [ ] Workflows are step-by-step and deterministic
- [ ] Decision log schema is consistent across all agents
- [ ] README documentation is accurate

## Phase 1 Sync and Merge

After PR approval:

```bash
git checkout main
git pull origin main
git merge feature/agent-skills
git push origin main
```

## Phase 2 (M4 Drives Integration Tests)

M4 runs the operator flow in OpenClaw while M2 and M3 validate scripts.

### A) Analyst test

Prompt:

```
/shieldtrade-analyst Research AAPL and tell me if I should buy
```

Verify:

- quote and bars commands are used
- report file appears in /output/reports/
- no order placement attempt

### B) Risk Manager test

Prompt:

```
/shieldtrade-risk-manager Validate the latest AAPL recommendation
```

Verify:

- recommendation is read
- check-trade executes
- account is checked
- delegation file appears in /output/risk-decisions/
- no order placement attempt

### C) Trader test

Prompt:

```
/shieldtrade-trader Execute the approved AAPL trade
```

Verify:

- delegation is read and validated
- check-delegation executes
- order command is called
- execution log appears in /output/trade-logs/
- no quote/bars usage

### D) Required blocked scenarios

- Analyst asked to buy directly -> blocked
- Trader asked to buy without delegation -> blocked
- Risk Manager validates unapproved ticker -> blocked
- Trader attempts quantity above delegation -> blocked

## Phase 2 Checkpoint (Pass Criteria)

- [ ] Full pipeline succeeds: Analyst -> Risk Manager -> Trader
- [ ] At least 3 blocked scenarios demonstrated
- [ ] Logs exist for each stage
- [ ] Gateway shows intent enforcement evidence

## Phase 3 (M4 Demo and Submission)

### M4 deliverables

- Record 3-minute demo video
- Show one full happy-path execution
- Show 2-3 blocked actions
- Present architecture and enforcement rationale

### Suggested 3-minute structure

- 0:00-0:30: architecture overview
- 0:30-0:45: policy model snapshot
- 0:45-1:30: live pipeline run
- 1:30-2:15: blocked scenario proofs
- 2:15-2:45: gateway intent logs
- 2:45-3:00: summary and outcomes

## Troubleshooting Notes for M4

- Skill not triggering: verify frontmatter and skill naming
- Agent violates scope: strengthen explicit NEVER rules
- Missing outputs: verify output directory paths and file naming
- Failed trade validation: inspect policy_engine.py check output before retry

## Ready-to-Use M4 Checklist

- [ ] Branch feature/agent-skills created from latest main
- [ ] 3 skill files created and reviewed
- [ ] Commit pushed and PR opened
- [ ] Merged to main after review
- [ ] Integration tests run with team
- [ ] Demo video recorded and uploaded
