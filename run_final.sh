#!/bin/bash
set -a
source .env
set +a
export GOOGLE_API_KEY=${GEMINI_API_KEY2:-$GEMINI_API_KEY}

# Force daemon and CLI to use the exact same config file to prevent token mismatch
export OPENCLAW_CONFIG_PATH="/home/naithick/hackathons/ossome-hacks/config/openclaw.json"

killall openclaw 2>/dev/null

nohup /home/naithick/.nvm/versions/node/v22.16.0/bin/openclaw gateway run --force > gateway.log 2>&1 &
echo "Waiting for Gateway to boot..."
sleep 5

venv/bin/python scripts/demo_blocked_trade.py
