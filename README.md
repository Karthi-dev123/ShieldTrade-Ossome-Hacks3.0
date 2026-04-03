# ShieldTrade - Ossome Hacks 3.0 Submission

ShieldTrade is a highly secure multi-agent financial advisory system operating on the OpenClaw framework. It features deterministic declarative policies, AI-driven advisory workflows, and completely secure trading intent execution via ArmorClaw and Alpaca bridges.

## Features at a Glance

- **Multi-Agent Advisory**: Specialized roles (Analyst, Risk Manager, Trader) collaborating seamlessly.
- **Deterministic Policy Engine**: Highly secure, declarative YAML-based trading limits and rules.
- **Auditable & Traceable**: Full integration with Postgres via Supabase.
- **Zero-Trust Trading**: Forced execution constraints with ArmorClaw API intent tokens and robust validations.

---

## 🚀 Quick Start / Evaluation Guide

We have consolidated the entire pipeline into a single execution step to evaluate the complete platform lifecycle cleanly and gracefully. All necessary `.env` files with credentials will be provided directly and must be placed in the repository root.

### Evaluation Requirements
- A valid `.env` file at the root of the project (provided directly by our team).
- Python 3.10+
- Bash environment (Git Bash or WSL for Windows users)

> **Note on AI API Fallbacks**: Due to API rate limits during testing, our proxy system routes logic automatically. If all primary keys fail, the execution will gracefully fall back or you can configure `USE_OLLAMA=true` to route via a local Ollama instance seamlessly.

### 2. Run the Demo

Simply execute the evaluation script from the root directory.

**For Linux / Mac:**
```bash
./run_shieldtrade.sh
```

**For Windows:**
Simply double-click the `run_shieldtrade.bat` file, or run it via terminal:
```cmd
run_shieldtrade.bat
```

**What this evaluation script does automatically:**
1. Loads the provided `.env` credentials securely.
2. Simulates an end-to-end trade validation and decision lifecycle entirely locally.
3. Triggers the policy guardrails proactively to prove our defensive execution checks work.
4. Generates an intent signature securely, validates it, and traces the outcome.
5. Emits a clean, traceable output to the terminal.

---

## Technical Cleanliness Guarantee
This repository has been fully sanitized for grading. To eliminate noise, all internal documentation, logs (`output/`, `data/`), test caching (`__pycache__`), API keys, and environment files have been permanently stripped from this codebase. The repository contains only the exact executable logic needed to grade the solution.
