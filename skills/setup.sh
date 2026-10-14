#!/bin/sh
# skills/setup.sh — one command installs every pinned skill dependency (WS-B, ISI-5927).
#
# Used standalone and by the WS-A installers. After it, run skills/preflight.sh
# to verify everything actually loads. Pure POSIX sh; no root required.
#
# Python deps: installed into the active virtualenv if any, else --user, else a
# dedicated skills/.venv is created (activation hint printed). Renderer skills
# have zero npm dependencies; `npm ci` verifies their committed lockfiles only.
set -eu

HERE=$(cd "$(dirname "$0")" && pwd)

say() { printf 'setup: %s\n' "$*"; }
die() { printf 'setup: ERROR: %s\n' "$*" >&2; exit 1; }

command -v python3 >/dev/null 2>&1 || die "python3 not found. Install Python 3.10+ (e.g. 'sudo apt install python3 python3-venv' or https://python.org/downloads)."
command -v npm >/dev/null 2>&1 || die "npm not found. Install Node.js >= 20 (e.g. https://nodejs.org or 'brew install node')."

REQS=""
for r in "$HERE"/*/requirements.txt; do
    [ -f "$r" ] || continue
    REQS="$REQS $r"
done

install_pip() { python3 -m pip install --disable-pip-version-check "$@" $REQS; }

# ---- Python pins ------------------------------------------------------------
pins_satisfied() { # all pinned packages import at the pinned versions
    for r in $REQS; do
        while IFS= read -r line; do
            case "$line" in
                \#*|"") continue ;;
            esac
            pkg=$(printf '%s' "$line" | cut -d= -f1)
            want=$(printf '%s' "$line" | sed -n 's/.*==\(.*\)$/\1/p')
            got=$(python3 - "$pkg" 2>/dev/null <<'PY'
import importlib.metadata, sys
try:
    print(importlib.metadata.version(sys.argv[1]))
except importlib.metadata.PackageNotFoundError:
    print("MISSING")
PY
)
            [ "$got" != "MISSING" ] || return 1
            [ -z "$want" ] || [ "$got" = "$want" ] || return 1
        done < "$r"
    done
    return 0
}

if [ -n "${VIRTUAL_ENV:-}" ]; then
    if pins_satisfied; then say "python pins already satisfied in active virtualenv — skipping pip"; else
        say "installing python pins into active virtualenv ($VIRTUAL_ENV)"
        install_pip
    fi
elif pins_satisfied; then
    say "python pins already satisfied — skipping pip (no install needed)"
else
    TMPLOG=$(mktemp)
    if install_pip --user >"$TMPLOG" 2>&1; then
        say "installed python pins into user site-packages"
    else
        say "user install unavailable (PEP 668 or restricted site) — creating $HERE/.venv"
        python3 -m venv "$HERE/.venv" || { cat "$TMPLOG" >&2; die "cannot create venv (install python3-venv)"; }
        "$HERE/.venv/bin/python" -m pip install --quiet --disable-pip-version-check --upgrade pip
        "$HERE/.venv/bin/python" -m pip install --disable-pip-version-check $REQS
        say "installed python pins into skills/.venv — activate with: . $HERE/.venv/bin/activate"
    fi
    rm -f "$TMPLOG"
fi

# ---- Renderer skills: verify committed lockfiles via npm ci -----------------
for pkg in "$HERE"/*/package.json; do
    [ -f "$pkg" ] || continue
    dir=$(dirname "$pkg")
    name=$(basename "$dir")
    if [ -f "$dir/package-lock.json" ]; then
        (cd "$dir" && npm ci --silent --no-audit --no-fund >/dev/null)
        say "npm ci ok: $name"
    else
        say "WARN: no package-lock.json in $name — generate with: (cd skills/$name && npm install --package-lock-only)"
    fi
done

# Runtime tool CLIs (k6, jmeter, gatling, locust, dtctl) are intentionally NOT
# installed here — install methods differ per platform. preflight.sh probes each
# and prints the exact install command for anything missing.

say "done. verify with: sh $HERE/preflight.sh"
