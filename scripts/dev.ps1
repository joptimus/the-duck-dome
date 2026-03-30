$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

# ── Setup (idempotent) ────────────────────────────────────────────────────────

Write-Host "==> Checking backend..."
if (-not (Test-Path "$RepoRoot\backend\.venv\Scripts\Activate.ps1")) {
    Write-Host "    Creating Python venv..."
    python -m venv "$RepoRoot\backend\.venv"
}
& "$RepoRoot\backend\.venv\Scripts\Activate.ps1"
pip install -e "$RepoRoot\backend[dev]" --quiet

Write-Host "==> Checking web dependencies..."
if (-not (Test-Path "$RepoRoot\apps\web\node_modules")) {
    Write-Host "    Installing npm packages..."
    Push-Location "$RepoRoot\apps\web"
    npm install --silent
    Pop-Location
}

Write-Host "==> Checking desktop dependencies..."
if (-not (Test-Path "$RepoRoot\apps\desktop\node_modules")) {
    Write-Host "    Installing npm packages..."
    Push-Location "$RepoRoot\apps\desktop"
    npm install --silent
    Pop-Location
}

# ── Kill stale processes on ports we need ─────────────────────────────────────

Write-Host "==> Rebuilding web frontend..."
Push-Location "$RepoRoot\apps\web"
npm run build
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    throw "Web build failed."
}
Pop-Location

foreach ($port in @(8000, 8200, 5173)) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($conn) {
        foreach ($c in $conn) {
            Write-Host "    Killing stale process on port $port (PID $($c.OwningProcess))..."
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Milliseconds 500
    }
}

# ── Run ───────────────────────────────────────────────────────────────────────

Write-Host "==> Starting DuckDome..."

$backend = Start-Process -NoNewWindow -PassThru -FilePath python -ArgumentList "-m", "uvicorn", "duckdome.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload" -WorkingDirectory "$RepoRoot\backend"

$web = Start-Process -NoNewWindow -PassThru -FilePath npm -ArgumentList "run", "dev" -WorkingDirectory "$RepoRoot\apps\web"

Write-Host "==> Waiting for Vite..."
$viteTimeout = 60
$viteElapsed = 0
do {
    Start-Sleep -Seconds 1
    $viteElapsed++
    if ($viteElapsed -ge $viteTimeout) {
        throw "Vite did not start within $viteTimeout seconds."
    }
    try { $null = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 1 -ErrorAction SilentlyContinue } catch {}
} until ((Test-NetConnection -ComputerName localhost -Port 5173 -WarningAction SilentlyContinue).TcpTestSucceeded)

$desktop = Start-Process -NoNewWindow -PassThru -FilePath npm -ArgumentList "run", "dev" -WorkingDirectory "$RepoRoot\apps\desktop"

Write-Host ""
Write-Host "    Backend  -> http://localhost:8000"
Write-Host "    Web UI   -> http://localhost:5173"
Write-Host "    Electron -> launching..."
Write-Host ""
Write-Host "    Press Ctrl+C to stop."
Write-Host ""

try {
    while (-not $backend.HasExited -and -not $web.HasExited) {
        Start-Sleep -Seconds 1
    }
} finally {
    Write-Host "`n==> Shutting down..."
    foreach ($proc in @($backend, $web, $desktop)) {
        if ($proc -and -not $proc.HasExited) {
            Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
        }
    }
}
