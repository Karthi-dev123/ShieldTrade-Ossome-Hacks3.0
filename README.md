# ShieldTrade

ShieldTrade is a multi-agent financial advisory system operating on the OpenClaw framework, with declarative policies and deterministic intent execution via ArmorClaw.

## Architecture

This branch serves as the finalized integration for the multi-agent trading backend, combining policy enforcement, Alpaca bridges, Supabase audit logs, and gateway tools into a single source of truth. 

## Quick Start (For Judges)

To run the complete Analyst → Risk Manager → Trader lifecycle simulation with full policy enforcement and execution logic:

```bash
# Setup dependencies and start the end-to-end demo
bash scripts/demo_e2e_lifecycle.sh
```

> **Note**: This single script handles the environment setup, runs the agent simulation, validates trades against the declarative policy engine, and provides clear output at every stage.

## Environment Variables
Ensure you have a `.env` file at the repository root with the required API keys (Alpaca, Groq, Armoriq, Supabase, Gemini). See `.env.example` for the required keys.
