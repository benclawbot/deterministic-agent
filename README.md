# deterministic-agent

Deterministic guardrails for AI coding agents. Move checks from *after*
(reviews, tests) to *before* (schemas, gates) and *during* (law lints,
replay).

## The four checks

| Check | Fires when | What it does |
|---|---|---|
| **schema** (`schemas.py`) | After any tool call | Validates tool output against JSON Schema. The model gets a typed shape, not prose. |
| **preflight** (`preflight.py`) | Before writes, network, kills | Blocks destructive actions outside an allowlist. Pure functions, no LLM. |
| **lawlint** (`lawlint.py`) | After a skill ends | Asserts the skill's structured output conforms to its `LAWS.md`. Inspired by Bend's `LAWS.bend`, in markdown + Python. |
| **replay** (`replay.py`) | On cron for research skills | Re-runs last-period inputs and compares output hashes. Surfaces silent regressions. |

All four are **pure Python, JSON-in/JSON-out, exit 0/2** — the contract every
agent hook system already understands.

## Install

```bash
pip install deterministic-agent
deterministic-agent init   # writes ~/.config/deterministic-agent/gates.yaml
```

For Hermes, also install the portable plugin:

```bash
hermes plugins install <git-url>
```

For Claude Code:

```bash
claude --plugin-dir adapters/claude/    # local dev
# or: claude --plugin-url <zip-url>     # one-shot
```

For OpenCode:

```bash
opencode plugin deterministic-agent
```

## Quick start

### Schema-check a tool result

```bash
deterministic-agent validate web_search result.json
# {"ok": true, "detail": "valid"}
# or: {"ok": false, "detail": "payload violation in web_search: ..."}
```

### Gate a destructive action

```bash
echo '{"path":"/etc/passwd"}' | deterministic-agent preflight write_file -
# {"ok": false, "detail": "write target '/etc/passwd' is outside allowed roots..."}
```

### Lint a skill's output against its LAWS.md

```bash
deterministic-agent lawlint skills/requesting-code-review/LAWS.md output.json
# {"ok": true, "detail": "all 4 laws conformant"}
```

### Replay a research run

```bash
deterministic-agent replay competitor-news-monitor inputs.json output.json
# {"ok": true, "detail": "output unchanged (a3f9c2...)"}
# or: {"ok": false, "detail": "regression detected: previous hash ... differs from ..."}
```

## How a hook sees it

Hermes, Claude, and OpenCode all use the same contract: shell out, read JSON
on stdin, exit 0 for pass / 2 for fail. Example (`adapters/hermes/hooks/pre_tool_use.sh`):

```bash
PAYLOAD="$(cat)"
ACTION="$(jq -r '.tool' <<<"$PAYLOAD")"
ARGS="$(jq -c '.args' <<<"$PAYLOAD")"
case "$ACTION" in
  write_file|patch)        deterministic-agent preflight write_file   <<<"$ARGS" ;;
  terminal)                deterministic-agent preflight terminal   <<<"$ARGS" ;;
  process_kill)            deterministic-agent preflight process_kill <<<"$ARGS" ;;
esac
```

## Writing LAWS.md

```markdown
## LAW: every_finding_cites_location
- require: findings.0.file has ":"
- message: every finding must include "file:line"

## LAW: severity_is_canonical
- require: findings.0.severity in {critical,high,medium,low,nit}
```

Operators: `==`, `!=`, `in`, `notin`, `has`, `len>=`, `len<=`, `len==`.

See `laws/examples/` for full examples.

## Configuration

`~/.config/deterministic-agent/gates.yaml`:

```yaml
allowed_write_roots:
  - $cwd
  - $HOME/.hermes
allowed_network_hosts:
  - github.com
  - api.github.com
  - pypi.org
require_confirmation_for_kill: true
block_curl_to_ip_literal: true
```

Set `DETERMINISTIC_AGENT_SKIP=1` to bypass all gates in one shot (escape hatch).

## Why

LLM-written code is probabilistic. The things we *care about* (the code didn't
break an invariant, the tool returned the right shape, the network call
wasn't to an unexpected host) are deterministic. Make those checks
deterministic — by schemas, by gates, by lint, by replay — and the
probabilistic layer only has to get the *interesting* parts right.

This is the same idea as Bend's `LAWS.bend`, expressed in a form that
drops into any agent that already runs hooks. No new language, no new
compiler, no rewrite.

## Status

`v0.1.0` — schemas, preflight, lawlint, replay all functional. Hermes
adapter ships. Claude Code and OpenCode adapters are scaffolds in
`adapters/`; wire them next.

## License

MIT.
