<#!
.SYNOPSIS
  Start VirtualManWeek in development tray mode.
#>
param(
  [switch]$Recreate,
  [switch]$Debug
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptRoot '..')
Set-Location $repoRoot

# Add src to PYTHONPATH for editable import
$srcPath = Join-Path $repoRoot 'src'
if ($env:PYTHONPATH) { $env:PYTHONPATH = "$srcPath;$env:PYTHONPATH" } else { $env:PYTHONPATH = $srcPath }

# Ensure venv exists (or recreate if requested)
$venvPath = Join-Path $repoRoot '.venv'
if ($Recreate -and (Test-Path $venvPath)) {
  Write-Host 'Removing existing venv' -ForegroundColor Yellow
  Remove-Item -Recurse -Force $venvPath
}
if (-not (Test-Path $venvPath)) {
  Write-Host 'Virtual env missing -> running setup.ps1' -ForegroundColor Cyan
  & (Join-Path $scriptRoot 'setup.ps1') -Dev
}

# Activate
$activate = Join-Path $venvPath 'Scripts' | Join-Path -ChildPath 'Activate.ps1'
. $activate

if ($Debug) {
  $env:VM_DEBUG = '1'
  Write-Host 'Debug mode enabled (VM_DEBUG=1)' -ForegroundColor Yellow
}

Write-Host 'Launching tray app...' -ForegroundColor Green
python -m virtualmanweek.main --tray
