<#!
.SYNOPSIS
  Run test suite inside virtual environment.
#>
param(
  [string]$Markers,
  [switch]$Coverage
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $root '..')
Set-Location $repoRoot

$venvPath = Join-Path $repoRoot '.venv'
if (-not (Test-Path $venvPath)) { Write-Error 'Virtual environment not found. Run scripts/setup.ps1 first.' }
$activate = Join-Path $venvPath 'Scripts' 'Activate.ps1'
. $activate

if (-not (Get-Command pytest -ErrorAction SilentlyContinue)) {
  Write-Host 'Installing pytest (missing)' -ForegroundColor Yellow
  pip install pytest
}

$cmd = 'pytest'
if ($Markers) { $cmd += " -m $Markers" }
if ($Coverage) {
  if (-not (Get-Command coverage -ErrorAction SilentlyContinue)) { pip install coverage }
  $cmd = "coverage run -m $cmd && coverage report"
}

Write-Host "Running: $cmd" -ForegroundColor Cyan
Invoke-Expression $cmd
