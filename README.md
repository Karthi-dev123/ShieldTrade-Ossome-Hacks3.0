# ShieldTrade Hackathon Repository

This repository contains the ShieldTrade implementation for the hackathon workflow.

Current completed modules in this repo:
- M2: Alpaca paper-trading bridge

## Repository Structure

```text
scripts/
	alpaca_bridge.py
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

## Security

- Never commit `.env` or secret keys.
- Rotate any key that was ever shared in logs or chat.
