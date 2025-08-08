# PLAN.md – Implementation Plan for VirtualManWeek Time Tracking System

## Open Questions / Clarifications Needed

1. UI toolkit preference? (Options: PySide6/Qt, Tkinter, wxPython, PySimpleGUI, custom Electron/Python bridge) – affects tray icon + dialog + charts.
   A: No preference. What seems to be the best. PyQt might work?

2. Minimum supported Windows version? (Win10? Win11?)
   A: Windows 11 should be good.

3. Packaging preference: PyInstaller, Nuitka, Briefcase, cx_Freeze?
   A: PyInstaller but anything possible

4. Storage location for SQLite DB? (AppData/Roaming/VirtualManWeek vs portable local folder)
   A: AppData is good.

5. Need multi-user separation on same machine? (Per Windows user profile assumed?)
   A: Yes, personal for current user only.

6. Time resolution: per minute, or per second internally? (Spec mentions minutes; suggest second-level capture, aggregate to minutes)
   A: Time resolution is seconds but round to minutes after summing.

7. Idle detection timeout fixed at 5 minutes or configurable?
   A: Could be configurable in the database, but let's say 5 minutes.

8. Definition of "idle" – only no keyboard/mouse events, or also full-screen meeting apps detection, screen lock, sleep, RDP disconnect?
   A: Idle means no keyboard or mouse activity detected in 5 mins. In case of disconnect, stop logging data and save the recording - or at least stop measuring minutes.

9. Handling system sleep/hibernate: treat sleep interval as idle or cut the active segment at sleep start?
   A: Sleep is idle, unless user disconnects from the server, then timer must stop.

10. What happens if user changes project/mode very rapidly (<1 minute)? Record minimal 1-minute entries or allow zero-duration filtering?
    A: Time resolution is seconds so that should solve it.

11. Manual override precedence rules: Does a manual Modify fully replace an auto row or annotate it? Keep history of modifications?
    A: The original records will stay, manual entries affect only on the data display or export. Export not yet implemented.

12. Are overlapping manual Add entries allowed? If yes, how aggregated in weekly totals?
    A: In case of overlap, manual entries will win. Notify user of overlap when adding manual entry.

13. Project fields: Only (name, code) or also description, archived flag?
    A: Just the name and code is enough. Project can be arcived though.

14. How large can the project list be? (Performance considerations for autocomplete)
    A: No limits there right now.

15. CSV project import format (columns, delimiters, header names, encoding) – need sample.
    A: Let's forget the CSV import for now, you can either manually add or remove projects or use the possible Azure AD import.

16. Jira integration scope (if implemented): only fetch assigned issues, or also epics/subtasks? Frequency of refresh?
    A: Fetch only issues or tasks that are assigned to the user.

17. Azure AD login vs direct Jira API token? (Auth flow affects complexity)
    A: Only Azure AD if available.

18. Should "Mode" (activity type) be constrained to uploaded list + historical free-text, or always free-text with suggestions?
    A: Mode is free text, so no constraints there, but autocomplete and tags allow granularity.

19. Tag cloud size limit / ranking metric (frequency over last N days, overall, decay function?)
    A: What feels good, I was thinking maybe 10 max and then open window to select or remove.

20. Week definition: ISO week (Mon-Sun) or locale dependent? (Important for DB grouping)
    A: So the week will be ISO week ( Mon - Sun ) here.

21. Timezone handling: store UTC with local offset, or store naive local times?
    A: Use just the Date + Duration. The time part (if the saving happened at 8am or 10am) is not important, but it can be saved.

22. Daylight saving transitions: how to handle ambiguous/missing hours?
    A: Consider just the Date and hours, the exact time is not important.

23. Charts required: bar by project per day, total week pie by project, stacked bar by mode? Export to PNG/PDF?
    A: Time spent per mode could be a bar chart in sorted order. Time spent per project might be a pie chart.

24. Export/reporting needed? (CSV/Excel) Format?
    A: Export HTML report in the beginning of the week. CSV export also. CSV export of the summary data.

25. Any compliance constraints (PII, data retention, encryption at rest)?
    A: Not at this point.

26. Logging verbosity & location. Rotating logs?
    A: There can be an action log.

27. Automatic updates required?
    A: Not at this point. Maybe add later.

28. Testing level expected: unit tests only, or integration + UI tests?
    A: If possible, write unit test for the data handling parts.

29. Localization/i18n needed?
    A: English, Chinese, Indian

30. Accessibility requirements for dialog & color choices?
    A: Keep it simple. If possible to select accessible colors, would be good

31. Performance target: max memory footprint / CPU overhead while tracking idle?
    A: Should be quite good, avoid exessive CPU use.

32. Security constraints: code signing certificate for the executable?
    A: Not at this point.

Additional clarifications recommended:

Q: Rounding rule: Aggregate seconds then round per entry or only at report (floor, nearest, bankers, always up)?
A: Round at report.

Q: Minimum granularity display: show seconds or only whole minutes?
A: Display granularity can be minutes, but use hours like 5h 30min instead of 330 mins when showing results in charts. The exported CSV data can have the measurements in minutes.

Q: Splitting at midnight: forbid cross‑day entries or always split automatically (need start/end timestamps even if reports use date+duration).
A: The start timestamp will determine which day the entry belongs, so if the activity starts at 23pm and lasts 2 hours it will belong to the previous day. It is possible to have over 24 hour days, but here it does not matter really because we are mostly interested in the time spent per mode.

Q: Overlap resolution algorithm: when manual wins, do you (a) hide overlapped auto portions, (b) subtract overlap, or (c) mark whole auto entry shadowed?
A: Change: do not worry about the overlaps at this point. Invalid entries are users problem.

Q: Manual entry validation: max duration? allow zero length?
A: Zero length not allowed. Max duration is 24 hours.

Q: Mode normalization: case-insensitive uniqueness? Trim whitespace?
A: Case insensitive uniqueness. So if user writes "Lunch" and then "lunch" they should select the same mode.

Q: Project code uniqueness & case sensitivity; archive behavior (hide from dropdown? reversible?).
A: Case insensitive uniqueness here too.

Q: Idle segment accounting: accumulate idle seconds inside an active entry vs split into a separate “(Idle)” entry? (Spec implies append “(Idle)” to mode—confirm).
A: The activity recording will be on the same entry but for the "Idle time" column

Q: Idle polling interval (e.g. every 15s / 30s) and CPU target; debounce strategy.
A: Decide what is best, not sure.

Q: Sleep detection: if system sleeps > idle threshold, continue same entry flagged with idle minutes or close at sleep start? (Answer leans to counting as idle—confirm finish behavior).
A: If system goes to sleep and the program can not record, then cut the recording ( I guess the recording should automatically stop if the program can not write new data to the active row)

Q: Rapid switches: keep entries of a few seconds—any minimum filter for noise?
A: Remove entries less than 10 seconds

Q: Source field values: choose exact enum strings (auto, manual, modified) and whether “modified” refers only to new replacement entry.
A: Not sure what this means. Choose a solid strategy

Q: Exports: Week HTML report exact columns & ordering; CSV summary columns (project, mode, minutes, idle_minutes?). Include archived projects?
A: Include what is active on exported week.

Q: Localization: target languages (English + which specifically: Simplified Chinese? Hindi?) and approach (gettext, JSON catalogs).
A: Yes.

Q: Tag cloud ordering: frequency descending; tie-break by last_used_at? Removal UX (right-click, x button?).
Frequency decay: apply? (If not, simple counts only).
A: Order alphabetically

Q: Settings persistence: JSON file vs settings table canonical; precedence rules.
A: Can be stored in the roaming data JSON

Q: Logging: action log fields (timestamp, event_type, project_id, mode, duration, idle_flag) and retention/rotation size.
A: Ok.

Q: Backup strategy: periodic DB copy? On schema migration only?
A: Manual backup using "Save SQL database" and copy to some other folder

Q: Corruption recovery: auto rename corrupt DB then recreate? User prompt?
A: Manual restore databse option

Q: WAL mode & vacuum schedule: enable WAL? periodic vacuum weekly?
A: No need.

Q: Security of tokens (Azure AD): stored encrypted or plain? If encrypted, key management?
A: If storing, alway encrypted

Q: Azure AD scope refresh interval & silent token refresh strategy (msal cache path).
A: If implemented, decide this

Q: Accessibility: keyboard-only navigation of tray dialog; high contrast mode toggle?
A: Not implemented now, maybe later.

Q: Performance budget specifics: target idle loop CPU < 0.5% with polling interval X.
A: No idea.

Q: Testing: deterministic clock/time injection needed—introduce TimeProvider interface?
A: Keep it simple.

Q: Versioning: semantic version sourced from git tag; fallback 0.0.dev+hash.
A: Keep it simple now.

Q: CLI debug mode: flag to print state transitions for troubleshooting?
A: Can be done

Q: Startup at login: implement via Startup folder shortcut or registry Run key? Provide toggle.
A: This would be important. Think about this, and select good strategy

Q: Uninstall cleanup: remove DB/logs or leave user data?
A: Yes.

Q: Telemetry (if later): ensure opt-in flag reserved now.
A: No telemetry

Q: License choice (MIT, Apache 2.0) to add before publishing.
A: MIT.

Q: Next step: Confirm/answer the above, then lock the schema & start bootstrap (Milestone 1). Want a distilled checklist to proceed? Let me know.
A: Proceed.

---

## High-Level Architecture

- Core Tracker Service (state machine handling current project, mode, timing, idle detection)
- Input Capture Layer (Windows hooks for keyboard/mouse idle detection)
- Persistence Layer (SQLite + migration manager)
- Import Layer (Projects CSV parser, optional Jira sync & Azure AD auth abstraction)
- Domain Model (Project, ModeSuggestion, TimeEntry, ManualEntry, OverrideRecord, WeekIndex)
- Tray UI Layer (Tray icon, context menu, quick actions, open dialogs panels)
- Dialog/UI Components (Entry switcher, Manual edit dialog, Week chart window, Settings)
- Autocomplete & Tag Cloud Engine (frequency analysis + decay weighting)
- Reporting/Export Module (Aggregations + output formatting)
- Packaging/Bootstrap (Single exe launcher, config directories)
- Configuration & Preferences (JSON or table; persists user choices)
- Logging (structured logging with rotation)

## Data Model (Initial Draft)

Tables:

1. projects(id PK, code TEXT, name TEXT, active INT, created_at, updated_at)
2. modes(id PK, label TEXT UNIQUE, usage_count INT, last_used_at)
3. weeks(id PK, iso_year INT, iso_week INT, start_date DATE, created_at)
4. time_entries(id PK, week_id FK, date DATE, start_ts INT(epoch), end_ts INT(epoch), active_minutes INT, project_id FK NULL, mode_label TEXT, idle_minutes INT DEFAULT 0, source TEXT CHECK(auto|manual|modified), replaced_by INT NULL)
5. overrides(id PK, original_entry_id FK NULL, action TEXT(add|modify), created_at, note TEXT)
6. settings(key TEXT PRIMARY KEY, value TEXT)
7. imports(id PK, type TEXT(csv_jira|csv_projects|jira_api), status TEXT, detail TEXT, created_at)
   Indexes: time_entries(week_id, date), modes(usage_count DESC), projects(code)

## Core State Machine

States: Idle, Active(project+mode), Transitioning (during dialog). Events: UserSwitch, IdleTimeout, ResumeActivity, Sleep, Wake, ManualModify.

## Planned Phases & Tasks

1. Project Bootstrap
   - Initialize repo structure (src/, tests/, assets/, scripts/)
   - Create virtual environment & requirements baseline
2. Dependency Selection
   - Choose UI toolkit (provisional: PySide6 for tray + charts via matplotlib/pyqtgraph)
   - Choose packaging tool (PyInstaller)
   - Add libraries: SQLAlchemy (or raw sqlite3), watchdog (optional), pywin32 / pynput for idle, matplotlib, python-dateutil, tzdata
3. Environment Setup
   - requirements.txt / pyproject.toml
   - Pre-commit hooks (black, isort, flake8, mypy optional)
4. Configuration Management
   - Implement AppDirs path resolution
   - JSON settings loader + defaults
5. Database Layer
   - Migration system (alembic lightweight or simple version table)
   - Implement ORM models or raw schema creation
   - CRUD utilities
6. Week Indexing Logic
   - Function: ensure_week_record(dt) -> week_id
7. Idle Detection Module
   - Windows Hooks (GetLastInputInfo) polling loop (every 30s) configurable
   - Emits IdleTimeout/Resume events
8. Tracking Engine
   - Current session object with start_ts, project_id, mode_label
   - On change: close previous entry (compute active + idle minutes)
   - Aggregation & rounding rules
9. Sleep/Hibernate Handling
   - Listen for WM_POWERBROADCAST events (if using hidden window), or poll system uptime delta
   - Split session at sleep start
10. Tray Icon & Menu
    - Base icon loading
    - Menu items: Switch Activity, Quick Modes (Lunch/Meeting/etc), Show Week Chart, Manual Entry, Settings, Exit
11. Activity Switch Dialog
    - Project dropdown (searchable)
    - Mode autocomplete + tag cloud
    - Buttons for quick default modes
12. Autocomplete & Tag Cloud
    - Frequency store (modes table usage_count)
    - Decay algorithm (optional) or trailing 30-day frequency
13. Manual Entry / Modify UI
    - Add new synthetic entry -> time_entries(source=manual)
    - Modify existing -> mark old entry replaced (replaced_by link), insert new (source=modified)
14. Validation Rules
    - Reject negative durations
    - Prevent overlapping manual entries unless allowed config
15. Weekly Aggregations
    - Query builder returning per-project totals, per-mode totals, daily breakdown
16. Charting Window
    - Tabs: Projects, Modes
    - Matplotlib stacked bar (days) + pie chart total week
17. CSV Importer (Projects)
    - Schema detection (columns: code,name)
    - Idempotent insert/update
18. Jira Integration (Optional Phase)
    - Azure AD / OAuth flow (msal library) OR API token config
    - Fetch assigned issues, map to projects table
19. Settings UI
    - Idle minutes threshold, UI theme, start on login
20. Startup Registration
    - Option to add shortcut to Windows Startup folder
21. Logging
    - Rotating log (10 files x 1MB) using logging.handlers
22. Error Handling & Telemetry (optional)
    - Graceful fallback when DB locked/corrupted (auto backup & rebuild)
23. Export / Reporting
    - Export current week to CSV (project, mode, minutes)
24. Testing
    - Unit tests: time splitting, idle detection simulation, week indexing
    - Integration tests: DB migrations, import CSV
25. Code Quality
    - Lint & format CI workflow (GitHub Actions) (if repo remote)
26. Packaging
    - PyInstaller spec file customization (icon embedding, exclude tests)
    - Version stamping (git tag -> **version**)
27. Distribution
    - Build artifact folder (dist/VirtualManWeek.exe)
    - Optionally create installer (Inno Setup or MSIX) (future)
28. Documentation
    - README usage section
    - User Guide (docs/) with screenshots
29. Security and Privacy Review
    - Ensure no sensitive Jira tokens logged
30. Performance Optimization
    - Ensure idle poll loop low CPU
31. Future Enhancements (Backlog)
    - Pomodoro mode
    - Cloud sync (OneDrive) / encryption
    - Multi-monitor focus-based mode suggestions
    - AI suggestion of mode based on active window title

## File / Directory Structure (Proposed)

- src/virtualmanweek/
  - **init**.py
  - main.py
  - config.py
  - db/ (models.py, migrations/)
  - tracking/ (engine.py, idle.py, state.py)
  - ui/ (tray.py, dialogs.py, charts.py, resources/)
  - importers/ (csv_projects.py, jira.py)
  - reporting/ (aggregate.py, export.py)
  - utils/ (time.py, logging.py)
- tests/
- assets/icon.ico
- requirements.txt / pyproject.toml
- scripts/build.ps1

## Milestone Breakdown

M1: Bootstrap + DB + basic tracking (no UI switch, just logs)
M2: Tray icon + switch dialog + idle detection
M3: Autocomplete + Tag cloud + manual entries
M4: Weekly charts + export
M5: CSV import + packaging
M6: (Optional) Jira + Azure AD
M7: Polishing, docs, installer

## Risk Register (Key)

- Idle detection reliability (mitigation: poll GetLastInputInfo + test)
- Sleep detection edge cases (mitigation: timestamp gaps)
- Data corruption (mitigation: WAL mode + backups)
- Packaging size (Qt large; consider alternative if too big)
- Jira auth complexity (optional milestone)

## Success Criteria

- Accurate per-minute aggregation over a week (error < 1 minute vs wall clock in test scenarios)
- Idle recognized within 60s after threshold crossed
- Switching activity from tray <= 3 clicks
- App average CPU < 1% idle, memory < 150MB (Qt) or <80MB (lighter UI)

## Immediate Next Actions

1. Confirm open questions (esp. UI toolkit, packaging, idle policy)
2. Create project skeleton & requirements draft
3. Implement config + logging scaffolding
4. Implement DB schema & migration baseline
5. Implement minimal tracking engine + CLI test harness

(End of Plan)
