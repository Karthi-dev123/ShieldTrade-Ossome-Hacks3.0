# ShieldTrade - Ossome Hacks 3.0 Submission

ShieldTrade is a highly secure multi-agent financial advisory system operating on the OpenClaw framework. It features deterministic declarative policies, AI-driven advisory workflows, and completely secure trading intent execution via ArmorClaw and Alpaca bridges.

## Features at a Glance

- **Multi-Agent Advisory**: Specialized roles (Analyst, Risk Manager, Trader) collaborating seamlessly.
- **Deterministic Policy Engine**: Highly secure, declarative YAML-based trading limits and rules.
- **Auditable & Traceable**: Full integration with Postgres via Supabase.
- **Zero-Trust Trading**: Forced execution constraints with ArmorClaw API intent tokens and robust validations.

---

## 🚀 Quick Start / Evaluation Guide

We have consolidated the entire pipeline into a **single, secure executable script** to evaluate the complete platform lifecycle cleanly and gracefully. 

### 1. Prerequisites
- Python 3.10+
- A valid `.env` file at the root of the project (copy the provided `.env.example` and insert your credentials).

> **Note on Gemini API Fallbacks**: AI APIs can frequently hit rate limits. For graceful degradation, our proxy system handles key rotations automatically. If all keys fail, you can set `USE_OLLAMA=true` in your `.env` to route logic through a local Ollama instance seamlessly.

### 2. Run the Evaluation Simulation

Execute the following script from the root of the repository to witness the complete "Analyst -> Risk Manager -> Trader -> Gateway" flow:

```bash
bash scripts/demo_e2e_lifecycle.sh
```

**What this script does securely:**
1. Verifies your environment and API capabilities.
2. Simulates an end-to-end trade validation and decision lifecycle.
3. Automatically triggers the policy guardrails to prove our defensive execution blocks.
4. Generates an intent signature via Armoriq, securely validates it, and logs the outcome.
5. Emits a clean, traceable output to the terminal and database without manual intervention.

---

## Technical Guarantee
This repository has been sanitized and follows strict security and architecture guidelines. All sensitive keys, build caching, `__pycache__`, `node_modules`, and environment configurations have been permanently excluded from tracking to ensure a zero-leak footprint.

All architectural rules (e.g. `America/New_York` timezone checks) apply dynamically and deterministically.
