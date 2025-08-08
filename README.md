# virtualmanweek

Track time in Windows from the system tray icon

## Requirements

- Windows 11
- Python 3.11+ available as `py` launcher (or adjust scripts)
- PowerShell 5.1 or later

## Quick Start

1. Clone repo
2. Open PowerShell in repo root
3. Setup environment (creates .venv and installs deps)
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Dev
   ```
4. Run demo harness (currently logs one sample session)
   ```powershell
   .\.venv\Scripts\python -m virtualmanweek.main
   ```

## Testing

Run all tests (pytest auto-installed if missing):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
```

With coverage report:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1 -Coverage
```

## Building Executable

Clean build (folder output):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Clean
```

One-file executable (may increase startup time):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Clean -OneFile
```

Result appears under `dist/`.

## Packaging (Installer / Portable ZIP)

Create executable + ZIP (and installer if Inno Setup present):

```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 -Clean -OneFile
```

Outputs:

- `installer/VirtualManWeek-<version>.zip` portable package
- `installer/VirtualManWeek.iss` Inno Setup script (auto-generated first run)
- `installer/VirtualManWeek-Setup-<version>.exe` (if Inno Setup's `ISCC.exe` found on PATH)

Install Inno Setup: https://jrsoftware.org/isinfo.php

## Scripts Overview

- `scripts/setup.ps1` : create / update virtual environment (add -Dev for dev tools)
- `scripts/test.ps1` : run tests (add -Coverage for coverage)
- `scripts/build.ps1` : build executable (add -OneFile for single EXE, -Clean to remove old artifacts)
- `scripts/package.ps1` : build exe then produce portable ZIP and optional installer

## Project Status

Early bootstrap: tracking engine skeleton, DB schema, logging. UI tray and full features not implemented yet.

## License

MIT (see LICENSE file)
