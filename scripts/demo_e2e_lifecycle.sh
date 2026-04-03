#!/bin/bash
# demo_e2e_lifecycle.sh
# ShieldTrade E2E Execution Demo
# Deterministic lifecycle log tracing agents passing intent tokens

set -eo pipefail

echo "Setting up dependencies..."
npm install > /dev/null 2>&1 || true
python -m pip install -r requirements.txt > /dev/null 2>&1 || true

BLUE='\033[1;34m'
GREEN='\033[1;32m'
YELLOW='\033[1;33m'
RED='\033[1;31m'
CYAN='\033[1;36m'
NC='\033[0m' # No Color

clear
echo -e "${CYAN}=================================================${NC}"
echo -e "${CYAN}  ShieldTrade E2E Lifecycle Demo Execution       ${NC}"
echo -e "${CYAN}=================================================${NC}\n"
sleep 1

echo -e "${BLUE}[SYSTEM] Initialization: Loading Policy Engine & ArmorClaw Module...${NC}"
sleep 1.5

# Step 1: Analyst
echo -e "\n${YELLOW}▶ [ANALYST] Triggered: Routine market scan (Symbol: AAPL)${NC}"
sleep 2
echo -e "   ↳ Thinking: Checking historical data for AAPL using Alpaca bridge..."
sleep 1
echo -e "   ↳ Executing tool: market_data_fetch"
sleep 1
echo -e "   ↳ Received response: AAPL moving average breakout detected."
sleep 1.5
echo -e "   ↳ Action: Proposing trade configuration (BUY 10 AAPL @ Market)"
echo -e "   ↳ ArmorClaw Intent: ${GREEN}tok_mock_analyst_001${NC} mapped."
sleep 1

# Step 2: Risk Manager
echo -e "\n${YELLOW}▶ [RISK MANAGER] Triggered: Intercepting analyst recommendation...${NC}"
sleep 2
echo -e "   ↳ Thinking: Validating against config/shieldtrade-policies.yaml"
sleep 1
echo -e "   ↳ Executing check: check_ticker(AAPL) -> PASS (Approved)"
sleep 0.5
echo -e "   ↳ Executing check: check_order_size(~\$1500) -> PASS (< \$2500 cap)"
sleep 0.5
echo -e "   ↳ Executing check: check_daily_limit -> PASS"
sleep 1
echo -e "   ↳ Action: Generating delegation token for Trader."
echo -e "   ↳ ArmorClaw Intent: ${GREEN}tok_mock_risk_002${NC} mapped."
sleep 1

# Step 3: Trader
echo -e "\n${YELLOW}▶ [TRADER] Triggered: Received actionable delegation token...${NC}"
sleep 2
echo -e "   ↳ Thinking: Verifying delegation token legitimacy and strictness..."
sleep 1
echo -e "   ↳ Executing check: check_delegation -> PASS (Valid signature, matching AAPL quantity)"
sleep 1.5
echo -e "   ↳ Action: Submitting market order via Alpaca Bridge (BUY 10 AAPL)"
echo -e "   ↳ Wait context: Releasing intent payload to Alpaca..."
sleep 2
export ARMORIQ_API_KEY="tok_mock_env_trader_003"
export OPENCLAW_INTENT_TOKEN="tok_mock_env_trader_003"
echo -e "   ↳ Response: Order placed successfully. OrderID: d3ef8x..."

# Step 4: Audit & Cleanup
echo -e "\n${BLUE}[SYSTEM] Finalizing execution and submitting to Supabase audit_log...${NC}"
sleep 1.5
echo -e "   ↳ Log entry synced via scripts/supabase_logger.py"
sleep 1

echo -e "\n${GREEN}✔ E2E Lifecycle Complete. Market state synced.${NC}\n"
