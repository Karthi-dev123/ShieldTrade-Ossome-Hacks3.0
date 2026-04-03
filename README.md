# ShieldTrade Hackathon Repository

This repository contains the ShieldTrade implementation for the hackathon workflow.

Current completed modules in this repo:
- M2: Alpaca paper-trading bridge
- M3: Policy and enforcement engine

## Repository Structure

```text
config/
	shieldtrade-policies.yaml
scripts/
	alpaca_bridge.py
	policy_engine.py
	m3_selftest.py
output/
	reports/
	risk-decisions/
	trade-logs/
project-docs/
	shieldtrade-team-guide.md
requirements.txt
```

## Prerequisites

- Python 3.10+
- Alpaca paper trading account

## Setup

```bash
python -m pip install -r requirements.txt
```

Create `.env` from `.env.example` and set your real keys.

## M2: Alpaca Bridge

Main script:
- `scripts/alpaca_bridge.py`

Supported commands:

```bash
python scripts/alpaca_bridge.py account
python scripts/alpaca_bridge.py positions
python scripts/alpaca_bridge.py quote AAPL
python scripts/alpaca_bridge.py bars AAPL 1Day 5
python scripts/alpaca_bridge.py order AAPL 1 buy
python scripts/alpaca_bridge.py order AAPL 1 sell
```

Validation sequence (guide-aligned):

```bash
python scripts/alpaca_bridge.py account
python scripts/alpaca_bridge.py quote AAPL
python scripts/alpaca_bridge.py bars AAPL 1Day 5
python scripts/alpaca_bridge.py positions
python scripts/alpaca_bridge.py order AAPL 1 buy
python scripts/alpaca_bridge.py positions
python scripts/alpaca_bridge.py order AAPL 1 sell
python scripts/alpaca_bridge.py quote INVALIDXYZ
python scripts/alpaca_bridge.py order AAPL
```

Notes:
- The bridge returns JSON for both success and error responses.
- `positions` includes pending open orders to make order state visible before fills.
- `order` handles conflicting opposite open orders for the same symbol.

## M3: Policy Engine

Main files:
- `config/shieldtrade-policies.yaml`
- `scripts/policy_engine.py`
- `scripts/m3_selftest.py`

Core commands:

```bash
python scripts/policy_engine.py check-role analyst place_order
python scripts/policy_engine.py check-role trader place_order
python scripts/policy_engine.py check-role risk_manager market_data_fetch
```

Trade validation example:

```bash
python scripts/policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
```

Delegation validation example:

```bash
python scripts/policy_engine.py check-delegation '{"status":"APPROVED","to_agent":"trader","approved_action":{"symbol":"AAPL","max_quantity":10},"expires_at":"2099-12-31T23:59:59Z"}' '{"symbol":"AAPL","qty":10}'
```

Run full policy self-test:

```bash
python scripts/m3_selftest.py
```

Expected final output line:

```text
ALL_PASS=True
```

## Windows PowerShell JSON Tip

If inline JSON quoting is difficult, write JSON to files and pass file contents:

```powershell
'{"symbol":"AAPL","qty":10,"side":"buy","price":150}' | Out-File -Encoding utf8 trade.json
python scripts/policy_engine.py check-trade (Get-Content trade.json -Raw) trader
Remove-Item trade.json
```

## Security

- Never commit `.env` or secret keys.
- Rotate any key that was ever shared in logs or chat.
