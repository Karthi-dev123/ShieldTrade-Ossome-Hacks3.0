#!/bin/bash
killall openclaw 2>/dev/null
sleep 2

# Start the gateway
nohup /home/naithick/.nvm/versions/node/v22.16.0/bin/openclaw gateway run --force > gateway-daemon.log 2>&1 &

echo "Gateway booting..."
sleep 5

# Synchronize API keys from .env
set -a
source .env
set +a
export OPENCLAW_CONFIG_PATH="/home/naithick/hackathons/ossome-hacks/config/openclaw.json"

# Execute
venv/bin/python scripts/demo_blocked_trade.py
