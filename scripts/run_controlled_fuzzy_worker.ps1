param([ValidateSet('pilot','confirmation')][string]$Stage = 'pilot', [string]$OutputRoot = '')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing validated .venv.' }
$env:MINIFLS_STUDY = 'controlled-fuzzy-ablation'
$env:MINIFLS_FUZZY_CONFIG = "configurations/controlled-fuzzy-ablation-$Stage.json"
$env:MINIFLS_FUZZY_MODE = if ($Stage -eq 'pilot') { 'pilot' } else { 'full' }
$env:MINIFLS_FUZZY_OUTPUT = if ($OutputRoot) { $OutputRoot } else { "artifacts/research/controlled-fuzzy-ablation/$Stage" }
$env:PYTHONUTF8 = '1'
& $python -u scripts/research_watchdog.py worker
exit $LASTEXITCODE
