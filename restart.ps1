# Restart uvicorn: kill ports 8000-8003, start only on 8000 (foreground)
# Tip: use .\start.ps1 to run in background; only keep ONE instance running.
$ErrorActionPreference = "SilentlyContinue"
$port = 8000
$ports = 8000, 8001, 8002, 8003

Write-Host "Cleaning ports $($ports -join ', ')..."

foreach ($p in $ports) {
    Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            $procId = $_.OwningProcess
            if ($procId -gt 0) {
                Write-Host "  Stop port $p PID $procId"
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                taskkill /F /PID $procId 2>$null
            }
        }
}

Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object {
        $_.CommandLine -like '*uvicorn*app.main:app*' -or
        $_.CommandLine -like '*multiprocessing.spawn*spawn_main*'
    } |
    ForEach-Object {
        Write-Host "  Stop python PID $($_.ProcessId)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        taskkill /F /T /PID $_.ProcessId 2>$null
    }

Start-Sleep -Seconds 2

$remaining = Get-NetTCPConnection -LocalPort $ports -State Listen -ErrorAction SilentlyContinue
if ($remaining) {
    Write-Host ""
    Write-Host "WARN: ports still in use. End python.exe in Task Manager, then retry." -ForegroundColor Yellow
    $remaining | Select-Object LocalPort, OwningProcess -Unique | Format-Table -AutoSize
    exit 1
}

Set-Location $PSScriptRoot
Write-Host ""
Write-Host "Starting http://127.0.0.1:$port" -ForegroundColor Green
python -m uvicorn app.main:app --host 127.0.0.1 --port $port --reload
