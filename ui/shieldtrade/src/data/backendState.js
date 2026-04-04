export const symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA'];

export const seedQuotes = {
  AAPL: 241.35,
  MSFT: 349.21,
  GOOGL: 171.44,
  AMZN: 182.6,
  NVDA: 166.86,
  TSLA: 188.42,
};

export const bars = {
  NVDA: {
    '1D': [162, 163, 162.5, 164, 164.2, 165.1, 164.8, 166.2, 165.9, 166.7],
    '1W': [158, 159.3, 160.1, 161.2, 162.8, 164.4, 166.7],
    '1M': [149, 151, 153, 150, 155, 157, 160, 158, 163, 166.7],
  },
  AAPL: {
    '1D': [238, 238.6, 239.2, 240, 239.4, 240.2, 241.1, 241.35],
    '1W': [232, 233.5, 235, 236.7, 238.2, 240.1, 241.35],
    '1M': [224, 227, 229, 231, 233, 236, 238, 239, 240.2, 241.35],
  },
  MSFT: {
    '1D': [345.8, 346.4, 347.1, 346.8, 347.6, 348.2, 348.9, 349.21],
    '1W': [338, 340.5, 342.2, 344.1, 346.3, 348.4, 349.21],
    '1M': [328, 331, 334, 336, 339, 341, 344, 346, 348, 349.21],
  },
  GOOGL: {
    '1D': [169.1, 169.8, 170.4, 170.1, 170.9, 171.2, 171.44],
    '1W': [165.2, 166.8, 167.9, 168.6, 169.7, 170.8, 171.44],
    '1M': [159, 161, 162.5, 163.7, 165.3, 166.2, 167.9, 168.5, 170.2, 171.44],
  },
  AMZN: {
    '1D': [180.1, 180.6, 181.2, 181.8, 181.5, 182.2, 182.6],
    '1W': [176.4, 177.8, 178.9, 179.6, 180.8, 181.7, 182.6],
    '1M': [169, 171, 173.2, 174.8, 176.1, 177.7, 179.3, 180.9, 181.8, 182.6],
  },
  TSLA: {
    '1D': [184.4, 185.9, 186.1, 185.2, 186.8, 187.6, 188.42],
    '1W': [177.4, 179.6, 181.1, 182.8, 184.9, 186.7, 188.42],
    '1M': [168, 170, 173, 175, 178, 180, 182, 184, 186.1, 188.42],
  },
};

export const agentProfiles = {
  ANALYST: {
    label: 'Analyst',
    icon: '[AN]',
    role: 'Analyzes market context and writes structured recommendations.',
  },
  RISK: {
    label: 'Risk Manager',
    icon: '[RM]',
    role: 'Applies deterministic policy checks and issues delegation tokens.',
  },
  TRADER: {
    label: 'Trader',
    icon: '[TR]',
    role: 'Executes paper orders only after valid delegation approval.',
  },
};

export const recommendationSnapshot = {
  symbol: 'NVDA',
  action: 'BUY',
  qty: 12,
  price_target: 180,
  confidence: 0.8,
  reasoning: 'NVDA has strong growth potential in AI and gaming, with momentum and broad sector demand support.',
  timestamp: '2026-04-04T04:29:06.051113+00:00',
};

export const riskDecisionSnapshot = {
  approved: true,
  delegation_token: 'f47ac10b-3f2a-48b7-8b10-3b464a26a6d9',
  expires_in_seconds: 300,
  timestamp: '2026-04-04T04:29:06.051113+00:00',
  notes: 'Trade recommendation approved for execution',
};

export const tradeLogSnapshot = {
  timestamp: '2026-04-04T04:29:15.706932+00:00',
  ticker: 'NVDA',
  action: 'BUY',
  qty: 12,
  amount_usd: 2160,
  order_result: {
    order_id: '2047c85a-7e24-43b7-85d0-5da94d126a5a',
    status: 'OrderStatus.ACCEPTED',
  },
};

export const policyRules = {
  allowedTickers: ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META'],
  maxPositionSize: 100,
  maxDailySpend: 10000,
  maxSingleOrder: 2500,
  ttlSeconds: 300,
  paperOnly: true,
};

export const rawPolicyYaml = `enforcement: "deterministic"
version: "0.1.0"

global:
  denied_tools: [shell, exec, web_fetch]
  network:
    allowed_domains: [paper-api.alpaca.markets, data.alpaca.markets]
    blocked_domains: [api.alpaca.markets]

market_hours:
  enabled: false
  timezone: "US/Eastern"

trading:
  paper_only: true
  allowed_tickers: [AAPL, MSFT, GOOGL, AMZN, NVDA, TSLA, META]
  max_position_size: 100
  max_daily_spend_usd: 10000
  max_single_order_usd: 2500

delegation:
  token_ttl_seconds: 300
  require_risk_approval: true
  max_concurrent_tokens: 3`;
