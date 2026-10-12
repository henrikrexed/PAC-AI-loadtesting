#!/usr/bin/env bash
# secret-scan.sh — automated pre-publish scan for the AI-Performance-Testing repo.
# Fails (exit 1) on any hit. Run from the repo root:  bash tools/secret-scan.sh
#
# Catches: Dynatrace token formats, tenant/env URLs, private IPs, internal
# workspace identifiers, and generic credential-looking assignments.
set -uo pipefail

ROOT="$(cd "$(dirname "${0}")/.." && pwd)"
EXCLUDES=(--exclude-dir=.git --exclude-dir=out --exclude-dir=runs --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.pytest_cache)

hit() { echo "SECRET-SCAN HIT [$1] $2"; FOUND=1; }
FOUND=0

# 1. Dynatrace token formats (classic dt0c01/dt0s01/dt0a01 + any long bearer-ish blob)
while IFS=: read -r file line text; do
  hit "dt-token" "$file:$line: $text"
done < <(grep -rEn ${EXCLUDES[@]} -- 'dt0[acs]0[12][A-Za-z0-9]{10,}' "$ROOT" 2>/dev/null)

# 2. Real tenant/environment URLs (placeholder your-environment / your-env is allowed)
while IFS=: read -r file line text; do
  hit "tenant-url" "$file:$line: $text"
done < <(grep -rEn ${EXCLUDES[@]} -- 'https://[A-Za-z0-9-]+\.(live|dev)\.dynatrace\.com' "$ROOT" 2>/dev/null \
        | grep -v 'your-environment\|your-env' )

# 3. Private IPs (RFC1918) — localhost/127.0.0.1 allowed
while IFS=: read -r file line text; do
  hit "private-ip" "$file:$line: $text"
done < <(grep -rEn ${EXCLUDES[@]} -- '(^|[^0-9])(10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)([^0-9]|$)' "$ROOT" 2>/dev/null \
        | grep -v '127\.0\.0\.1' )

# 4. Generic credential-looking assignments (token/secret/password/api key with a value)
while IFS=: read -r file line text; do
  hit "credential" "$file:$line: $text"
done < <(grep -rEIn ${EXCLUDES[@]} -- '(?i)(api[_-]?token|secret|password|apikey|api[_-]?key)["'"'"']?\s*[:=]\s*["'"'"']?[A-Za-z0-9+/_-]{16,}' "$ROOT" 2>/dev/null \
        | grep -v 'DT_API_TOKEN=\|your-\|<your\|example\|placeholder\|\.env\.example' )

# 5. Known internal-namespace identifiers (add yours before publishing; self-excluded)
while IFS=: read -r file line text; do
  hit "internal-id" "$file:$line: $text"
done < <(grep -rEn ${EXCLUDES[@]} -- 'oat05854|wkf10640|smartfreight|openclaw|ISI-[0-9]+' "$ROOT" 2>/dev/null \
        | grep -v 'tools/secret-scan\.sh' )

if [ "$FOUND" -ne 0 ]; then
  echo "secret-scan: FAIL — clean the hits above before publishing."
  exit 1
fi
echo "secret-scan: PASS — no tokens, tenant URLs, private IPs, or internal IDs found."
