#!/usr/bin/env bash
# secret-scan.sh — automated pre-publish scan for the AI-Performance-Testing repo.
# Fails (exit 1) on any hit. Run from the repo root:  bash tools/secret-scan.sh
#
# Catches: Dynatrace token formats, tenant/env URLs, private IPs, generic
# credential-looking assignments, internal workspace identifiers, internal
# issue-tracker ids, the internal platform name, and internal project-name
# variants. Reuses the SCRUB-REPORT methodology; wired as a CI gate in
# .github/workflows/secret-scan.yml.
set -uo pipefail

ROOT="$(cd "$(dirname "${0}")/.." && pwd)"
# This gate scans exactly the tree that ships to the public repo. The authority on
# "what ships" is tools/publish-fresh-history.sh, which stages a clean copy minus a
# set of internal-only files and THEN runs this scanner. We mirror that same
# non-shipping set here so a standalone run of the gate reflects the publishable
# reality: in the public repo these files do not exist, so CI there scans a clean
# tree. Keep this list in lockstep with publish-fresh-history.sh EXCLUDES.
#   * generated/cache dirs (out, runs, node_modules, caches) — never shipped;
#   * .isi5735-pending — local publish-courier (patch/bundle/apply notes), internal refs;
#   * publish-fresh-history.sh — the internal publish tool itself, not a public artifact;
#   * SCRUB-REPORT.md — internal scrub provenance (issue ids), not a public artifact.
EXCLUDES=(
  --exclude-dir=.git --exclude-dir=out --exclude-dir=runs
  --exclude-dir=node_modules --exclude-dir=__pycache__ --exclude-dir=.pytest_cache
  --exclude-dir=.isi5735-pending
  --exclude=publish-fresh-history.sh
  --exclude=SCRUB-REPORT.md
)
# Never flag the scanner on its own pattern literals.
SELF='tools/secret-scan\.sh'

hit() { echo "SECRET-SCAN HIT [$1] $2"; FOUND=1; }
FOUND=0

# 1. Dynatrace token formats (classic dt0c01/dt0s01/dt0a01 + any long bearer-ish blob)
while IFS=: read -r file line text; do
  hit "dt-token" "$file:$line: $text"
done < <(grep -rEn "${EXCLUDES[@]}" -- 'dt0[acs]0[12][A-Za-z0-9]{10,}' "$ROOT" 2>/dev/null)

# 2. Real tenant/environment URLs (placeholder your-environment / your-env is allowed)
while IFS=: read -r file line text; do
  hit "tenant-url" "$file:$line: $text"
done < <(grep -rEn "${EXCLUDES[@]}" -- 'https://[A-Za-z0-9-]+\.(live|dev)\.dynatrace\.com' "$ROOT" 2>/dev/null \
        | grep -v 'your-environment\|your-env' )

# 3. Private IPs (RFC1918) — localhost/127.0.0.1 allowed
while IFS=: read -r file line text; do
  hit "private-ip" "$file:$line: $text"
done < <(grep -rEn "${EXCLUDES[@]}" -- '(^|[^0-9])(10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)([^0-9]|$)' "$ROOT" 2>/dev/null \
        | grep -v '127\.0\.0\.1' )

# 4. Generic credential-looking assignments (token/secret/password/api key with a value)
while IFS=: read -r file line text; do
  hit "credential" "$file:$line: $text"
done < <(grep -rEIn "${EXCLUDES[@]}" -- '(api[_-]?token|secret|password|apikey|api[_-]?key)["'"'"']?[[:space:]]*[:=][[:space:]]*["'"'"']?[A-Za-z0-9+/_-]{16,}' "$ROOT" 2>/dev/null \
        | grep -iv 'DT_API_TOKEN=\|your-\|<your\|example\|placeholder\|\.env\.example' )

# 5. Known internal-namespace identifiers from the source workspace (tenant/cluster ids)
while IFS=: read -r file line text; do
  hit "internal-id" "$file:$line: $text"
done < <(grep -rEn "${EXCLUDES[@]}" -- 'oat05854|wkf10640|smartfreight|openclaw' "$ROOT" 2>/dev/null \
        | grep -v "$SELF" )

# 6. Internal issue-tracker ids (e.g. ISI-1234)
while IFS=: read -r file line text; do
  hit "issue-id" "$file:$line: $text"
done < <(grep -rEn "${EXCLUDES[@]}" -- 'ISI-[0-9]+' "$ROOT" 2>/dev/null \
        | grep -v "$SELF" )

# 7. Internal platform name
while IFS=: read -r file line text; do
  hit "platform-name" "$file:$line: $text"
done < <(grep -rEin "${EXCLUDES[@]}" -- 'paperclip' "$ROOT" 2>/dev/null \
        | grep -v "$SELF" )

# 8. Internal project-name variants (PAC-AI-Loadtest and friends: PAC-AI-loadtesting,
#    PAC_AI_Loadtest, PACAILoad…). Anchored on PAC+AI+load so "namespace"/"PAC toolkit"
#    etc. do not false-positive.
while IFS=: read -r file line text; do
  hit "project-name" "$file:$line: $text"
done < <(grep -rEin "${EXCLUDES[@]}" -- 'PAC[-_ ]?AI[-_ ]?load' "$ROOT" 2>/dev/null \
        | grep -v "$SELF" )

if [ "$FOUND" -ne 0 ]; then
  echo "secret-scan: FAIL — clean the hits above before publishing."
  exit 1
fi
echo "secret-scan: PASS — no tokens, tenant URLs, private IPs, internal ids, issue ids, platform name, or project-name variants found."
