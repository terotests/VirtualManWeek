# VirtualManWeek

Lightweight Windows system tray time tracker with mode switching, idle/sleep handling, statistics and export.

## Requirements
- Windows 11 (Win10 likely works)
- Python 3.11+ (for development / building)
- PowerShell 5.1+ / 7+
- (Optional) Inno Setup (ISCC.exe on PATH) to build installer

## Quick Start (Source)
1. Clone repository
2. In repo root run:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/setup.ps1 -Dev
   ```
3. Launch tray UI:
   ```powershell
   .\.venv\Scripts\python -m virtualmanweek.main --tray
   ```
4. Tray icon appears (Idle = yellow, Active = green, Stopped = red). Left‑click to open menu.

## Key Features
- System tray UI (start on Idle, switch modes quickly)
- Custom & quick modes (with optional description per switch)
- Automatic idle detection (yellow) + recovery; sleep gap handling
- Mode distribution chart (QtCharts fallback to HTML/Chart.js) + export
- Detailed HTML report (daily timeline + per‑mode entries)
- CSV export of recent entries
- Project & mode management dialogs
- Database export / import and safe clear (admin menu)
- Portable ZIP or Windows installer packaging (PyInstaller + optional Inno Setup)

## Common Actions (Tray Menu)
- Switch Mode / Custom… : change current activity
- Set Idle : manually mark idle
- Statistics → Mode Distribution : view chart / export HTML
- Export Week (CSV) : raw entries sample export
- Admin → Export / Import Database, Clear Logged Entries

## Build Executable
Clean folder build:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Clean
```
One‑file exe (slower start):
```powershell
powershell -ExecutionPolicy Bypass -File scripts/build.ps1 -Clean -OneFile
```
Run built app:
```powershell
./dist/VirtualManWeek.exe --tray
```

## Package (ZIP / Installer)
```powershell
powershell -ExecutionPolicy Bypass -File scripts/package.ps1 -Clean -OneFile
```
Outputs under `installer/`:
- `VirtualManWeek-<version>.zip` (portable)
- `VirtualManWeek-Setup-<version>.exe` (if ISCC.exe available)
- `VirtualManWeek.iss` (generated script; customize if desired)

## Testing
```powershell
powershell -ExecutionPolicy Bypass -File scripts/test.ps1
powershell -ExecutionPolicy Bypass -File scripts/test.ps1 -Coverage   # add coverage
```

## Scripts Summary
| Script | Purpose |
|--------|---------|
| setup.ps1 | Create/update virtual env & install deps (-Dev for dev tools) |
| test.ps1 | Run tests (optional -Coverage) |
| build.ps1 | PyInstaller build (-OneFile / -Clean) |
| package.ps1 | Build + ZIP + optional installer |

## Versioning
Defined in `virtualmanweek/__init__.py` (`__version__`). Packaging script reads this value.

## License
MIT (see `LICENSE`).
