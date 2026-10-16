$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $workspace 'artifacts/processes.json'
if (-not (Test-Path -LiteralPath $pidFile)) { throw 'No saved MiniFLS process IDs.' }
$saved = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
function Stop-Tree([int]$processId) {
    foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$processId")) {
        Stop-Tree -processId $child.ProcessId
    }
    Stop-Process -Id $processId -ErrorAction SilentlyContinue
}
foreach ($entry in @(@{id=$saved.worker;pattern='uvicorn.+minifls\.api:app'},@{id=$saved.server;pattern='ferderatedsystem-0\.0\.1-SNAPSHOT\.jar'})) {
    $running = Get-CimInstance Win32_Process -Filter "ProcessId=$($entry.id)"
    if ($null -eq $running) { continue }
    if ($running.CommandLine -notmatch $entry.pattern) { throw "PID $($entry.id) no longer belongs to the saved MiniFLS service." }
    Stop-Tree -processId $entry.id
    Write-Output "Stopped MiniFLS PID $($entry.id) and its child processes."
}
