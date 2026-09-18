#!/usr/bin/env bash
# post-tool-use hook: validates tool output shape against JSON Schema.
# Exit 0 = allow, exit 2 = block (the agent sees the schema violation).
#
# Receives a JSON envelope on stdin describing the tool and its result:
#   {"tool": "web_search", "result": {...}}
#
# Extracts .result, wraps it in the standard envelope, pipes to stdin.
set -euo pipefail

if [ "${DETERMINISTIC_AGENT_SKIP:-0}" = "1" ]; then
  exit 0
fi

PAYLOAD="$(cat)"
TOOL="$(printf '%s' "$PAYLOAD" | jq -r '.tool // "unknown"')"

# Tools we have schemas for (keep in sync with core/deterministic_agent/schemas.py)
case "$TOOL" in
  terminal|web_search|web_extract|read_file|search_files) ;;
  *) exit 0 ;;
esac

# Wrap the agent's result in the standard envelope, pipe to validator.
RESULT="$(jq -n --argjson r "$(printf '%s' "$PAYLOAD" | jq -c '.result // {}')" \
  '{status: "ok", payload: $r}' \
  | deterministic-agent validate "$TOOL" - 2>&1 || true)"

OK="$(printf '%s' "$RESULT" | jq -r '.ok' 2>/dev/null || echo "true")"
if [ "$OK" = "true" ]; then
  exit 0
fi

DETAIL="$(printf '%s' "$RESULT" | jq -r '.detail // "schema violation"')"
echo "deterministic-agent schema violation: $DETAIL" >&2
exit 2
