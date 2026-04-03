# ShieldTrade

ShieldTrade is a multi-agent financial advisory system operating on the OpenClaw framework, with declarative policies and deterministic intent execution via ArmorClaw.

## Architecture & Branches

This branch serves as the finalized integration for the multi-agent trading backend, combining policy enforcement, Alpaca bridges, Supabase audit logs, and gateway tools into a single source of truth. 

**Strict Isolation:**
- Node.js logic runs the local proxy and gateway.
- Python code operates within `scripts/` and `tests/` exclusively.

## Setup

1. **Initialize Requirements:**
```bash
python -m pip install -r requirements.txt
npm install
```

2. **Environment Variables:**
Create `.env` at the repository root:
```dotenv
GROQ_API_KEY=...
ALPACA_API_KEY=...
ALPACA_SECRET_KEY=...
ARMORIQ_API_KEY=...
GEMINI_API_KEY1=...
GEMINI_API_KEY2=...
GEMINI_API_KEY3=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_KEY=...
ANTHROPIC_API_KEY=...
USE_OLLAMA=false
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_API_KEY=...
```

Never commit `.env`.

## Services

### Local LLM Rate-Limit Proxy
To avoid LLM API rate limits when managing intensive agent routines:
```bash
node scripts/proxy.js
```
The proxy runs on port 4000. It features an integrated failover API logic. 
If `USE_OLLAMA=true` is set, the proxy automatically routes standard agent operations to a local Ollama instance (defaulting to `http://localhost:11434`) using `OLLAMA_API_KEY` for seamless offline/unmetered testing. 

### Policy Engine Enforcement
Executables reside in `scripts/policy_engine.py` for evaluating trade constraints. Timezone validation strictly adheres to `America/New_York`.

```bash
python scripts/policy_engine.py check-trade '{"symbol":"AAPL","qty":10,"side":"buy","price":150}' trader
```

## Validation & Testing

```bash
python -m pytest tests/ -q
```

Output constraints:
- `output/reports/gateway-validation.json` holds evidence of dropped intents.
- Audit integrations pipe deterministically to `audit_log` via Supabase implementations.
