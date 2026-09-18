#!/usr/bin/env bash
# post-tool-call hook: validates tool output shape against JSON Schema.
# Receives a JSON envelope on stdin describing the tool and its result.
#
# Hermes wire protocol for post_tool_call only honors {"context": "..."}.
# We CANNOT block a tool call that has already completed; we can only emit
# context that surfaces in the conversation log + gets attached to the
# next LLM turn. fail_closed here is informational only — the dispatcher's
# `fail_closed` semantics apply to pre_tool_call, not post_tool_call.
#
# To get real schema enforcement on tool output, use pre_tool_call
# `modify` directives to wrap the call, or run schema validation as a
# post-verify gate (pre_verify event).
set -uo pipefail

if [ "${DETERMINISTIC_AGENT_SKIP:-0}" = "1" ]; then
  exit 0
fi

PAYLOAD="$(cat)"
TOOL="$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // .tool // "unknown"')"

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
# Emit a context message. post_tool_call can't block, but the agent will
# see this on its next turn and in the session log.
jq -nc --arg msg "$DETAIL" '{context: ("deterministic-agent: schema violation in " + "'"$TOOL"'" + ": " + $msg + " (output was already delivered; consider adding a pre_tool_call modify to sanitize)")}'
exit 0
