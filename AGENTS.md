# deterministic-agent

Deterministic guardrails for AI coding agents. Move checks from *after*
(reviews, tests) to *before* (schemas, gates) and *during* (law lints,
replay).

## Skills

- `software-development/` — for changes that touch code, tools, or CI
- `AGENTS.md` — operating rules for AI agents working in this repo

## Conventions

- Pure Python in `core/`, no agent coupling
- Adapters are thin shims that call `core/`
- Exit codes: 0 = pass, 2 = fail (matches Hermes/Claude hook convention)
- Tests required for every change to `core/`

See `README.md` for the public-facing description.
