#!/usr/bin/env bash
# pre-tool-use hook: gates destructive actions before the agent runs them.
# Receives a JSON payload on stdin describing the proposed action.
# Exit 0 = allow, exit 2 = block (stderr fed back to the agent).
#
# The hook extracts the relevant args via jq, then pipes a small JSON
# payload via stdin to `deterministic-agent preflight <action> -`.
# This avoids any shell interpolation of agent-controlled strings.
set -euo pipefail

if [ "${DETERMINISTIC_AGENT_SKIP:-0}" = "1" ]; then
  exit 0
fi

PAYLOAD="$(cat)"
TOOL="$(printf '%s' "$PAYLOAD" | jq -r '.tool // "unknown"')"

# Map tool names to preflight actions. Each branch pipes JSON via stdin.
case "$TOOL" in
  write_file|patch)
    PAYLOAD_PATH="$(printf '%s' "$PAYLOAD" | jq -r '.args.path // ""')"
    RESULT="$(jq -n --arg path "$PAYLOAD_PATH" '{path:$path}' \
      | deterministic-agent preflight write_file - 2>&1 || true)"
    ;;
  terminal)
    PAYLOAD_CMD="$(printf '%s' "$PAYLOAD" | jq -r '.args.command // ""')"
    # Build JSON with jq (safer than printf for special chars)
    RESULT="$(jq -n --arg cmd "$PAYLOAD_CMD" '{command:$cmd}' \
      | deterministic-agent preflight terminal - 2>&1 || true)"
    ;;
  process_kill)
    PAYLOAD_PID="$(printf '%s' "$PAYLOAD" | jq -r '.args.pid // 0')"
    RESULT="$(jq -n --argjson pid "$PAYLOAD_PID" '{pid:$pid}' \
      | deterministic-agent preflight process_kill - 2>&1 || true)"
    ;;
  *)
    exit 0
    ;;
esac

OK="$(printf '%s' "$RESULT" | jq -r '.ok' 2>/dev/null || echo "true")"
if [ "$OK" = "true" ]; then
  exit 0
fi

DETAIL="$(printf '%s' "$RESULT" | jq -r '.detail // "blocked by deterministic-agent preflight"')"
echo "deterministic-agent blocked: $DETAIL" >&2
exit 2
