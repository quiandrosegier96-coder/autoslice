<#
.SYNOPSIS
    AutoSlice — Electron desktop installer build script
    Produces: electron/dist/AutoSlice Setup x.x.x.exe

.REQUIREMENTS
    - Python 3.12 (in PATH)
    - Node.js 20+ (in PATH)
    - pip install pyinstaller  (auto-installed below)
    - Internet access for first run (downloads portable Node.js)

.USAGE
    From the repo root:
        powershell -ExecutionPolicy Bypass -File build\build_electron.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Root     = Split-Path $PSScriptRoot -Parent
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Electron = Join-Path $Root "electron"
$Resources = Join-Path $Electron "resources"

# ── 1. Python build deps ─────────────────────────────────────────────────────
Write-Host "`n[1/6] Installing Python build dependencies..." -ForegroundColor Cyan
pip install pyinstaller --quiet

# ── 2. PyInstaller backend ────────────────────────────────────────────────────
Write-Host "`n[2/6] Building backend with PyInstaller..." -ForegroundColor Cyan
Set-Location $Root
pyinstaller build\backend.spec `
    --distpath (Join-Path $Resources "backend_tmp") `
    --workpath  (Join-Path $Root "build\work_backend") `
    --noconfirm

# Move the one-folder bundle to resources/backend
$BackendTmp  = Join-Path $Resources "backend_tmp\autoslice_backend"
$BackendDest = Join-Path $Resources "backend"
if (Test-Path $BackendDest) { Remove-Item $BackendDest -Recurse -Force }
Move-Item $BackendTmp $BackendDest
Remove-Item (Join-Path $Resources "backend_tmp") -Recurse -Force -ErrorAction SilentlyContinue

# ── 3. Next.js production build ───────────────────────────────────────────────
Write-Host "`n[3/6] Building Next.js frontend (standalone)..." -ForegroundColor Cyan
Set-Location $Frontend
npm ci --silent
npm run build
Set-Location $Root

# Copy standalone output to resources/frontend
$FeDest = Join-Path $Resources "frontend"
if (Test-Path $FeDest) { Remove-Item $FeDest -Recurse -Force }
Copy-Item (Join-Path $Frontend ".next\standalone") $FeDest -Recurse
# Static assets that standalone doesn't bundle itself
$StaticSrc = Join-Path $Frontend ".next\static"
$StaticDst = Join-Path $FeDest ".next\static"
if (Test-Path $StaticSrc) { Copy-Item $StaticSrc $StaticDst -Recurse }
$PublicSrc = Join-Path $Frontend "public"
if (Test-Path $PublicSrc)  { Copy-Item $PublicSrc (Join-Path $FeDest "public") -Recurse }

# ── 4. Portable Node.js for the Next.js server ────────────────────────────────
Write-Host "`n[4/6] Downloading portable Node.js..." -ForegroundColor Cyan

$NodeDest = Join-Path $Resources "node"
$NodeVer  = "22.14.0"
$NodeZip  = Join-Path $Resources "node.zip"
$NodeUrl  = "https://nodejs.org/dist/v$NodeVer/node-v$NodeVer-win-x64.zip"

if (-not (Test-Path (Join-Path $NodeDest "node.exe"))) {
    New-Item -ItemType Directory -Path $Resources -Force | Out-Null
    Write-Host "    Downloading Node.js $NodeVer..."
    Invoke-WebRequest -Uri $NodeUrl -OutFile $NodeZip -UseBasicParsing
    Expand-Archive -Path $NodeZip -DestinationPath $Resources -Force
    if (Test-Path $NodeDest) { Remove-Item $NodeDest -Recurse -Force }
    Rename-Item (Join-Path $Resources "node-v$NodeVer-win-x64") $NodeDest
    Remove-Item $NodeZip
} else {
    Write-Host "    Portable Node.js already present, skipping download."
}

# ── 5. Electron npm install ───────────────────────────────────────────────────
Write-Host "`n[5/6] Installing Electron dependencies..." -ForegroundColor Cyan
Set-Location $Electron
npm install --save-dev --silent

# ── 6. Build Electron installer ───────────────────────────────────────────────
Write-Host "`n[6/6] Packaging with electron-builder..." -ForegroundColor Cyan

# Generate a minimal icon if none exists
$IconPath = Join-Path $Electron "assets\icon.ico"
if (-not (Test-Path $IconPath)) {
    Write-Host "    No icon.ico found - generating placeholder icon..." -ForegroundColor Yellow
    # Use PowerShell + .NET to create a minimal 32x32 ICO
    Add-Type -AssemblyName System.Drawing
    $bmp = New-Object System.Drawing.Bitmap(32, 32)
    $g   = [System.Drawing.Graphics]::FromImage($bmp)
    $g.Clear([System.Drawing.Color]::FromArgb(224, 36, 36))
    $g.Dispose()
    $bmp.Save($IconPath, [System.Drawing.Imaging.ImageFormat]::Icon)
    $bmp.Dispose()
}

$env:CSC_IDENTITY_AUTO_DISCOVERY = "false"
$env:WIN_CSC_LINK                 = ""
$env:WIN_CSC_KEY_PASSWORD         = ""
# Point SIGNTOOL_PATH to the system signtool so electron-builder skips the
# winCodeSign download entirely (it short-circuits before downloading when
# SIGNTOOL_PATH is set).  Signing is still skipped because no cert is present.
$env:SIGNTOOL_PATH = "signtool.exe"
npm run dist

Write-Host "`nDone! Installer is at:" -ForegroundColor Green
Get-ChildItem (Join-Path $Electron "dist") -Filter "*.exe" | ForEach-Object {
    Write-Host "  $($_.FullName)" -ForegroundColor Green
}

Set-Location $Root
