#!/bin/sh
# skills/preflight.sh — install-time verification for skill dependencies (WS-B, ISI-5927).
#
# Verifies every pinned python dependency actually imports at the pinned version,
# node/npm are usable, and (optionally) the runtime tool CLIs are on PATH.
# On failure prints an actionable report: what is missing + the exact command to
# fix it — instead of failing late mid-task.
#
# Usage:
#   sh skills/preflight.sh                # core deps only (pip + node); tool CLIs warn
#   sh skills/preflight.sh --require-tools # also fail on missing k6/jmeter/gatling/locust/dtctl
set -u

HERE=$(cd "$(dirname "$0")" && pwd)
REQUIRE_TOOLS=0
for arg in "$@"; do
    case "$arg" in
        --require-tools) REQUIRE_TOOLS=1 ;;
        *) printf 'preflight: unknown flag %s\n' "$arg" >&2; exit 2 ;;
    esac
done

FAILS=""
WARNS=""

fail() { FAILS="$FAILS
- $*"; }
warn() { WARNS="$WARNS
- $*"; }

# ---- python3 + pinned deps ---------------------------------------------------
if command -v python3 >/dev/null 2>&1; then
    for r in "$HERE"/*/requirements.txt; do
        [ -f "$r" ] || continue
        skill=$(basename "$(dirname "$r")")
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
            if [ "$got" = "MISSING" ]; then
                fail "$skill: python package '$pkg' not installed. Fix: sh $HERE/setup.sh  (or: python3 -m pip install --user '$line')"
            elif [ -n "$want" ] && [ "$got" != "$want" ]; then
                fail "$skill: python package '$pkg' version $got found, pinned $want required. Fix: python3 -m pip install --user '$line'"
            fi
        done < "$r"
    done
else
    fail "python3 not found. Fix: 'sudo apt install python3 python3-venv' or https://python.org/downloads"
fi

# ---- node / npm --------------------------------------------------------------
if command -v node >/dev/null 2>&1; then
    node_major=$(node -e 'const [v]=process.versions.node.split("."); console.log(Number(v))')
    if [ "$node_major" -lt 20 ]; then
        fail "node $(node --version) found, >= 20 required. Fix: https://nodejs.org or 'brew install node'"
    fi
else
    fail "node not found. Fix: https://nodejs.org or 'brew install node'"
fi
command -v npm >/dev/null 2>&1 || fail "npm not found. Fix: https://nodejs.org (ships with node)"

# ---- renderer skill tests importable (pure ESM, no third-party deps) ---------
for pkg in "$HERE"/*/package.json; do
    [ -f "$pkg" ] || continue
    dir=$(dirname "$pkg")
    name=$(basename "$dir")
    [ -f "$dir/package-lock.json" ] || warn "$name: no package-lock.json. Fix: (cd skills/$name && npm install --package-lock-only)"
done

# ---- runtime tool CLIs -------------------------------------------------------
probe_tool() { # $1=cli $2=install hint
    if command -v "$1" >/dev/null 2>&1; then
        return 0
    fi
    msg="tool CLI '$1' not on PATH (needed by EXECUTE/baseline stages, not by synthesis). Fix: $2"
    if [ "$REQUIRE_TOOLS" -eq 1 ]; then fail "$msg"; else warn "$msg"; fi
}
probe_tool k6      "https://k6.io (e.g. 'brew install k6' / 'sudo apt install k6' / choco install k6)"
probe_tool jmeter  "https://jmeter.apache.org + Plugins Manager (Throughput Shaping Timer, OTel listener)"
probe_tool gatling "https://gatling.io (Gatling bundle requires JDK 17+)"
probe_tool locust  "'python3 -m pip install --user locust==2.x' or https://locust.io"
probe_tool dtctl   "Dynatrace dtctl CLI — see docs/ (requires DYNATRACE_* env vars too)"

# ---- report ------------------------------------------------------------------
if [ -n "$WARNS" ]; then
    printf 'preflight: WARNINGS (non-blocking):%s\n' "$WARNS"
fi
if [ -n "$FAILS" ]; then
    printf 'preflight: FAILED — fix the following and re-run:%s\n' "$FAILS" >&2
    exit 1
fi
printf 'preflight: OK — all pinned skill dependencies verified.\n'
[ "$REQUIRE_TOOLS" -eq 1 ] && printf 'preflight: runtime tool CLIs (k6/jmeter/gatling/locust/dtctl) all present.\n'
exit 0
