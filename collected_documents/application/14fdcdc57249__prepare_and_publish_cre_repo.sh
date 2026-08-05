#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="${REPO_NAME:-cre-foundry}"
REPO_DESCRIPTION="${REPO_DESCRIPTION:-Institutionally engineered commercial real estate decision intelligence, research, validation, governance, and implementation.}"
COLLECTOR="${COLLECTOR:-$HOME/Downloads/collect_all_cre_agent_work_from_mac.sh}"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT_BASE="${OUT_BASE:-$HOME/Desktop/CRE-Foundry-Consolidation-$STAMP}"

fail() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

echo "== CRE Foundry prepare and publish =="

command -v git >/dev/null 2>&1 || fail "Git is missing."
command -v python3 >/dev/null 2>&1 || fail "Python 3 is missing."

if ! command -v gh >/dev/null 2>&1; then
  command -v brew >/dev/null 2>&1 || fail "GitHub CLI and Homebrew are missing."
  brew install gh
fi

[[ -f "$COLLECTOR" ]] || fail "Collector not found: $COLLECTOR"
chmod +x "$COLLECTOR"

if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth login --hostname github.com --git-protocol https --web
fi
gh auth setup-git --hostname github.com

GH_LOGIN="$(gh api user --jq '.login')"
GH_ID="$(gh api user --jq '.id')"
FULL_REPO="$GH_LOGIN/$REPO_NAME"

echo "GitHub account: $GH_LOGIN"
echo "Target repo:    $FULL_REPO"
echo "Output folder:  $OUT_BASE"

OUT_BASE="$OUT_BASE" bash "$COLLECTOR" | tee "$OUT_BASE-terminal.log"

PUBLIC_REPO="$OUT_BASE/PUBLIC_REPO"
PRIVATE_ARCHIVE="$OUT_BASE/PRIVATE_ARCHIVE"

[[ -d "$PUBLIC_REPO/.git" ]] || fail "Organized public Git repo was not created."
[[ -f "$PUBLIC_REPO/00_INDEX/PUBLICATION_BLOCKERS.md" ]] || fail "Publication report is missing."

echo
echo "== Publication report =="
sed -n '1,260p' "$PUBLIC_REPO/00_INDEX/PUBLICATION_BLOCKERS.md"

SCAN="$PUBLIC_REPO/reports/FINAL_PUBLIC_SCAN.json"
ERRORS="$PUBLIC_REPO/reports/COPY_ERRORS.json"
WARNINGS="$PUBLIC_REPO/reports/WARNINGS.json"

read -r CRITICAL COPY_ERRORS PII_WARNINGS <<<"$(
python3 - "$SCAN" "$ERRORS" "$WARNINGS" <<'PY'
import json
import sys
from pathlib import Path

def load(path):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []

critical = load(sys.argv[1])
errors = load(sys.argv[2])
warnings = load(sys.argv[3])
pii = [
    item for item in warnings
    if set(item.get("findings", [])).intersection({"email", "phone"})
]
print(len(critical), len(errors), len(pii))
PY
)"

echo
echo "Critical public findings: $CRITICAL"
echo "Copy errors:              $COPY_ERRORS"
echo "Email/phone warnings:     $PII_WARNINGS"

[[ "$CRITICAL" -eq 0 ]] || fail "Critical findings remain. Review $SCAN"
[[ "$COPY_ERRORS" -eq 0 ]] || fail "Copy errors remain. Review $ERRORS"
[[ "$PII_WARNINGS" -eq 0 ]] || fail "Possible PII requires review. Review $WARNINGS"

cd "$PUBLIC_REPO"
git config user.name "$GH_LOGIN"
git config user.email "${GH_ID}+${GH_LOGIN}@users.noreply.github.com"
git add -A

if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  git commit -m "Consolidate CRE Foundry agent work"
elif ! git diff --cached --quiet; then
  git commit -m "Finalize CRE Foundry consolidated snapshot"
fi

git branch -M main
[[ -z "$(git status --porcelain)" ]] || fail "Local public repository is not clean."

if gh repo view "$FULL_REPO" >/dev/null 2>&1; then
  fail "GitHub repository already exists: $FULL_REPO"
fi

gh repo create "$FULL_REPO" \
  --public \
  --description "$REPO_DESCRIPTION" \
  --source="$PUBLIC_REPO" \
  --remote=origin \
  --push

gh repo edit "$FULL_REPO" \
  --enable-issues \
  --enable-wiki=false \
  --delete-branch-on-merge \
  --enable-squash-merge \
  --enable-rebase-merge \
  --enable-merge-commit=false \
  --add-topic commercial-real-estate \
  --add-topic decision-intelligence \
  --add-topic machine-learning \
  --add-topic causal-inference \
  --add-topic operations-research \
  --add-topic model-risk \
  --add-topic python

set +e
gh repo edit "$FULL_REPO" \
  --enable-secret-scanning \
  --enable-secret-scanning-push-protection
set -e

LIVE_URL="$(gh repo view "$FULL_REPO" --json url --jq '.url')"

echo
echo "============================================================"
echo "CRE FOUNDRY PUBLIC REPOSITORY READY"
echo "============================================================"
echo "Live URL:        $LIVE_URL"
echo "Public source:   $PUBLIC_REPO"
echo "Private archive: $PRIVATE_ARCHIVE"

open "$LIVE_URL"
