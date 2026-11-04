$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing .venv. Install the validated requirements as documented in README.md.' }
$env:PYTHONUTF8 = '1'
& $python -u scripts/research_watchdog.py worker
exit $LASTEXITCODE
