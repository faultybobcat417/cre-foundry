#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python scripts/validate_os.py
python scripts/probe_codex_capabilities.py
python scripts/select_next_task.py
python scripts/compile_task_context.py

CAP="$ROOT/artifacts/codex_capabilities.json"
if ! python - "$CAP" <<'PY'
import json, sys
data=json.load(open(sys.argv[1]))
raise SystemExit(0 if data.get("codex_found") else 1)
PY
then
  echo "Codex executable not found. Use interactive mode or install/configure Codex, then rerun the capability probe." >&2
  exit 2
fi

PROMPT="$ROOT/FINAL_CODEX_LAUNCH_PROMPT_v2.2.md"
PACKET="$ROOT/artifacts/context/current_task_packet.md"
OUT="$ROOT/artifacts/headless"
mkdir -p "$OUT"

HELP="$(codex exec --help 2>&1 || true)"
ARGS=(exec --json -o "$OUT/last_message.txt")
if grep -q -- "--output-schema" <<<"$HELP"; then
  ARGS+=(--output-schema "$ROOT/schemas/task_result.schema.json")
fi

{
  cat "$PROMPT"
  printf '\n\n# Current compiled task context\n'
  cat "$PACKET"
} | codex "${ARGS[@]}" -
