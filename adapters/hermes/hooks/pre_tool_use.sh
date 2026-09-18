#!/usr/bin/env bash
# pre-tool-call hook: gates destructive actions before the agent runs them.
# Receives a JSON payload on stdin describing the proposed action.
# Wire protocol (Hermes):
#   exit 0 + no JSON stdout              → allow
#   exit 2 + {"action":"block","message":...} on stdout → block with message
# fail_closed:true in config means spawn errors / timeouts also block.
#
# Design:
#   1. Extract the relevant value with jq -R (raw string stdin) so special
#      chars in the value are not interpreted by jq as expressions.
#   2. Pass the value into a SECOND jq call via --arg / --argjson, where
#      the value comes from a bash variable that was assigned from
#      `jq -R`'s output (so the value never goes through shell quoting
#      back into jq).
#   3. Pipe the constructed JSON object into deterministic-agent.
set -uo pipefail

if [ "${DETERMINISTIC_AGENT_SKIP:-0}" = "1" ]; then
  exit 0
fi

PAYLOAD="$(cat)"
TOOL="$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // .tool // "unknown"')"

# safe_extract <jq_filter>  — runs `jq -R` against PAYLOAD, returns raw string
safe_extract() {
  local filter="$1"
  printf '%s' "$PAYLOAD" | jq -R -r "$filter"
}

# gate <action> <json_object_string>
# Caller has already built the JSON object via jq (safe).
# This fn pipes it to deterministic-agent and emits the block JSON on failure.
gate() {
  local action="$1" json="$2"
  local out rc
  # Use a tempfile to avoid word-splitting on values containing spaces.
  local tmpf
  tmpf="$(mktemp)"
  printf '%s' "$json" | deterministic-agent preflight "$action" - >"$tmpf" 2>&1
  rc=$?
  out="$(cat "$tmpf")"
  rm -f "$tmpf"
  if [ "$rc" -eq 0 ]; then
    exit 0
  fi
  local detail
  detail="$(printf '%s' "$out" | jq -r '.detail // "blocked by deterministic-agent preflight"' 2>/dev/null || echo "blocked by deterministic-agent preflight")"
  jq -nc --arg msg "$detail" '{action: "block", message: ("deterministic-agent: " + $msg)}'
  exit 2
}

# Build a JSON object from key=value args. Args come from `safe_extract`
# outputs that are then assigned to local vars (no shell re-quoting of
# the values into jq).
build_obj() {
  # args: key1 value1 key2 value2 ...
  local out="{"
  local first=1
  while [ $# -gt 0 ]; do
    local key="$1" val="$2"
    shift 2
    # Build JSON incrementally with jq -n --arg, safe for any value.
    if [ "$first" -eq 1 ]; then
      out="$(jq -n --arg k "$key" --arg v "$val" '{($k): $v}')"
      first=0
    else
      local existing="$out"
      out="$(jq -n --argjson a "$existing" --arg k "$key" --arg v "$val" '$a + {($k): $v}')"
    fi
  done
  printf '%s' "$out"
}

case "$TOOL" in
  write_file|patch)
    P="$(safe_extract 'try (fromjson | .args.path // "") catch ""')"
    gate write_file "$(build_obj path "$P")"
    ;;
  terminal)
    C="$(safe_extract 'try (fromjson | .args.command // "") catch ""')"
    gate terminal "$(build_obj command "$C")"
    ;;
  process_kill)
    PID="$(safe_extract 'try (fromjson | .args.pid // 0) catch 0')"
    gate process_kill "$(jq -nc --argjson pid "$PID" '{pid: $pid}')"
    ;;
  browser)
    U="$(safe_extract 'try (fromjson | .args.url // "") catch ""')"
    H="$(safe_extract 'try (fromjson | .args.host // "") catch ""')"
    if [ -z "$H" ] && [ -n "$U" ]; then
      # Extract host from URL safely. Use jq -R to treat as raw string.
      H="$(printf '%s' "$U" | jq -R -r 'split("/")[2] // ""')"
    fi
    if [ -z "$H" ]; then
      exit 0
    fi
    gate browser "$(build_obj host "$H")"
    ;;
  *)
    exit 0
    ;;
esac
