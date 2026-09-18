#!/usr/bin/env bash
# cron-triggered replay check. Wire this from a cron job:
#   0 * * * * deterministic-agent replay "$SKILL" "$INPUTS" "$OUTPUT" \
#     && exit 0 || (echo "regression" | mail -s "dagent replay" you)
set -euo pipefail
exec deterministic-agent replay "$@"
