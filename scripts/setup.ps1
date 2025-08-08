<#!
.SYNOPSIS
  Create / update local virtual environment and install dependencies.
#>
param(
  [switch]$Recreate,
  [switch]$Dev
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $root '..')
Set-Location $repoRoot

$venvPath = Join-Path $repoRoot '.venv'

if ($Recreate -and (Test-Path $venvPath)) {
  Write-Host 'Removing existing venv' -ForegroundColor Yellow
  Remove-Item -Recurse -Force $venvPath
}

if (-not (Test-Path $venvPath)) {
  Write-Host 'Creating virtual environment' -ForegroundColor Cyan
  if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 -m venv .venv
  } else {
    python -m venv .venv
  }
}

# Activate (fix Join-Path usage)
$activateDir = Join-Path $venvPath 'Scripts'
$activate = Join-Path $activateDir 'Activate.ps1'
if (-not (Test-Path $activate)) { Write-Error "Activate script not found at $activate" }
. $activate

Write-Host "Python: $(python --version)" -ForegroundColor Green

# Upgrade pip
python -m pip install --upgrade pip

# Base requirements
if (Test-Path 'requirements.txt') {
  Write-Host 'Installing requirements.txt' -ForegroundColor Cyan
  pip install -r requirements.txt
}
else {
  Write-Host 'requirements.txt not found, skipping base install' -ForegroundColor Yellow
}

if ($Dev) {
  $devPackages = @('pytest','pyinstaller','black','flake8')
  Write-Host 'Installing dev packages: ' ($devPackages -join ', ') -ForegroundColor Cyan
  pip install @devPackages
}

Write-Host 'Environment ready.' -ForegroundColor Green
