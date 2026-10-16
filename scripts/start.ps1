param([int]$WorkerPort=8000, [int]$ServerPort=8080)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $workspace
foreach ($port in @($WorkerPort,$ServerPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use; stop the existing service or select other ports."
    }
}
New-Item -ItemType Directory -Force artifacts/logs | Out-Null
$python = Join-Path $workspace '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run the README installation steps first.' }
Push-Location ferderatedsystem
try {
    & .\gradlew.bat bootJar --no-daemon
    if ($LASTEXITCODE -ne 0) { throw 'Java build failed' }
} finally { Pop-Location }
$env:MINIFLS_WORKSPACE = $workspace
$env:MINIFLS_SERVER_PORT = "$ServerPort"
$env:MINIFLS_WORKER_URL = "http://127.0.0.1:$WorkerPort"
$env:MINIFLS_DATABASE = Join-Path $workspace 'artifacts/minifls.db'
$worker = Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','minifls.api:app','--host','127.0.0.1','--port',"$WorkerPort",'--workers','1') -WorkingDirectory $workspace -WindowStyle Hidden -PassThru -RedirectStandardOutput artifacts/logs/worker.log -RedirectStandardError artifacts/logs/worker-error.log
$server = Start-Process -FilePath 'java' -ArgumentList @('-Xmx512m','-jar','ferderatedsystem/build/libs/ferderatedsystem-0.0.1-SNAPSHOT.jar') -WorkingDirectory $workspace -WindowStyle Hidden -PassThru -RedirectStandardOutput artifacts/logs/server.log -RedirectStandardError artifacts/logs/server-error.log
@{worker=$worker.Id;server=$server.Id} | ConvertTo-Json | Set-Content artifacts/processes.json
Write-Output "Worker PID $($worker.Id), server PID $($server.Id). Logs: artifacts/logs"
for ($attempt=0; $attempt -lt 60; $attempt++) {
    try {
        $health = Invoke-RestMethod "http://127.0.0.1:$ServerPort/health"
        # Venv trên Windows có thể tạo process Python con; lưu PID thực sự đang lắng nghe cổng.
        $workerListener = Get-NetTCPConnection -LocalPort $WorkerPort -State Listen | Select-Object -First 1
        $serverListener = Get-NetTCPConnection -LocalPort $ServerPort -State Listen | Select-Object -First 1
        @{worker=$workerListener.OwningProcess;server=$serverListener.OwningProcess} | ConvertTo-Json | Set-Content artifacts/processes.json
        $health | ConvertTo-Json
        exit 0
    } catch { Start-Sleep -Seconds 1 }
}
throw 'Services did not become healthy. Inspect artifacts/logs.'
