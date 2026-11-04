param(
    [ValidateSet('pilot','confirmation')][string]$Stage = 'pilot',
    [ValidateSet('run','preflight','report-only')][string]$Mode = 'run',
    [int]$RunBudget = 1,
    [int]$RoundBudget = 70,
    [switch]$AcceptConfirmation,
    [string]$OutputRoot = ''
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if ($RunBudget -lt 0 -or $RoundBudget -lt 0) { throw 'Budgets must be nonnegative.' }
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Missing validated .venv.' }
if (-not (Get-Command java -ErrorAction SilentlyContinue)) { throw 'Java 17 is required.' }
$env:MINIFLS_STUDY = 'controlled-fuzzy-ablation'
$env:MINIFLS_FUZZY_CONFIG = "configurations/controlled-fuzzy-ablation-$Stage.json"
$env:MINIFLS_FUZZY_MODE = if ($Mode -eq 'run') { if ($Stage -eq 'pilot') { 'pilot' } else { 'full' } } else { $Mode }
$env:MINIFLS_FUZZY_OUTPUT = if ($OutputRoot) { $OutputRoot } else { "artifacts/research/controlled-fuzzy-ablation/$Stage" }
$env:MINIFLS_FUZZY_RUN_BUDGET = "$RunBudget"
$env:MINIFLS_FUZZY_ROUND_BUDGET = "$RoundBudget"
$env:MINIFLS_ABLATION_ACCEPT_CONFIRMATION = if ($AcceptConfirmation) { '1' } else { '0' }
$env:PYTHONUTF8 = '1'
& $python -u scripts/research_watchdog.py java
exit $LASTEXITCODE
