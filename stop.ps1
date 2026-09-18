# Stop background uvicorn
$ErrorActionPreference = "SilentlyContinue"
$pidFile = Join-Path $PSScriptRoot ".uvicorn.pid"

if (Test-Path $pidFile) {
    $procId = Get-Content $pidFile
    if ($procId) {
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        taskkill /F /T /PID $procId 2>$null
    }
    Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
}

8000, 8001, 8002, 8003 | ForEach-Object {
    Get-NetTCPConnection -LocalPort $_ -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object {
            $procId = $_.OwningProcess
            if ($procId -gt 0) {
                Write-Host "  Stop port $_ PID $procId"
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

Write-Host "Stopped."
