#!/usr/bin/env bash
# pre-tool-call hook with USER CONFIRMATION flow.
#
# Wire protocol (Hermes pre_tool_call):
#   exit 0                               → allow (silent pass-through)
#   exit 0 + {"context": "..."}           → allow but inject context
#   exit 0 + {"action":"continue","message":"..."} → yield to client for user confirmation
#   exit 2 + {"action":"block","message":"..."}    → deny with message to model
#
# Flow:
#   - Allowed writes (inside $cwd, $HOME/.hermes): allow silently
#   - Unknown network calls: block (security cannot prompt)
#   - process_kill: prompt user (kill is rarely needed by LLMs)
#   - Unknown writes: prompt user via "continue" directive

set -uo pipefail

if [ "${DETERMINISTIC_AGENT_SKIP:-0}" = "1" ]; then
  exit 0
fi

PAYLOAD="$(cat)"
TOOL="$(printf '%s' "$PAYLOAD" | jq -r '.tool_name // .tool // "unknown"')"

# safe_extract: jq -R reads stdin as raw string, fromjson parses JSON
safe_extract() { printf '%s' "$PAYLOAD" | jq -R -r "$1"; }

case "$TOOL" in
  write_file|patch)
    P="$(safe_extract 'try (fromjson | .args.path // "") catch ""')"
    if [ -z "$P" ]; then
      exit 0
    fi

    # Check if path is in allowed roots
    ALLOWED=$(deterministic-agent preflight write_file - < <(jq -n --arg path "$P" '{path: $path}') 2>&1)
    RC=$?
    if [ "$RC" -eq 0 ]; then
      exit 0
    fi

    # Not in allowed roots → ask user for confirmation
    # The desktop app will render a dialog from this message
    DETAIL="$(printf '%s' "$ALLOWED" | jq -r '.detail // "path outside allowed roots"')"
    jq -nc --arg msg "Allow write to $P?  '$DETAIL'" '{action: "continue", message: ("deterministic-agent wants to write: " + $msg + " (click to approve, or ignore to cancel)")}'
    echo "exit=continue (waiting for user)" >&2
    ;;

  terminal)
    C="$(safe_extract 'try (fromjson | .args.command // "") catch ""')"
    if [ -z "$C" ]; then
      exit 0
    fi

    NETWORK_ALLOW=$(deterministic-agent preflight terminal - < <(jq -n --arg cmd "$C" '{command: $cmd}') 2>&1)
    RC=$?
    if [ "$RC" -eq 0 ]; then
      exit 0
    fi

    # Terminal command blocked (e.g., curl to unknown host) → block (security)
    DETAIL="$(printf '%s' "$NETWORK_ALLOW" | jq -r '.detail // "network call blocked"')"
    jq -nc --arg msg "$DETAIL" '{action: "block", message: ("deterministic-agent: " + $msg)}'
    ;;

  browser)
    U="$(safe_extract 'try (fromjson | .args.url // "") catch ""')"
    if [ -z "$U" ]; then
      exit 0
    fi
    H="$(printf '%s' "$U" | jq -R -r 'split("/")[2] // ""')"

    BROWSER_ALLOW=$(deterministic-agent preflight browser - < <(jq -n --arg host "$H" '{host: $host}') 2>&1)
    RC=$?
    if [ "$RC" -eq 0 ]; then
      exit 0
    fi

    DETAIL="$(printf '%s' "$BROWSER_ALLOW" | jq -r '.detail // "unknown host"')"
    jq -nc --arg msg "$DETAIL" '{action: "block", message: ("deterministic-agent: " + $msg)}'
    ;;

  process_kill)
    PID="$(safe_extract 'try (fromjson | .args.pid // 0) catch 0')"
    if [ "$PID" -eq 0 ]; then
      exit 0
    fi

    # Process kills should always prompt user (rarely needed by LLMs)
    jq -nc --arg pid "$PID" '{action: "continue", message: ("deterministic-agent wants to kill PID " + $pid + ". Allow?")}'
    ;;

  delegate_task)
    # delegate_task is allowed by default; future: enforce subagent scope
    exit 0
    ;;

  *)
    exit 0
    ;;
esac