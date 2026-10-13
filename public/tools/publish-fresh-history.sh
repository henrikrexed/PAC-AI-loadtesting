#!/usr/bin/env bash
# publish-fresh-history.sh — fresh-history publish of the scanner-clean public tree
# to github.com/henrikrexed/AI-Performance-Testing (ISI-5760, plan §1/§8).
#
# WHY fresh-history: the working repo's 72 commits carry internal ISI ids and old
# commits still hold previously-scrubbed live-tenant/RUM data. Deleting at HEAD does
# NOT remove history. We therefore seed the public repo from a single orphan commit
# built ONLY from the clean tree — "no presentation/loadtests/research" is true by
# construction, and no internal history is ever pushed.
#
# Fails CLOSED:
#   * runs secret-scan.sh on the staged tree and aborts on any hit;
#   * never pushes without an explicit --push flag AND a write token in the env;
#   * default mode is a dry run that stages + scans + prints what WOULD be pushed.
#
# Usage:
#   bash tools/publish-fresh-history.sh                 # dry run (stage + scan, no push)
#   GITHUB_TOKEN=xxx bash tools/publish-fresh-history.sh --push
#   bash tools/publish-fresh-history.sh --src <dir>     # override source tree
#
# The write token (GITHUB_TOKEN) is board-provisioned (ISI-5760 blocker). Agents have
# no apiTokens.write; do NOT hard-code or commit a token.
set -euo pipefail

# ---- config -----------------------------------------------------------------
SRC_DEFAULT="$(cd "$(dirname "${0}")/.." && pwd)"   # the public/ tree by default
SRC="$SRC_DEFAULT"
REMOTE_URL="https://github.com/henrikrexed/AI-Performance-Testing.git"
BRANCH="main"
COMMIT_MSG="Initial public release of the AI-Performance-Testing toolkit"
DO_PUSH=0

# Internal-only files that must NEVER reach the public repo even if present in SRC.
EXCLUDES=(
  ".git"
  ".isi5735-pending"      # patch/bundle staging for the working repo
  "SCRUB-REPORT.md"       # references internal ISI ids / scrub provenance
  "tools/publish-fresh-history.sh"  # this internal publish tool is not a public artifact
  "__pycache__"
  ".pytest_cache"
)

# ---- args -------------------------------------------------------------------
while [ $# -gt 0 ]; do
  case "$1" in
    --push)   DO_PUSH=1; shift ;;
    --src)    SRC="$2"; shift 2 ;;
    --remote) REMOTE_URL="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

echo "== publish-fresh-history =="
echo "source tree : $SRC"
echo "remote      : $REMOTE_URL"
echo "branch      : $BRANCH"
echo "mode        : $([ "$DO_PUSH" -eq 1 ] && echo PUSH || echo 'DRY RUN (no push)')"
echo

[ -d "$SRC" ] || { echo "ERROR: source tree not found: $SRC" >&2; exit 1; }

# ---- stage a clean copy -----------------------------------------------------
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
echo "staging clean tree -> $STAGE"

RSYNC_EX=()
for e in "${EXCLUDES[@]}"; do RSYNC_EX+=(--exclude "$e"); done
if command -v rsync >/dev/null 2>&1; then
  rsync -a "${RSYNC_EX[@]}" "$SRC"/ "$STAGE"/
else
  cp -a "$SRC"/. "$STAGE"/
  for e in "${EXCLUDES[@]}"; do rm -rf "$STAGE/$e"; done
fi

# ---- secret scan (fail closed) ---------------------------------------------
SCAN="$STAGE/tools/secret-scan.sh"
if [ -x "$SCAN" ] || [ -f "$SCAN" ]; then
  echo "running secret-scan on staged tree..."
  if ! bash "$SCAN"; then
    echo "ABORT: secret-scan failed on the staged tree — nothing published." >&2
    exit 1
  fi
else
  echo "ABORT: tools/secret-scan.sh missing from staged tree — refusing to publish blind." >&2
  exit 1
fi
echo

# ---- build orphan single-commit history ------------------------------------
echo "building fresh orphan history..."
git -C "$STAGE" init -q -b "$BRANCH"
git -C "$STAGE" add -A
# Deterministic authorship; override via GIT_AUTHOR_* / GIT_COMMITTER_* in env.
git -C "$STAGE" -c user.name="${GIT_AUTHOR_NAME:-Henrik Rexed}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-henrik@perfbytes.com}" \
    commit -q -m "$COMMIT_MSG"

echo
echo "fresh history (single commit):"
git -C "$STAGE" log --oneline
echo
echo "files to publish:"
git -C "$STAGE" ls-files | sed 's/^/  /'
echo

# ---- push -------------------------------------------------------------------
if [ "$DO_PUSH" -ne 1 ]; then
  echo "DRY RUN complete. Tree staged + scanned clean. Re-run with --push and a token to publish."
  exit 0
fi

if [ -z "${GITHUB_TOKEN:-}" ]; then
  echo "ABORT: --push given but GITHUB_TOKEN is empty." >&2
  echo "       The public-repo write token is board-provisioned (ISI-5760 blocker)." >&2
  exit 1
fi

# Inject token into the push URL without persisting it to disk.
PUSH_URL="$(printf '%s' "$REMOTE_URL" | sed -E "s#https://#https://x-access-token:${GITHUB_TOKEN}@#")"
git -C "$STAGE" remote add origin "$PUSH_URL"
echo "pushing orphan $BRANCH to $REMOTE_URL (force, fresh history)..."
git -C "$STAGE" push --force origin "$BRANCH"
echo "PUBLISHED: $REMOTE_URL @ $BRANCH"
