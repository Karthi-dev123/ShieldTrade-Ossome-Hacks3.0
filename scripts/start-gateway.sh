#!/usr/bin/env bash
# Start OpenClaw Gateway

# Source NVM to ensure node 22.16.0 and openclaw are in PATH
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm use 22.16.0

# Export path to the OpenClaw configuration file using absolute path resolution
export OPENCLAW_CONFIG_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/config/openclaw.json"

# Start the OpenClaw gateway service natively
openclaw gateway start
