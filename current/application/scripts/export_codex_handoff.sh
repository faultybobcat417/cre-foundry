#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(
    dirname "${BASH_SOURCE[0]}"
  )/.."
  pwd
)"

cd "$ROOT"

STAMP="$(
  date -u +"%Y%m%dT%H%M%SZ"
)"

OUTPUT_ROOT="$ROOT/outputs/codex_handoff/$STAMP"

mkdir -p "$OUTPUT_ROOT"

COMMIT="$(
  git rev-parse HEAD
)"

SHORT_COMMIT="$(
  git rev-parse --short HEAD
)"

BRANCH="$(
  git branch --show-current
)"

LATEST_TAG="$(
  git describe \
    --tags \
    --abbrev=0 \
    2>/dev/null \
    || printf '%s' "none"
)"

git status --short \
  > "$OUTPUT_ROOT/git_status.txt"

git log \
  --oneline \
  --decorate \
  -30 \
  > "$OUTPUT_ROOT/recent_commits.txt"

git tag \
  --sort=-creatordate \
  > "$OUTPUT_ROOT/tags.txt"

git ls-files \
  > "$OUTPUT_ROOT/tracked_files.txt"

find \
  src \
  tests \
  config \
  docs \
  scripts \
  -type f \
  2>/dev/null |
  sort \
  > "$OUTPUT_ROOT/context_file_manifest.txt"

./scripts/verify.sh |
  tee "$OUTPUT_ROOT/verification.txt"

{
  echo "# CRE Foundry Live Codex Session"
  echo
  echo "Repository: $ROOT"
  echo "Branch: $BRANCH"
  echo "Commit: $COMMIT"
  echo "Short commit: $SHORT_COMMIT"
  echo "Latest tag: $LATEST_TAG"
  echo "Generated UTC: $STAMP"
  echo
  echo "The repository was fully verified immediately before this prompt was generated."
  echo
  cat \
    "$ROOT/docs/codex/CRE_FOUNDRY_CODEX_HANDOFF.md"
} > "$OUTPUT_ROOT/CODEX_PROMPT.md"

ARCHIVE_ITEMS=()

for item in \
  src \
  tests \
  config \
  docs \
  scripts \
  pyproject.toml \
  uv.lock
do
  if [ -e "$ROOT/$item" ]; then
    ARCHIVE_ITEMS+=(
      "$item"
    )
  fi
done

tar \
  -czf "$OUTPUT_ROOT/repo_context.tar.gz" \
  "${ARCHIVE_ITEMS[@]}"

shasum \
  -a 256 \
  "$OUTPUT_ROOT/repo_context.tar.gz" \
  > "$OUTPUT_ROOT/repo_context.tar.gz.sha256"

python3 - "$OUTPUT_ROOT" "$COMMIT" "$BRANCH" "$LATEST_TAG" "$STAMP" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

output_root = Path(
    sys.argv[1]
)

payload = {
    "bundle_version": "cre-foundry-codex-handoff-v1",
    "commit": sys.argv[2],
    "branch": sys.argv[3],
    "latest_tag": sys.argv[4],
    "generated_at_utc": sys.argv[5],
    "files": {
        "prompt": "CODEX_PROMPT.md",
        "verification": "verification.txt",
        "git_status": "git_status.txt",
        "recent_commits": "recent_commits.txt",
        "tags": "tags.txt",
        "tracked_files": "tracked_files.txt",
        "context_file_manifest": "context_file_manifest.txt",
        "context_archive": "repo_context.tar.gz",
        "context_archive_sha256": "repo_context.tar.gz.sha256",
    },
    "safety": {
        "operating_mode": "shadow",
        "outreach_eligible": False,
        "opportunity_ranked": False,
        "automatic_conclusions": False,
    },
}

(
    output_root
    / "bundle_manifest.json"
).write_text(
    json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
)
PY

if [ -s "$OUTPUT_ROOT/git_status.txt" ]; then
  echo "Repository was not clean during handoff generation."
  cat "$OUTPUT_ROOT/git_status.txt"
  exit 1
fi

test -s "$OUTPUT_ROOT/CODEX_PROMPT.md"
test -s "$OUTPUT_ROOT/verification.txt"
test -s "$OUTPUT_ROOT/repo_context.tar.gz"
test -s "$OUTPUT_ROOT/repo_context.tar.gz.sha256"
test -s "$OUTPUT_ROOT/bundle_manifest.json"

echo "$OUTPUT_ROOT"
