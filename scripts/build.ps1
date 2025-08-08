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
$activate = Join-Path (Join-Path $venvPath 'Scripts') 'Activate.ps1'
if (-not $env:VIRTUAL_ENV) {
  if (-not (Test-Path $activate)) { Write-Error "Activation script not found at $activate" }
  . $activate
} else {
  Write-Host "Using already activated venv: $env:VIRTUAL_ENV" -ForegroundColor DarkGray
}

if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
  Write-Host 'Installing pyinstaller (missing)' -ForegroundColor Yellow
  pip install pyinstaller | Out-Null
}

if ($Clean) {
  Write-Host 'Cleaning previous build artifacts' -ForegroundColor Yellow
  # Try to stop any running instance so files aren't locked
  $proc = Get-Process -Name 'VirtualManWeek' -ErrorAction SilentlyContinue
  if ($proc) {
    Write-Host 'Stopping running VirtualManWeek.exe to avoid file lock...' -ForegroundColor Yellow
    try { $proc | Stop-Process -Force -ErrorAction Stop } catch { Write-Host "Warning: could not stop process: $_" -ForegroundColor Red }
    Start-Sleep -Milliseconds 300
  }
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
if ($OneFile) {
  $pyiArgs += '--onefile'
} else {
  Write-Host 'Building default onedir layout (folder with dependencies). Use -OneFile for single exe (slower start).' -ForegroundColor DarkGray
}
$pyiArgs += $entry

Write-Host "Running PyInstaller: $pyiArgs" -ForegroundColor Cyan
pyinstaller @pyiArgs

Write-Host 'Build complete. See dist/VirtualManWeek or dist/VirtualManWeek.exe' -ForegroundColor Green
if ($OneFile) {
  $portableMsg = 'Portable: copy dist/VirtualManWeek.exe only.'
} else {
  $portableMsg = 'Portable: copy entire dist/VirtualManWeek folder (includes python DLLs).'
}
Write-Host $portableMsg -ForegroundColor DarkGray
