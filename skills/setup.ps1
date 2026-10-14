# skills/setup.ps1 — one command installs every pinned skill dependency (WS-B, ISI-5927).
# PowerShell 5.1+ / 7+. Run: pwsh skills/setup.ps1  (or right-click > Run with PowerShell)
# After it, run skills/preflight.ps1 to verify everything actually loads.
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

function Say($m) { Write-Host "setup: $m" }
function Die($m) { Write-Error "setup: $m"; exit 1 }

if (-not (Get-Command python3 -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Die "python not found. Install Python 3.10+ from https://python.org (check 'Add to PATH')."
}
$py = if (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Die "npm not found. Install Node.js >= 20 from https://nodejs.org."
}

# ---- Python pins ------------------------------------------------------------
$reqs = Get-ChildItem "$here\*\requirements.txt" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
if ($reqs) {
    Say "installing python pins ($(& $py --version))"
    & $py -m pip install --disable-pip-version-check @reqs
    if ($LASTEXITCODE -ne 0) { Die "pip install failed — see output above." }
} else {
    Say "no python requirements.txt found (unexpected)"
}

# ---- Renderer skills: verify committed lockfiles via npm ci -----------------
Get-ChildItem "$here\*\package.json" -ErrorAction SilentlyContinue | ForEach-Object {
    $dir = Split-Path -Parent $_.FullName
    $name = Split-Path -Leaf $dir
    if (Test-Path "$dir\package-lock.json") {
        Push-Location $dir
        & npm ci --silent --no-audit --no-fund | Out-Null
        Pop-Location
        Say "npm ci ok: $name"
    } else {
        Write-Warning "no package-lock.json in $name — generate with: cd skills/$name; npm install --package-lock-only"
    }
}

# Runtime tool CLIs (k6, jmeter, gatling, locust, dtctl) are intentionally NOT
# installed here — preflight.ps1 probes them with exact install commands.
Say "done. verify with: pwsh $here\preflight.ps1"
