# Start uvicorn in background (one instance on port 8000, with --reload)
$ErrorActionPreference = "SilentlyContinue"
$port = 8000
$root = $PSScriptRoot
$logFile = Join-Path $root "uvicorn.log"
$errFile = Join-Path $root "uvicorn.err.log"
$pidFile = Join-Path $root ".uvicorn.pid"

# Already running?
if (Test-Path $pidFile) {
    $oldPid = Get-Content $pidFile -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue)) {
        Write-Host "Already running (PID $oldPid). http://127.0.0.1:$port"
        Write-Host "To restart: .\restart.ps1"
        exit 0
    }
}

# Clean ports
8000, 8001, 8002, 8003 | ForEach-Object {
    Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
        }
}
Start-Sleep -Seconds 1

Set-Location $root
$proc = Start-Process python `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$port", "--reload" `
    -WorkingDirectory $root `
    -WindowStyle Hidden `
    -PassThru `
    -RedirectStandardOutput $logFile `
    -RedirectStandardError $errFile

$proc.Id | Set-Content $pidFile
Write-Host "Started in background (PID $($proc.Id))"
Write-Host "URL:  http://127.0.0.1:$port"
Write-Host "Log:  $logFile"
Write-Host "Stop: .\stop.ps1  or  .\restart.ps1"
