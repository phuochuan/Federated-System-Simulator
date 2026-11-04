$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing .venv. Install the validated requirements as documented in README.md.' }
if (-not (Get-Command java -ErrorAction SilentlyContinue)) { throw 'Java 17 or later is required.' }
$env:PYTHONUTF8 = '1'
& $python -u scripts/research_watchdog.py java
exit $LASTEXITCODE
