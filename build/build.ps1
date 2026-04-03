<#
.SYNOPSIS
    AutoSlice — Windows installer build script
    Produces: dist/installer/AutoSliceSetup_x.x.x.exe

.REQUIREMENTS
    - Python 3.12 (in PATH)
    - Node.js 20+ (in PATH)
    - pip install pyinstaller pystray pillow  (auto-installed below)
    - Inno Setup 6  (https://jrsoftware.org/isdl.php)

.USAGE
    From the repo root:
        powershell -ExecutionPolicy Bypass -File build\build.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root     = Split-Path $PSScriptRoot -Parent
$Build    = Join-Path $Root "build"
$Dist     = Join-Path $Root "dist"
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

# ── 1. Python deps ───────────────────────────────────────────────────────────
Write-Host "`n[1/6] Installing Python build dependencies..." -ForegroundColor Cyan
pip install pyinstaller pystray pillow --quiet

# ── 2. Build backend with PyInstaller ────────────────────────────────────────
Write-Host "`n[2/6] Building backend (PyInstaller)..." -ForegroundColor Cyan
Set-Location $Root
pyinstaller build\backend.spec --distpath dist --workpath build\work_backend --noconfirm
# Result: dist\autoslice_backend\

# ── 3. Build launcher with PyInstaller ───────────────────────────────────────
Write-Host "`n[3/6] Building launcher (PyInstaller)..." -ForegroundColor Cyan
Set-Location $Build
pyinstaller launcher.spec --distpath ..\dist --workpath work_launcher --noconfirm
Set-Location $Root
# Result: dist\AutoSlice.exe

# ── 4. Build Next.js frontend (standalone) ───────────────────────────────────
Write-Host "`n[4/6] Building Next.js frontend..." -ForegroundColor Cyan
Set-Location $Frontend
npm ci --silent
npm run build
Set-Location $Root

# Copy standalone output to dist/frontend
$FrontendDist = Join-Path $Dist "frontend"
if (Test-Path $FrontendDist) { Remove-Item $FrontendDist -Recurse -Force }
Copy-Item (Join-Path $Frontend ".next\standalone") $FrontendDist -Recurse
# Copy static assets that standalone doesn't include
Copy-Item (Join-Path $Frontend ".next\static") (Join-Path $FrontendDist ".next\static") -Recurse
if (Test-Path (Join-Path $Frontend "public")) {
    Copy-Item (Join-Path $Frontend "public") (Join-Path $FrontendDist "public") -Recurse
}

# ── 5. Bundle portable Node.js ───────────────────────────────────────────────
Write-Host "`n[5/6] Downloading portable Node.js..." -ForegroundColor Cyan

$NodeDir  = Join-Path $Dist "node"
$NodeVer  = "22.14.0"
$NodeZip  = Join-Path $Dist "node.zip"
$NodeUrl  = "https://nodejs.org/dist/v$NodeVer/node-v$NodeVer-win-x64.zip"

if (-not (Test-Path $NodeDir)) {
    Write-Host "    Downloading Node.js $NodeVer..."
    Invoke-WebRequest -Uri $NodeUrl -OutFile $NodeZip -UseBasicParsing
    Expand-Archive -Path $NodeZip -DestinationPath $Dist -Force
    Rename-Item (Join-Path $Dist "node-v$NodeVer-win-x64") $NodeDir
    Remove-Item $NodeZip
} else {
    Write-Host "    node/ already present, skipping download."
}

# ── 6. Inno Setup ────────────────────────────────────────────────────────────
Write-Host "`n[6/6] Creating installer with Inno Setup..." -ForegroundColor Cyan

$IsccCmd = Get-Command iscc -ErrorAction SilentlyContinue
$IsccPaths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
if ($IsccCmd) { $IsccPaths += $IsccCmd.Source }
$Iscc = $IsccPaths | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1

if (-not $Iscc) {
    Write-Host "`n  Inno Setup not found. Download from https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "  After installing, re-run this script or run:" -ForegroundColor Yellow
    Write-Host "      iscc build\setup.iss" -ForegroundColor Yellow
} else {
    New-Item -ItemType Directory -Path (Join-Path $Dist "installer") -Force | Out-Null
    & $Iscc (Join-Path $Build "setup.iss")
    Write-Host "`nDone! Installer is at: dist\installer\AutoSliceSetup_*.exe" -ForegroundColor Green
}

Write-Host "`nBuild complete." -ForegroundColor Green
