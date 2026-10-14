# skills/preflight.ps1 — install-time verification for skill dependencies (WS-B, ISI-5927).
# PowerShell 5.1+ / 7+. Verifies pinned python deps import at the pinned version,
# node/npm are usable, and (with -RequireTools) the runtime tool CLIs are on PATH.
# Prints an actionable report (what is missing + exact fix) instead of failing late.
param([switch]$RequireTools)
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$fails = New-Object System.Collections.Generic.List[string]
$warns = New-Object System.Collections.Generic.List[string]

# ---- python + pinned deps ----------------------------------------------------
$py = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } elseif (Get-Command python -ErrorAction SilentlyContinue) { "python" } else { $null }
if ($py) {
    Get-ChildItem "$here\*\requirements.txt" -ErrorAction SilentlyContinue | ForEach-Object {
        $skill = Split-Path -Leaf (Split-Path -Parent $_.FullName)
        Get-Content $_.FullName | ForEach-Object {
            $line = $_.Trim()
            if ($line -and -not $line.StartsWith('#')) {
                $pkg = ($line -split '=')[0]
                $want = if ($line -match '==(.+)$') { $Matches[1] } else { $null }
                $got = & $py -c "import importlib.metadata,sys
try: print(importlib.metadata.version(sys.argv[1]))
except importlib.metadata.PackageNotFoundError: print('MISSING')" $pkg 2>$null
                if ($got -eq 'MISSING' -or -not $got) {
                    $fails.Add("$skill python package '$pkg' not installed. Fix: pwsh skills\setup.ps1 (or: $py -m pip install `"$line`")")
                } elseif ($want -and ($got -ne $want)) {
                    $fails.Add("$skill python package '$pkg' version $got found, pinned $want required. Fix: $py -m pip install `"$line`"")
                }
            }
        }
    }
} else {
    $fails.Add("python not found. Fix: install Python 3.10+ from https://python.org (check 'Add to PATH').")
}

# ---- node / npm --------------------------------------------------------------
$node = Get-Command node -ErrorAction SilentlyContinue
if ($node) {
    $major = [int]((& node -e "console.log(Number(process.versions.node.split('.')[0]))"))
    if ($major -lt 20) { $fails.Add("node $((& node --version)) found, >= 20 required. Fix: https://nodejs.org") }
} else {
    $fails.Add("node not found. Fix: https://nodejs.org")
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { $fails.Add("npm not found. Fix: https://nodejs.org (ships with node)") }

# ---- lockfiles ---------------------------------------------------------------
Get-ChildItem "$here\*\package.json" -ErrorAction SilentlyContinue | ForEach-Object {
    $dir = Split-Path -Parent $_.FullName
    if (-not (Test-Path "$dir\package-lock.json")) {
        $warns.Add("$(Split-Path -Leaf $dir): no package-lock.json. Fix: cd skills/$(Split-Path -Leaf $dir); npm install --package-lock-only")
    }
}

# ---- runtime tool CLIs -------------------------------------------------------
function ProbeTool($cli, $hint) {
    if (Get-Command $cli -ErrorAction SilentlyContinue) { return }
    $msg = "tool CLI '$cli' not on PATH (needed by EXECUTE/baseline stages, not by synthesis). Fix: $hint"
    if ($RequireTools) { $fails.Add($msg) } else { $warns.Add($msg) }
}
ProbeTool k6      "https://k6.io (choco install k6 / winget install grafana.k6)"
ProbeTool jmeter  "https://jmeter.apache.org + Plugins Manager (Throughput Shaping Timer, OTel listener)"
ProbeTool gatling "https://gatling.io (requires JDK 17+)"
ProbeTool locust  "$py -m pip install locust==2.x or https://locust.io"
ProbeTool dtctl   "Dynatrace dtctl CLI — see docs/ (requires DYNATRACE_* env vars too)"

# ---- report ------------------------------------------------------------------
if ($warns.Count) { Write-Host "preflight: WARNINGS (non-blocking):"; $warns | ForEach-Object { Write-Host " - $_" } }
if ($fails.Count) {
    Write-Host "preflight: FAILED — fix the following and re-run:" -ForegroundColor Red
    $fails | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
    exit 1
}
Write-Host "preflight: OK — all pinned skill dependencies verified."
if ($RequireTools) { Write-Host "preflight: runtime tool CLIs (k6/jmeter/gatling/locust/dtctl) all present." }
exit 0
