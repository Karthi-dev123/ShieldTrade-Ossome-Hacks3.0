#!/bin/bash
echo "Starting ShieldTrade E2E Evaluator..."

if [ ! -f ".env" ]; then
    echo "Error: .env file missing! Please copy the credentials privately."
    exit 1
fi

venv/bin/python scripts/run_multi_agent_trade.py
