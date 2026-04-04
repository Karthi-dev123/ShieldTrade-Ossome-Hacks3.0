#!/bin/bash
set -a
source .env
set +a
export GOOGLE_API_KEY=${GEMINI_API_KEY3:-${GEMINI_API_KEY2:-$GEMINI_API_KEY}}
export OPENCLAW_CONFIG_PATH="/home/naithick/hackathons/ossome-hacks/config/openclaw.json"
venv/bin/python scripts/demo_blocked_trade.py
