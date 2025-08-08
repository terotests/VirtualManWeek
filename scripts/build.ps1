<#!
.SYNOPSIS
  Build standalone executable with PyInstaller.
#>
param(
  [switch]$OneFile,
  [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $root '..')
Set-Location $repoRoot

$venvPath = Join-Path $repoRoot '.venv'
if (-not (Test-Path $venvPath)) { Write-Error 'Virtual environment not found. Run scripts/setup.ps1 first.' }
$activate = Join-Path $venvPath 'Scripts' 'Activate.ps1'
. $activate

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
  Write-Host 'Installing pyinstaller (missing)' -ForegroundColor Yellow
  pip install pyinstaller
}

if ($Clean) {
  Write-Host 'Cleaning previous build artifacts' -ForegroundColor Yellow
  Remove-Item -Recurse -Force build -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force dist -ErrorAction SilentlyContinue
  Remove-Item *.spec -ErrorAction SilentlyContinue
}

$mainModule = 'virtualmanweek.main:main'
$entry = 'src/virtualmanweek/main.py'

$icon = 'assets/icon.ico'
if (-not (Test-Path $icon)) { $icon = $null }

$pyiArgs = @('--name','VirtualManWeek','--paths','src')
if ($icon) { $pyiArgs += @('--icon', $icon) }
if ($OneFile) { $pyiArgs += '--onefile' }
$pyiArgs += $entry
# Add runtime argument for tray via generated .spec tweak not yet; user can run with --tray

Write-Host "Running PyInstaller: $pyiArgs" -ForegroundColor Cyan
pyinstaller @pyiArgs

Write-Host 'Build complete. See dist/VirtualManWeek or dist/VirtualManWeek.exe' -ForegroundColor Green
