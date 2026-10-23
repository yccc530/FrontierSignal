param([switch]$SkipDatabase)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
function Invoke-Checked {
    param([string]$Command, [string[]]$Arguments)
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed: $Command" }
}
Invoke-Checked "uv" @("sync", "--locked")
Invoke-Checked "uv" @("run", "python", "scripts/setup.py")
if (-not $SkipDatabase) {
    Invoke-Checked "docker" @("compose", "up", "-d", "db")
}
Invoke-Checked "uv" @("run", "python", "scripts/wait_db.py")
Invoke-Checked "uv" @("run", "alembic", "upgrade", "head")
Invoke-Checked "npm.cmd" @("--prefix", "frontend", "ci")
Invoke-Checked "npm.cmd" @("--prefix", "frontend", "run", "build")
Write-Host "FrontierSignal: http://localhost:8000 (Ctrl+C to stop the web service)"
Invoke-Checked "uv" @("run", "uvicorn", "frontiersignal.main:app", "--host", "127.0.0.1", "--port", "8000")
