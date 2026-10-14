#!/bin/sh
# One-step onboarding for AI-Performance-Testing.
#
#   curl -fsSL https://raw.githubusercontent.com/henrikrexed/AI-Performance-Testing/main/install.sh | sh
#
# Fetches the repo (into ./AI-Performance-Testing, or a chosen dir) and runs
# `engine/cli.py init`, which installs the skills into your coding agent's skills
# directory (default ~/.claude/skills) and verifies them. Two commands total: this,
# then the guided flow it prints. Pure POSIX sh; no root required.
#
# Env overrides:
#   AIPT_REPO   git URL        (default: the public GitHub repo)
#   AIPT_REF    branch/tag     (default: main)
#   AIPT_DIR    checkout dir   (default: ./AI-Performance-Testing)
#   AIPT_DEST   skills dest    (passed to `init --dest`; default ~/.claude/skills)
set -eu

REPO="${AIPT_REPO:-https://github.com/henrikrexed/AI-Performance-Testing.git}"
REF="${AIPT_REF:-main}"
DIR="${AIPT_DIR:-AI-Performance-Testing}"

PY="$(command -v python3 || command -v python || true)"
if [ -z "$PY" ]; then
  echo "install.sh: python3 is required (the engine is pure Python 3)." >&2
  exit 1
fi

# Fetch: prefer git clone; fall back to a tarball download when git is absent.
if [ -d "$DIR/.git" ]; then
  echo "install.sh: updating existing checkout in $DIR"
  git -C "$DIR" fetch --depth 1 origin "$REF"
  git -C "$DIR" checkout -q FETCH_HEAD
elif command -v git >/dev/null 2>&1; then
  echo "install.sh: cloning $REPO ($REF) into $DIR"
  git clone --depth 1 --branch "$REF" "$REPO" "$DIR"
else
  echo "install.sh: git not found — downloading tarball"
  TARURL="$(echo "$REPO" | sed 's/\.git$//')/archive/refs/heads/$REF.tar.gz"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$TARURL" -o /tmp/aipt.tar.gz
  elif command -v wget >/dev/null 2>&1; then
    wget -qO /tmp/aipt.tar.gz "$TARURL"
  else
    echo "install.sh: need git, curl, or wget to fetch the repo." >&2
    exit 1
  fi
  mkdir -p "$DIR"
  tar -xzf /tmp/aipt.tar.gz -C "$DIR" --strip-components=1
  rm -f /tmp/aipt.tar.gz
fi

cd "$DIR"
if [ -n "${AIPT_DEST:-}" ]; then
  "$PY" engine/cli.py init --dest "$AIPT_DEST"
else
  "$PY" engine/cli.py init
fi

echo ""
echo "install.sh: done. You are in $(pwd)."
