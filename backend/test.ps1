param(
    [string]$Scope = "tests",
    [switch]$Bootstrap
)

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$VenvPython = Join-Path $BackendRoot ".venv\Scripts\python.exe"

if ($Bootstrap -and -not (Test-Path -LiteralPath $VenvPython)) {
    $SystemPython = Get-Command python -ErrorAction SilentlyContinue
    if (-not $SystemPython) {
        throw "Python 3.11+ is required. Install it, then rerun with -Bootstrap."
    }
    & $SystemPython.Source -m venv (Join-Path $BackendRoot ".venv")
    & $VenvPython -m pip install --upgrade pip
    & $VenvPython -m pip install -r (Join-Path $BackendRoot "requirements.txt")
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    throw "backend/.venv is missing. Run .\test.ps1 -Bootstrap once."
}

Push-Location $BackendRoot
try {
    & $VenvPython -m pytest $Scope
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
