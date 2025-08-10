# PORTING / LIGHTER DISTRIBUTION OPTIONS

Goal: Reduce packaged size and startup overhead versus current PyInstaller + PySide6 (Qt) build.

## 1. Stay in Python, Slim Down

| Idea                        | Expected Gain | Notes                                                                                                     |
| --------------------------- | ------------- | --------------------------------------------------------------------------------------------------------- |
| Remove QtCharts usage       | Few MB        | Use only HTML (Chart.js) for charts; drop PySide6.QtCharts import so its plugin DLLs not bundled.         |
| Onedir (no --onefile)       | Faster start  | Avoid self‑extract delay; does not reduce size but improves UX.                                           |
| Exclude unused stdlib       | Small         | Add --exclude-module test, tkinter, asyncio (if unused) to PyInstaller.                                   |
| Optimize .pyc               | Small         | Set optimize=2 in spec; strip asserts.                                                                    |
| UPX compress (verify)       | 10–30%        | Install UPX; keep upx=True. Some DLLs may be incompressible.                                              |
| Custom hook pruning         | Medium        | Manually remove unnecessary Qt plugins (bearer, printsupport, etc.) from dist if not used.                |
| Use PySide6-Essentials only | Few MB        | If extras are unused.                                                                                     |
| Embed Python manually       | Medium        | Ship embeddable Python + your sources (.pyc) without PyInstaller overhead. Manual launcher .exe required. |

## 2. Alternative Python GUI / Tray Stacks

| Stack                      | Pros                               | Cons                                                                   |
| -------------------------- | ---------------------------------- | ---------------------------------------------------------------------- |
| wxPython                   | Smaller than full Qt in some cases | Still large; Windows only focus for tray stable.                       |
| Tkinter + pystray          | Very small stdlib GUI base         | Tk’s look dated; charting via HTML (browser) or Pillow manual drawing. |
| PySimpleGUI (tk backend)   | Simple API                         | Same Tk limitations; wraps tkinter.                                    |
| pystray + Win32 toast libs | Minimal tray only                  | Need custom dialogs (Win32) or web dialogs; more code.                 |

## 3. Native Rewrites

### 3.1 C++ (Qt or Win32)

- Qt C++: Still ships Qt DLLs; size similar or slightly smaller than PySide because Python interpreter removed (saving ~8–10 MB compressed) but Qt core remains (tens of MB). Use static Qt build + optimization to shrink (complex licensing/build effort; LGPL static requires object files distribution or commercial).
- Pure Win32 + GDI: Smallest footprint (hundreds of KB). Implement tray icon (Shell_NotifyIcon), timers, SQLite (link against amalgamation), simple modal dialogs (DialogBox). Chart: generate HTML in temp + open default browser OR draw custom bar in GDI. Development effort higher.

### 3.2 C# / .NET (WinForms / WPF)

- Single-file trimmed publish (.NET 7+) can reach ~15–25 MB self-contained; with framework-dependent publish ~1–2 MB but requires .NET Runtime installed.
- Easy tray support (NotifyIcon), SQLite via Microsoft.Data.Sqlite.

### 3.3 Rust

Options:

- Tray: use system-tray crates (tray-icon, systray). GUI: Tauri (heavy) or minifb/egui (heavier). Minimal + HTML exports approach: headless core + tray only.
- Size: Release binary with SQLite (rusqlite) ~5–10 MB.
- Pros: Safety, performance, single static exe. Cons: More initial complexity for Windows-specific idle detection (WinAPI calls via winapi crate).

### 3.4 Go

- Single static binary (~10–15 MB). systray library for tray icon + menu. cgo needed for SQLite or use pure Go embedded DB (Modernc SQLite or buntdb). Idle detection via syscall + WinAPI wrappers.
- Pros: Fast iteration, cross-compilation. Cons: Larger baseline than pure C++.

### 3.5 Nim

- Can produce small native binaries (a few MB). Windows API binding manageable. Smaller ecosystem; fewer tray abstractions.

## 4. Architecture Split (Hybrid)

Keep logic (tracking, DB, exports) in a lightweight local service:

- Core: Small Rust (or Go) daemon writing SQLite + exposing minimal HTTP or named-pipe API.
- UI: Web (local HTML/JS) launched in Edge WebView2 or default browser; charts via Chart.js. Tray: separate tiny native process controlling service (Rust or Go). Minimizes duplication while enabling rich UI without bundling heavy GUI framework.

## 5. Simplify Features for Minimal Build

| Feature                            | Slim Alternative                                                                                      |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------- |
| Qt dialogs                         | Native MessageBox (WinAPI) + simple input forms replaced by text-based minimal forms or HTML dialogs. |
| Charts (QtCharts)                  | Only HTML/Chart.js generation, open in browser.                                                       |
| Rich multi-line description dialog | Plain single-line input or external editor invocation.                                                |
| Project management UI              | Simple JSON/INI edit + reload, or CLI subcommands.                                                    |

## 6. Native Windows Tray (C++ Sketch)

Components:

1. WinMain: Register window class, hidden message window.
2. Shell_NotifyIcon to add tray icon (NIM_ADD) and handle callbacks (WM_USER + ID).
3. Timer (SetTimer) every second → poll idle via GetLastInputInfo.
4. DB: sqlite3_open_v2, prepared statements for inserts/updates.
5. Idle/sleep handling: Track timestamp deltas; if gap > threshold mark idle segment.
6. Export: Generate CSV/HTML directly.
   Binary size: With /O2 /DNDEBUG and dynamic CRT ~300–600 KB (+ SQLite DLL ~600 KB) or static ~1–2 MB.

## 7. Priority Matrix

| Path                       | Effort | Size Win | Maintainability     |
| -------------------------- | ------ | -------- | ------------------- |
| Prune Qt (current Python)  | Low    | Small    | High (stay Python)  |
| Manually embed Python      | Medium | Medium   | Medium              |
| Rust rewrite (tray + core) | High   | Large    | High (once done)    |
| C++ Win32 rewrite          | High   | Largest  | Medium (harder dev) |
| Go rewrite                 | Medium | Large    | High                |
| Hybrid service + web UI    | High   | Medium   | Medium/High         |

## 8. Recommended Incremental Plan

1. Remove QtCharts import; rely on HTML report (fast immediate reduction).
2. Add PyInstaller excludes and optimize=2.
3. Audit and remove unused Qt plugins (manually delete from dist then test).
4. If still too big: prototype Go or Rust tray POC capturing sessions & writing SQLite; keep Python exporter temporarily (dual-run for validation).
5. Migrate exports to new core; retire Python once feature parity reached.

## 9. Idle Detection Port Notes

- Windows API: GetLastInputInfo (C/C++/Rust/Go bindings easy).
- Sleep detection: Compare consecutive poll timestamps; if delta > threshold → treat as system sleep/resume, segment session.

## 10. SQLite Portability

- Keep schema simple (current). Provide version table for future migrations.
- Use WAL mode for robustness on native builds (PRAGMA journal_mode=WAL). Optional for small app.

## 11. Testing & Validation Strategy

- Dual-run mode: Python and new native tracker log to separate DBs for a week; compare aggregates.
- Snapshot validator: Script to diff per-day active seconds per mode.

## 12. Security / Signing

- Native builds should be code-signed to reduce SmartScreen warnings (especially onefile Python or new native exe).

## 13. When to Abandon Python

Choose a rewrite if after pruning you still exceed distribution goals (e.g., target <15 MB) or need lower idle RAM (<30 MB). If size is acceptable (>40 MB but fine internally), keep Python for velocity.

---

Questions or next step: decide which reduction (remove QtCharts vs start Rust POC) to proceed with first.
