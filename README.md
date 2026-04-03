# ShieldTrade - Ossome Hacks 3.0 Submission

ShieldTrade is a deterministic, highly secure multi-agent financial advisory platform built on the OpenClaw framework. Because this is a **backend/agentic engine submission without a frontend UI**, we have created a single, comprehensive End-to-End (E2E) testing script to easily validate all core capabilities.

## Architecture Highlights
- **Multi-Agent Orchestration**: Specialized agents (Analyst, Risk Manager, Trader) collaborating seamlessly to make grounded decisions.
- **Deterministic Policy Engine**: Highly secure, declarative YAML-based trading limits and validation blockages.
- **Traceability & Governance**: Fully auditable pipeline with Postgres via Supabase logs.
- **Zero-Trust Trading Execution**: Forced API execution constraints utilizing ArmorClaw intent tokens and Alpaca bridges.

---

## 🚀 E2E Evaluation Guide

We have consolidated the entire complex backend pipeline into a **single execution step**. This script spins up the proxy, validates the agent logic sequentially, runs the defensive trade policy checks natively, handles APIs, and gracefully reports all outputs.

### Prerequisites

All sensitive configurations have been decoupled. **Please copy the `.env` file provided privately into the root of this repository before running.**

- Python 3.10+
- The `.env` file (provided directly) placed in the repository root.

### Running the End-to-End Test

Depending on your OS, simply run the appropriate script below.

**For Mac / Linux / WSL / Git Bash:**
```bash
./run_shieldtrade.sh
```

**For Native Windows (CMD/PowerShell):**
```cmd
run_shieldtrade.bat
```

*Note on Resilience: Generative AI API keys (like Gemini) often suffer from aggressive rate limiting. To prevent evaluation failures, our backend proxy will gracefully rotate through API keys automatically, and can fall back to Ollama if locally configured.*

---

## What the Script Does (The Flow)

If you follow the execution terminal output, you will see it natively step through:
1. **Network & Credential Check**: Securely parsing the `.env` and booting local failovers.
2. **Analysis Phase**: The Analyst agent fetching data to justify a market move.
3. **Risk Enforcement**: The Risk Manager agent reviewing the decision against strict YAML rules (ensuring no unauthorized pairs, size limits, or timezone bounds are breached).
4. **Trader Intent Generation**: Generating the final API signature via Armoriq for execution.
5. **Gateway Auditing**: Finally logging the resulting verified transaction state cleanly into Supabase.

*This repository is entirely sanitized for judging—stripped of bloat, temp caches (`__pycache__`), API keys, and test packages.*
