<#!
.SYNOPSIS
  Build executable (PyInstaller) and generate a Windows installer (Inno Setup) or ZIP package fallback.
.DESCRIPTION
  1. Runs build.ps1 (optionally one-file)
  2. Stages files under installer/staging
  3. Generates Inno Setup script (VirtualManWeek.iss) dynamically (if not already customized)
  4. Compiles installer if ISCC (Inno Setup) is available; otherwise leaves script + zip archive

  Install Inno Setup: https://jrsoftware.org/isinfo.php (ensure ISCC.exe is on PATH)
#>
param(
  [switch]$OneFile,
  [switch]$Clean,
  [string]$Arch = 'x64',          # Informational (not enforced by PyInstaller)
  [string]$OutputDir = 'installer'
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $root '..')
Set-Location $repoRoot

# Activate venv
$venvPath = Join-Path $repoRoot '.venv'
if (-not (Test-Path $venvPath)) { Write-Error 'Virtual environment not found. Run scripts/setup.ps1 first.' }
# Activate venv only if not already active
if (-not $env:VIRTUAL_ENV) {
  $activateScript = Join-Path (Join-Path $venvPath 'Scripts') 'Activate.ps1'
  if (-not (Test-Path $activateScript)) { Write-Error "Activation script not found at $activateScript" }
  . $activateScript
} else {
  Write-Host "Using already activated venv: $env:VIRTUAL_ENV" -ForegroundColor DarkGray
}

# Step 1: Build executable
$buildArgs = @()
if ($OneFile) { $buildArgs += '-OneFile' }
if ($Clean) { $buildArgs += '-Clean' }
$buildScript = Join-Path (Join-Path $repoRoot 'scripts') 'build.ps1'
& powershell -ExecutionPolicy Bypass -File $buildScript @buildArgs

# Determine version (parse from src/virtualmanweek/__init__.py to avoid python -c quoting issues)
$initPath = Join-Path (Join-Path $repoRoot 'src') 'virtualmanweek/__init__.py'
$version = '0.0.0'
if (Test-Path $initPath) {
  $verLine = Get-Content $initPath | Where-Object { $_ -match '__version__' } | Select-Object -First 1
  if ($verLine -and $verLine -match '"([0-9]+\.[0-9]+\.[0-9]+[^"]*)"') {
    $version = $matches[1]
  }
}
Write-Host "Detected version: $version" -ForegroundColor DarkGray

Write-Host "Packaging version $version" -ForegroundColor Cyan

# Paths
$distDir = Join-Path $repoRoot 'dist'
$exeName = if (Test-Path (Join-Path $distDir 'VirtualManWeek.exe')) { 'VirtualManWeek.exe' } else { 'VirtualManWeek/VirtualManWeek.exe' }
$exePath = Join-Path $distDir $exeName
if (-not (Test-Path $exePath)) { Write-Error "Executable not found at $exePath" }

$outRoot = Join-Path $repoRoot $OutputDir
$staging = Join-Path $outRoot 'staging'
if (Test-Path $staging) { Remove-Item -Recurse -Force $staging }
New-Item -ItemType Directory -Force -Path $staging | Out-Null

# Copy artifacts
# If we have an onedir build (exe inside dist/VirtualManWeek/ plus python DLLs), copy whole directory so dependencies are present.
$oneDirFolder = Join-Path $distDir 'VirtualManWeek'
$usingOneDir = $false
if (-not $OneFile -and (Test-Path (Join-Path $oneDirFolder 'VirtualManWeek.exe'))) {
  $usingOneDir = $true
}
if ($usingOneDir) {
  Write-Host 'Detected onedir build; copying entire dist/VirtualManWeek contents for portable package.' -ForegroundColor Yellow
  Copy-Item (Join-Path $oneDirFolder '*') $staging -Recurse -Force
}
else {
  # Onefile build: only the single exe is needed
  Copy-Item $exePath (Join-Path $staging 'VirtualManWeek.exe') -Force
}
foreach ($f in @('README.md','LICENSE')) { if (Test-Path $f) { Copy-Item $f $staging -Force } }

# Optional assets (icon)
if (Test-Path 'assets/icon.ico') { Copy-Item 'assets/icon.ico' (Join-Path $staging 'icon.ico') -Force }

# Create ZIP fallback
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = Join-Path $outRoot ("VirtualManWeek-$version.zip")
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
[System.IO.Compression.ZipFile]::CreateFromDirectory($staging, $zipPath)
Write-Host "Created portable ZIP: $zipPath" -ForegroundColor Green

# Step 2: Inno Setup script
$issPath = Join-Path $outRoot 'VirtualManWeek.iss'
if (-not (Test-Path $issPath)) {
  @"
; Auto-generated Inno Setup script. Customize as needed.
#define MyAppName "VirtualManWeek"
#define MyAppVersion "$version"
#define MyAppExeName "VirtualManWeek.exe"
#define MyAppPublisher "VirtualManWeek"
#define MyAppURL "https://example.invalid"
#define MyAppId "{{7B7D5A24-9C2F-4F5E-8A5E-VMW$($version.Replace('.', ''))}}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
DefaultDirName={autopf}\\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "staging\\VirtualManWeek.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "staging\\icon.ico"; DestDir: "{app}"; Flags: ignoreversion; Permissions: users-full

[Icons]
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
"@ | Set-Content -Encoding UTF8 $issPath
  Write-Host "Generated Inno Setup script: $issPath" -ForegroundColor Yellow
}
else {
  Write-Host "Using existing Inno Setup script: $issPath" -ForegroundColor Yellow
}

# Step 3: Compile installer if ISCC available
if (Get-Command ISCC.exe -ErrorAction SilentlyContinue) {
  Write-Host 'Compiling installer with Inno Setup...' -ForegroundColor Cyan
  & ISCC.exe $issPath /Qp | Out-Null
  Write-Host 'Installer build complete.' -ForegroundColor Green
  Get-ChildItem $outRoot -Filter 'VirtualManWeek-Setup-*.exe' | Sort-Object LastWriteTime -Descending | Select-Object -First 1 | ForEach-Object { Write-Host "Installer: $($_.FullName)" -ForegroundColor Green }
}
else {
  Write-Host 'ISCC.exe not found on PATH. Install Inno Setup to build installer. ZIP package is available.' -ForegroundColor Yellow
}

Write-Host 'Packaging done.' -ForegroundColor Green
