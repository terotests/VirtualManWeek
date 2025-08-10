# VirtualManWeek

Lightweight Windows system tray time tracker with mode switching, idle detection, and comprehensive reporting.

## Key Features

**Core Tracking:**
- System tray UI with visual status (green=active, yellow=idle, red=stopped)
- Quick mode switching with predefined and custom modes
- Automatic idle detection and sleep/hibernate handling
- Manual time entry with "Fill Idle Time" functionality
- Project and mode management with full CRUD operations

**Database & Data:**
- Multiple database support with easy switching
- Automatic initialization of default modes per database
- Export/import databases, clear data with confirmation
- Robust data integrity with orphaned mode detection

**Reporting & Export:**
- HTML reports with Chart.js visualizations (mode distribution, daily timeline)
- CSV export of time entries
- Standardized export filenames (WMW_DatabaseName_WeekDate.ext)
- Consistent time formatting throughout (e.g., "2h 15min", "45s", "1min 30s")

**User Experience:**
- Streamlined menu structure (combined Export submenu, Edit modes via Switch Mode)
- Enhanced tooltips showing current database, project, and mode
- Confirmation dialogs for destructive actions
- Manual time adjustment for retrospective logging

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

**Mode & Project Management:**
- Switch Mode → [Mode List] : quickly switch to existing modes
- Switch Mode → Edit... : open comprehensive mode management dialog
- Set Idle : manually mark current activity as idle
- Projects → [Project List] : switch between projects
- Projects → Edit Projects... : manage projects (add/edit/archive)

**Data Export:**
- Export → CSV... : export time entries to CSV file
- Export → HTML... : generate mode distribution charts and reports

**Database Management:**
- Admin → Create/Select Database : manage multiple databases
- Admin → Export/Import Database : backup and restore functionality
- Admin → Clear Logged Entries : reset data with confirmation

**Settings & Info:**
- Current database and project shown in tray tooltip and menu headers

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

| Script      | Purpose                                                       |
| ----------- | ------------------------------------------------------------- |
| setup.ps1   | Create/update virtual env & install deps (-Dev for dev tools) |
| test.ps1    | Run tests (optional -Coverage)                                |
| build.ps1   | PyInstaller build (-OneFile / -Clean)                         |
| package.ps1 | Build + ZIP + optional installer                              |

## Versioning

Defined in `virtualmanweek/__init__.py` (`__version__`). Packaging script reads this value.

## License

MIT (see `LICENSE`).
