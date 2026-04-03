# ShieldTrade — Agent Specification

## 1. System Identity
ShieldTrade is a multi-agent financial platform leveraging the OpenClaw 2026.3.28 framework. Security is enforced via ArmorClaw intent tokens and deterministic YAML policies.

## 2. Agent Definitions

### Analyst (`shieldtrade-analyst`)
- **Objective**: Conduct equity research and generate buy/sell recommendations.
- **Allowed Tools**: `market_data_fetch`, `write_report`, `recommend_trade`
- **Denied Tools**: `place_order`, `get_account`, `shell`, `web_fetch`
- **Boundaries**: 
  - Read: `/data/market/*`, `/data/earnings/*`
  - Write: `/output/reports/*`

### Risk Manager (`shieldtrade-risk-manager`)
- **Objective**: Validate Analyst recommendations against portfolio and risk constraints.
- **Allowed Tools**: `read_portfolio`, `check_limits`, `approve_trade`, `reject_trade`
- **Denied Tools**: `place_order`, `market_data_fetch`, `shell`
- **Boundaries**: 
  - Read: `/output/reports/*`, `/data/portfolio/*`
  - Write: `/output/risk-decisions/*`

### Trader (`shieldtrade-trader`)
- **Objective**: Execute approved trades within delegated scope only.
- **Requirement**: Must possess a valid ArmorClaw delegation token issued by the Risk Manager.
- **Allowed Tools**: `place_order`, `get_positions`, `get_account`
- **Denied Tools**: `market_data_fetch`, `write_report`, `shell`
- **Boundaries**: 
  - Read: `/output/risk-decisions/*`
  - Write: `/output/trade-logs/*`

## 3. Policy Constraints (`config/shieldtrade-policies.yaml`)

### Trading Limits
- **Single Order Cap**: $2,000 USD
- **Daily Aggregate Cap**: $10,000 USD
- **Share Limit**: 100 shares per order
- **Timezone**: `America/New_York` (strictly enforced for market hours)

### Data Safety
- **PII Blocking**: Regex-based blocking for SSN, credit cards, and credentials.
- **Exfiltration**: Traffic allowed only to `alpaca.markets` domains.

## 4. Audit & Logging
- **Mechanism**: Every policy evaluation and trade event is logged to the Supabase `audit_log` table.
- **Thought Tracing**: Agents must log their reasoning to `/output/thoughts/{agent}.jsonl` before tool execution.

## 5. Intent Token Requirements
All operations in `scripts/alpaca_bridge.py` strictly require `ARMORIQ_API_KEY`. Tool execution fail-closes if the ArmorClaw plugin is unreachable.
