#!/usr/bin/env bash
# skill-end hook: runs lawlint against the skill's most recent structured output.
# Skills opt in by shipping a LAWS.md next to their SKILL.md and writing
# their output to a known path (passed via env var DETERMINISTIC_AGENT_OUTPUT).
set -euo pipefail

if [ "${DETERMINISTIC_AGENT_SKIP:-0}" = "1" ]; then
  exit 0
fi

SKILL_DIR="${DETERMINISTIC_AGENT_SKILL_DIR:-}"
OUTPUT_PATH="${DETERMINISTIC_AGENT_OUTPUT:-}"
LAWS_PATH="${SKILL_DIR}/LAWS.md"

if [ -z "$SKILL_DIR" ] || [ -z "$OUTPUT_PATH" ] || [ ! -f "$LAWS_PATH" ] || [ ! -f "$OUTPUT_PATH" ]; then
  exit 0
fi

RESULT="$(deterministic-agent lawlint "$LAWS_PATH" "$OUTPUT_PATH" 2>&1 || true)"
OK="$(printf '%s' "$RESULT" | jq -r '.ok' 2>/dev/null || echo "true")"
if [ "$OK" = "true" ]; then
  exit 0
fi

DETAIL="$(printf '%s' "$RESULT" | jq -r '.detail // "law violation"')"
echo "deterministic-agent lawlint failure in $SKILL_DIR: $DETAIL" >&2
exit 2
