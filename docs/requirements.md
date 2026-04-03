# ShieldTrade — Requirements

## AI Coding Constraints

> **STRICT ENFORCEMENT — NO EXCEPTIONS**

- **Python**: `scripts/` and `tests/` only.
- **TypeScript/Node.js**: `config/`, gateway, plugins only.
- No NPM packages inside Python directories. No pip installs in Node directories.
- No mixed runtimes in a single directory.

## Stack

| Component | Version | Install Method |
|---|---|---|
| Node.js | 22.16.0 LTS | `nvm install 22.16.0` |
| OpenClaw | 2026.3.28 | `npm install -g openclaw@2026.3.28` |
| ArmorClaw | latest | `curl -fsSL https://armoriq.ai/install-armorclaw.sh \| bash` |
| pnpm | 10.6.5 | `npm install -g pnpm@10.6.5` |
| TypeScript | 5.8.3 | via pnpm |
| Python | 3.12.3 | System or `pyenv install 3.12.3` |
| LLM | claude-sonnet-4-6 | Anthropic API |
| alpaca-py | latest stable | `pip install alpaca-py` |
| Supabase | latest stable | `pip install supabase` |
| PyYAML | 6.0.2 | `pip install PyYAML==6.0.2` |
| filelock | 3.16.1 | `pip install filelock==3.16.1` |
| pytest | 8.3.5 | `pip install pytest==8.3.5` |
| httpx | 0.28.1 | `pip install httpx==0.28.1` |
| python-dotenv | 1.1.0 | `pip install python-dotenv==1.1.0` |

## Hard Constraints

- Node.js must be exactly 22.16.0 — 18.x breaks ArmorClaw plugin loader, 24.x is untested
- OpenClaw must be >= 2026.3.22 (earlier breaks ClawHub plugin API)
- ArmorClaw runs fail-closed — if IAP is unreachable, all tool execution blocks
- All trades hit `paper-api.alpaca.markets` only — live API is blocked at policy level
- `market_hours_only.enabled` = false during dev (IST ≠ ET)
- No real money at any stage
- Supabase free tier (500MB) — one project only

## Runtime Isolation

### Python Directories (scripts/, tests/)
- Only `pip install`
- No `package.json`, no `node_modules/`

### Node.js Directories (config/, root configs)
- Only `npm`/`pnpm`
- No `venv/`, no `__pycache__/`

## Testing

- Every policy check in `policy_engine.py` gets a pytest unit test
- Blocked scenarios (wrong ticker, over limit, expired delegation, no token) must all have tests
- `policy_engine.py` must use `filelock.FileLock` on `daily-spend.json` (race condition fix)
- All tests green before demo

## Git Workflow

- Branch: `main` (protected), `feat/<name>`, `fix/<name>`
- Conventional commits: `feat:`, `fix:`, `chore:`, `test:`, `docs:`
- Never commit: `.env`, `output/`, `*.log`, `__pycache__/`, `node_modules/`, `venv/`

## Environment Variables

```
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ARMORIQ_API_KEY=
ANTHROPIC_API_KEY=
SUPABASE_URL=
SUPABASE_ANON_KEY=
```
