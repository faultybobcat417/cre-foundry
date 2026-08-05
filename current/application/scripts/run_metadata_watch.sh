#!/bin/zsh
set -euo pipefail

ROOT="/Users/alimehdi/Projects/comfiance/cre-foundry"
export HOME="/Users/alimehdi"
export VIRTUAL_ENV="$ROOT/.venv"
export PATH="$ROOT/.venv/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PYTHONUNBUFFERED=1
export DO_NOT_TRACK=1
export PREFECT_SERVER_ANALYTICS_ENABLED=false
export PREFECT_HOME="$ROOT/data/control/prefect"

cd "$ROOT"

mkdir -p "$ROOT/logs"
mkdir -p "$PREFECT_HOME"

STATUS_FILE="$ROOT/logs/launchd_metadata_watch.status.json"
STATUS_TEMP="$STATUS_FILE.tmp.$$"
STARTED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

set +e
"$ROOT/.venv/bin/cre-foundry" run profile --profile metadata_watch
EXIT_CODE=$?
set -e

ENDED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

cat > "$STATUS_TEMP" <<EOF
{
  "started_at": "$STARTED_AT",
  "ended_at": "$ENDED_AT",
  "exit_code": $EXIT_CODE,
  "profile": "metadata_watch"
}
EOF

mv "$STATUS_TEMP" "$STATUS_FILE"

exit "$EXIT_CODE"
