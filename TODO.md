# TODO – VirtualManWeek Implementation Checklist

Legend: [ ] pending [~] in progress [x] done (★) stretch/optional

## 1. Repository & Licensing

[ ] Add MIT LICENSE (done in repo root)  
[x] Create initial skeleton (src/, tests/, scripts/)  
[ ] Add CONTRIBUTING.md (basic dev workflow)  
[ ] Add CODE_OF_CONDUCT.md (optional)

## 2. Environment & Tooling

[ ] Confirm required Python version in README (3.11+)  
[x] setup.ps1 script  
[x] test.ps1 script  
[x] build.ps1 script  
[ ] Add dev requirements (pytest, black, flake8) to requirements-dev.txt or pyproject  
[ ] (Skip for now) Pre-commit hook config (★)  
[ ] (Skip for now) GitHub Actions workflow (★)

## 3. Configuration & Settings

[x] AppData path resolver  
[x] Settings dataclass + JSON load/save  
[ ] Implement command to show settings file path  
[ ] Add setting for startup at login  
[ ] Add setting for language selection (placeholders)  
[ ] Add setting to toggle discard_sub_10s_entries  
[ ] Validate settings on load (fallback defaults)

## 4. Database Layer

[x] SQLite initialization + schema v1  
[x] Add weeks table population helper (ensure_week)  
[x] Add function to compute ISO week start date  
[ ] Add indices review (optimize queries later)  
[ ] Implement upgrade path (schema_version >1 placeholder)  
[ ] Implement manual backup (copy DB to user-selected path)  
[ ] Implement manual restore (validate + replace)  
[ ] Add project archive/unarchive functions  
[x] Add query: active projects list

## 5. Domain Logic

[x] Implement mode normalization utility (case-insensitive)  
[x] Mode upsert with usage_count increment  
[x] Add tag cloud retrieval (alphabetical limited to tag_cloud_limit)  
[x] Add mode suggestions API (distinct list)  
[ ] Add function to purge seldom-used modes (★)

## 6. Tracking Engine

[x] Basic session start/stop  
[x] Idle accumulation (poll-based)  
[x] Integrate ISO week + date assignment on insert  
[x] Enforce 10s discard rule (already in code)  
[x] Add explicit flush_all() at shutdown  
[ ] Add safeguard on crash: recover open session (persist temp file) (★)  
[ ] Implement cleanup of orphaned partial sessions (★)

## 7. Idle & Activity Detection

[x] Implement Windows GetLastInputInfo polling (basic in tray)  
[ ] Configurable poll interval (default 15s)  
[ ] Detect resume event to reset last_activity_ts  
[ ] Edge case: large gap > idle_threshold -> accumulate once, not multiple times  
[ ] Provide debug logging toggle for idle events

## 8. Sleep / Hibernate Handling

[ ] Implement WM_POWERBROADCAST handler (sleep/restore)  
[ ] On sleep: close active session immediately  
[ ] On resume: do NOT auto-restart (or decide)  
[ ] Unit test: simulate long sleep gap

## 9. Project Management UI

[ ] Add minimal UI to add/edit project (code, name)  
[ ] Implement archive toggle  
[ ] Filter archived in dropdown

## 10. Tray Application (PySide6)

[x] Initialize QApplication + system tray icon  
[x] Load icon asset (fallback if missing)  
[x] Tray menu: Quick Modes, Export, Exit  
[ ] Tray menu: Switch Activity full dialog  
[ ] Add Settings, Backup DB, Restore DB  
[x] Tooltip with current mode + project  
[ ] Optional balloon notification on switch (★)

## 11. Switch Activity Dialog

[ ] Project dropdown with type-to-filter  
[ ] Mode input with autocomplete (modes list)  
[ ] Alphabetical tag cloud (limit from settings)  
[x] Quick mode buttons (via menu)  
[ ] Validation (mode not empty)  
[x] Switch triggers session close + new start  
[x] Persist mode usage stats

## 12. Manual Entries

[ ] Manual Add form (date, start, duration, project, mode, idle minutes)  
[ ] Validate duration 10s–24h  
[ ] Reject zero length  
[ ] Mark source=manual  
[ ] Manual Replace (clone base row with source=manual_replace; keep original)  
[ ] Reporting layer chooses latest replacement where replaced_by present (★)  
[ ] UI warns about overlaps but allows them

## 13. Data Queries & Reporting

[ ] Implement raw seconds aggregation per (project, mode, day, week)  
[ ] Rounding at reporting (nearest minute, 30s up)  
[ ] Weekly summary provider  
[ ] Top modes provider  
[ ] Active streak / last switch info (★)

## 14. Charts

[ ] Implement Projects pie chart (week)  
[ ] Implement Modes bar chart (sorted descending time)  
[ ] Provide export to PNG (★)  
[ ] Handle no-data gracefully

## 15. Exports

[ ] CSV export (full week aggregated)  
[x] CSV export (POC raw entries)  
[ ] Weekly HTML report (summary + charts embed)  
[ ] Export command in tray menu (expand)  
[ ] Save to user-chosen path

## 16. Localization (Hooks Only Initial)

[ ] Introduce tr() function wrapper  
[ ] External messages file (English baseline)  
[ ] Placeholder catalogs for zh (Simplified) & hi (Hindi)  
[ ] Language selection in settings (reload minimal)  
[ ] Fallback to English

## 17. Startup at Login

[ ] Implement create/remove shortcut in Startup folder  
[ ] Toggle in Settings UI  
[ ] Verify idempotent behavior

## 18. Logging & Debug

[x] Action logging on every session start/close  
[ ] Log manual entry create/replace  
[ ] CLI debug flag (--debug) enabling verbose tray logs  
[x] Rotate files (already done)  
[ ] Add simple log viewer in Settings (★)

## 19. Security (Future Azure AD Placeholder)

[ ] Abstract credential store interface  
[ ] Implement simple encrypted blob store (cryptography) (★)  
[ ] Do not log tokens  
[ ] Feature flag off by default

## 20. Quality & Testing

[ ] Unit tests: mode normalization, project upsert, short session discard  
[ ] Unit tests: idle accumulation logic  
[ ] Unit tests: week calculation  
[ ] Unit tests: rounding rules  
[ ] Integration: create sessions across idle boundary  
[ ] Integration: manual replace & reporting  
[ ] UI smoke test (launch + shutdown) (★)

## 21. Packaging & Distribution

[x] Verify PyInstaller basic build  
[ ] Add custom spec file (optimize includes)  
[ ] Embed version (**version**)  
[ ] Test onefile vs dir build size/startup  
[ ] Document build steps in README  
[ ] Optional code signing (★)

## 22. Documentation

[ ] Expand README with feature list & screenshots  
[ ] Add USAGE.md (common workflows)  
[ ] Add TROUBLESHOOTING.md  
[ ] Include localization guide (★)

## 23. Performance

[ ] Measure idle poll CPU usage  
[ ] Optimize DB writes (batch if needed)  
[ ] Index review after sample data  
[ ] Memory footprint check with tracemalloc (★)

## 24. Cleanup & Polish

[ ] Consistent naming & code style pass  
[ ] Remove dead code / experimental flags  
[ ] Final license headers where needed  
[ ] Tag v0.1.0 release

## 25. Stretch / Backlog

[ ] Jira integration (Azure AD)  
[ ] Pomodoro mode  
[ ] Cloud sync / encryption  
[ ] AI window-title mode suggestions  
[ ] Automatic updates  
[ ] Advanced overlap resolution

---

Focus now: Implement Switch Activity dialog (11), manual entries (12 minimal), proper export (15), startup integration (17).
