param(
    [ValidateSet('audit','package','upload','verify','resume','status')]
    [string]$Mode = 'resume'
)
$ErrorActionPreference = 'Stop'
$preservationRoot = Split-Path -Parent $PSScriptRoot
$preservationPython = Join-Path $preservationRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $preservationPython)) { throw 'Missing project Python environment' }
Push-Location -LiteralPath $preservationRoot
try {
    & $preservationPython -u (Join-Path $PSScriptRoot 'preserve_research_artifacts.py') $Mode
    $preservationExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $preservationExitCode
