# ShieldTrade — Instructions

## Reference Material

Everything in `docs/` is reference. Nothing is hardcoded or final. Change anything that doesn't work.

| File | What it is |
|---|---|
| `AGENTS.md` | Reference sketch of the multi-agent architecture. Three agents, their tools, directory boundaries, demo sequences. Starting point — not a spec. |
| `armoriqdocs.md` | ArmorIQ SDK documentation (Python + TypeScript). Official docs in one file. Read when making ArmorIQ SDK calls. |
| `architecture.md` | System diagram, agent boundaries, data flow, security model. |
| `requirements.md` | Stack versions, coding constraints, testing rules. |
| `memory.md` | Session tracking. Update as work progresses. |

## Skills

1,300+ pre-built skills at `~/.gemini/antigravity/skills/`. Read the relevant `SKILL.md` before domain-specific work.

Key installs: `steipete-github`, `sql-toolkit`, `ivangdavila-code`, `docker-essentials`, `clawddocs`, `security-check`, `cc-godmode`, `bat-cat`, `backup`.

## Coding Rules

- No tutorial-style comments. Only comment non-obvious intent.
- Python in `scripts/` and `tests/` only. TypeScript in `config/` and gateway only.
- Read `armoriqdocs.md` for ArmorIQ SDK usage.
- Read `AGENTS.md` for architecture context — it's a starting point, not gospel.
