from __future__ import annotations
import sys
import time
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QStyle, QInputDialog, QFileDialog, QDialog
from PySide6.QtGui import QIcon, QAction, QActionGroup, QCursor, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtCore import QTimer, QRect, Qt
import time  # ensure time available for formatting
import webbrowser  # new for HTML fallback
from datetime import datetime, timedelta

from ..config import Settings, appdata_root
from ..tracking.engine import Tracker
from ..db import models
from .project_dialog import ProjectDialog  # new import
from .mode_switch_dialog import ModeSwitchDialog  # mode switching with manual time
from .mode_dialog import ModeDialog  # mode management dialog
from .export_dialog import ExportDateDialog  # date range selection for exports
from .edit_hours_dialog import EditHoursDialog  # edit today's time entries
from .startup_dialog import StartupDialog  # startup project and mode selection
from ..reporting import charts  # HTML-only chart export
from ..reporting.charts import _fmt_time_short  # Import time formatting function
import shutil  # for DB export/import
import os  # for database file operations

# Windows idle detection
try:
    import ctypes
    import ctypes.wintypes as wintypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    GetLastInputInfo = ctypes.windll.user32.GetLastInputInfo  # type: ignore
    GetTickCount = ctypes.windll.kernel32.GetTickCount  # type: ignore

    def get_idle_seconds() -> int:
        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not GetLastInputInfo(ctypes.byref(lii)):
            return 0
        millis = GetTickCount() - lii.dwTime
        return millis // 1000
except Exception:  # pragma: no cover
    def get_idle_seconds() -> int:  # type: ignore
        return 0

class TrayApp:
    def __init__(self):
        self.settings = Settings.load()
        # Create QApplication early to allow dialogs during bootstrap
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # keep running with only tray
        # Ensure a database is selected/created before tracker starts
        self._bootstrap_database_selection()
        # Initialize default modes if not already done
        models.initialize_default_modes()
        self.tracker = Tracker(self.settings)
        # Track current project selection for quick switching
        self.current_project_id: Optional[int] = None
        self._project_label_by_id: dict[int, str] = {}
        self._active_icon = None
        self._idle_icon = None
        self._stopped_icon = None  # new stopped icon
        self._last_icon_minute = -1  # Track when we last updated the clock icon
        self._create_tray()
        self._setup_poll_timer()
        # Show startup dialog for project and mode selection
        self._show_startup_dialog()

    def _bootstrap_database_selection(self) -> None:
        """On first run or missing DB, ask user to create/select DB. Apply selection and persist."""
        # If settings has a db path and it exists, apply override and return
        dbp = self.settings.database_path
        if dbp:
            p = Path(dbp)
            if p.exists():
                models.set_db_path(p)
                return
        # Ask user: Create or Select, else exit
        msg = QMessageBox()
        msg.setWindowTitle("Select Database")
        msg.setText("Create a new database or select an existing one to continue.")
        create_btn = msg.addButton("Create New", QMessageBox.AcceptRole)
        select_btn = msg.addButton("Select Existing", QMessageBox.ActionRole)
        cancel_btn = msg.addButton("Exit", QMessageBox.RejectRole)
        msg.setIcon(QMessageBox.Question)
        msg.exec()
        clicked = msg.clickedButton()
        if clicked == cancel_btn:
            # Exit application early
            self.app.quit()
            sys.exit(0)
        if clicked == create_btn:
            # Suggest appdata folder + default name
            suggested = str(appdata_root() / "VirtualManWeek.sqlite3")
            fname, _ = QFileDialog.getSaveFileName(
                None,
                "Create New Database",
                suggested,
                "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*.*)",
            )
            if not fname:
                self.app.quit()
                sys.exit(0)
            path = Path(fname)
            self._apply_database(path, notify=False)
            return
        if clicked == select_btn:
            start_dir = str(appdata_root())
            fname, _ = QFileDialog.getOpenFileName(
                None,
                "Select Existing Database",
                start_dir,
                "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*.*)",
            )
            if not fname:
                self.app.quit()
                sys.exit(0)
            path = Path(fname)
            self._apply_database(path, notify=False)
            return

    def _show_startup_dialog(self) -> None:
        """Show startup dialog for project and mode selection"""
        dialog = StartupDialog()
        if dialog.exec() == QDialog.Accepted:
            project_id, mode_label = dialog.get_selection()
            # Set current project for future operations
            self.current_project_id = project_id
            # Start tracking with selected project and mode
            self.tracker.start(project_id=project_id, mode_label=mode_label)
            self._apply_icon(idle=(mode_label.lower() == "idle"), force_update=True)
        else:
            # User cancelled - start with default (No Project, Idle)
            self.current_project_id = None
            self.tracker.start(project_id=None, mode_label="Idle")
            self._apply_icon(idle=True, force_update=True)

    def _get_today_work_seconds(self) -> int:
        """Get total active seconds worked today (excluding idle time)."""
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        with models.connect() as conn:
            cur = conn.cursor()
            # Sum active_seconds and manual_seconds, but exclude idle_seconds
            # Also exclude entries where mode_label is 'Idle' (case-insensitive)
            cur.execute("""
                SELECT COALESCE(SUM(active_seconds), 0) + COALESCE(SUM(manual_seconds), 0)
                FROM time_entries 
                WHERE date = ? AND LOWER(mode_label) != 'idle'
            """, (today,))
            result = cur.fetchone()
            return result[0] if result and result[0] else 0

    def _is_dark_theme(self) -> bool:
        """Detect if the system is using a dark theme."""
        try:
            # On Windows, check registry for dark theme preference
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 
                               r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return value == 0  # 0 = dark theme, 1 = light theme
        except Exception:
            # Fallback: assume light theme if detection fails
            return False

    def _gen_clock_icon(self, bg: QColor, hand: QColor, text_color: QColor, outline: QColor = QColor("#222")) -> QIcon:
        """Generate a clock icon with hands showing the current time and work progress."""
        import math
        from datetime import datetime
        
        size = 32
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        
        center = size // 2
        
        # Get today's work time for progress indicator
        today_work_seconds = self._get_today_work_seconds()
        today_work_minutes = today_work_seconds / 60.0
        today_work_hours = today_work_minutes / 60.0
        
        # Detect system theme and set progress color accordingly
        is_dark_theme = self._is_dark_theme()
        if today_work_hours >= 12:
            progress_color = QColor("#FF4444")  # Red for overtime (same for both themes)
        else:
            # Use white for dark theme, black for light theme
            progress_color = QColor("#FFFFFF") if is_dark_theme else QColor("#000000")
        
        # Don't track beyond 24 hours
        if today_work_hours >= 24:
            today_work_minutes = 24 * 60
            today_work_hours = 24
        
        # Draw work progress arcs
        if today_work_hours >= 1:
            # Hour progress markers - 2 pixels thick, drawn close to the clock for visibility
            clock_radius = (size - 6) // 2  # Clock face radius - 2 pixels smaller than before
            progress_radius = clock_radius + 3  # Progress arcs 3 pixels outside the clock (reduced from 6)
            hour_rect = QRect(center - progress_radius, center - progress_radius,
                            progress_radius * 2, progress_radius * 2)
            
            # Draw hour markers - 12 divisions (30 degrees each)
            completed_hours = int(today_work_hours)
            for hour in range(1, min(completed_hours + 1, 13)):  # Max 12 hours for first cycle
                # Each hour is 30 degrees (360/12)
                hour_angle = hour * 30
                p.setPen(QPen(progress_color, 2))  # 2 pixels thick - reduced from 8
                p.drawArc(hour_rect, (90 - hour_angle) * 16, -30 * 16)
            
            # If we're in the second 12-hour cycle (overtime), draw additional markers
            if today_work_hours >= 12:
                overtime_hours = int(today_work_hours - 12)
                for hour in range(1, min(overtime_hours + 1, 13)):
                    hour_angle = hour * 30
                    p.setPen(QPen(progress_color, 2))  # 2 pixels thick for overtime
                    p.drawArc(hour_rect, (90 - hour_angle) * 16, -30 * 16)
        
        # Draw main clock circle (2 pixels smaller than before)
        p.setBrush(bg)
        p.setPen(QPen(outline, 2))
        p.drawEllipse(3, 3, size - 6, size - 6)
        
        # Hour markers (12, 3, 6, 9) - adjusted for smaller clock
        p.setPen(QPen(hand, 2))
        for hour in [12, 3, 6, 9]:
            angle = math.radians((hour - 3) * 30)  # -3 to start from 12 o'clock
            x = center + int(9 * math.cos(angle))  # Reduced from 11 to 9 for smaller clock
            y = center + int(9 * math.sin(angle))  # Reduced from 11 to 9 for smaller clock
            p.drawPoint(x, y)
        
        # Get current time
        now = datetime.now()
        hours = now.hour % 12
        minutes = now.minute
        
        # Calculate hand angles (in radians, starting from 12 o'clock)
        hour_angle = math.radians((hours + minutes / 60.0) * 30 - 90)
        minute_angle = math.radians(minutes * 6 - 90)
        
        # Draw hour hand (shorter, thicker) - adjusted for smaller clock
        p.setPen(QPen(hand, 3))
        hour_length = 5  # Reduced from 7 to 5 for smaller clock
        hour_x = center + int(hour_length * math.cos(hour_angle))
        hour_y = center + int(hour_length * math.sin(hour_angle))
        p.drawLine(center, center, hour_x, hour_y)
        
        # Draw minute hand (longer, thinner) - adjusted for smaller clock
        p.setPen(QPen(hand, 2))
        minute_length = 9  # Reduced from 11 to 9 for smaller clock
        minute_x = center + int(minute_length * math.cos(minute_angle))
        minute_y = center + int(minute_length * math.sin(minute_angle))
        p.drawLine(center, center, minute_x, minute_y)
        
        # Center dot
        p.setPen(QPen(hand, 1))
        p.setBrush(hand)
        p.drawEllipse(center - 1, center - 1, 2, 2)
        
        p.end()
        return QIcon(pm)

    def _create_stop_icon(self) -> QIcon:
        """Create a custom stop icon that matches the current theme."""
        size = 16
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))  # Transparent background
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        
        # Use theme-appropriate color
        is_dark_theme = self._is_dark_theme()
        icon_color = QColor("#FFFFFF") if is_dark_theme else QColor("#333333")
        
        # Draw a stop square (rectangle with slightly rounded corners)
        margin = 3
        rect_size = size - (margin * 2)
        p.setBrush(icon_color)
        p.setPen(QPen(icon_color, 1))
        p.drawRoundedRect(margin, margin, rect_size, rect_size, 1, 1)
        
        p.end()
        return QIcon(pm)

    def _create_tray(self):
        # Color palette: green active, yellow idle, red stopped
        self.active_bg = QColor("#2E8B57")   # green
        self.active_hand = QColor("#FFFFFF")
        self.active_text = QColor("#FFFFFF")
        self.idle_bg = QColor("#FFC107")     # yellow
        self.idle_hand = QColor("#333333")
        self.idle_text = QColor("#333333")
        self.stopped_bg = QColor("#C0392B")  # red
        self.stopped_hand = QColor("#FFFFFF")
        self.stopped_text = QColor("#FFFFFF")
        
        # Create initial icons (will be updated dynamically)
        self._active_icon = self._gen_clock_icon(self.active_bg, self.active_hand, self.active_text)
        self._idle_icon = self._gen_clock_icon(self.idle_bg, self.idle_hand, self.idle_text)
        self._stopped_icon = self._gen_clock_icon(self.stopped_bg, self.stopped_hand, self.stopped_text)
        self.tray = QSystemTrayIcon(self._idle_icon, self.app)
        self.tray.activated.connect(self._on_tray_activated)  # left-click handler
        self.menu = QMenu()

        # Exit at the top for easy access
        quit_act = QAction("Exit", self.menu)
        quit_act.triggered.connect(self.quit)
        self.menu.addAction(quit_act)
        self.menu.addSeparator()

        self.action_current = QAction("Current: Idle", self.menu)
        self.action_current.setEnabled(False)
        self.menu.addAction(self.action_current)

        # Add Stop Tracking action right under Current with a custom stop icon
        self.stop_act = QAction("Stop Tracking", self.menu)
        # Create a custom stop icon that matches the theme
        stop_icon = self._create_stop_icon()
        self.stop_act.setIcon(stop_icon)
        self.stop_act.triggered.connect(self.stop_tracking)
        self.menu.addAction(self.stop_act)
        
        self.menu.addSeparator()

        # Dynamic switch menu
        self.switch_menu = self.menu.addMenu("Switch Mode")
        self._rebuild_switch_menu()

        idle_act = QAction("Set Idle", self.menu)
        idle_act.triggered.connect(lambda: self.switch_mode("Idle"))
        self.menu.addAction(idle_act)

        # Projects submenu: quick select + manage
        self.projects_menu = self.menu.addMenu("Projects")
        self.projects_menu.aboutToShow.connect(self._rebuild_projects_menu)
        self._rebuild_projects_menu()
        
        # Edit Hours
        edit_hours_act = QAction("Edit Hours", self.menu)
        edit_hours_act.setIcon(self.menu.style().standardIcon(QStyle.SP_FileDialogDetailedView))
        edit_hours_act.triggered.connect(self.open_edit_hours)
        self.menu.addAction(edit_hours_act)
        
        self.menu.addSeparator()

        # Export menu
        export_menu = self.menu.addMenu("Export")
        csv_act = QAction("CSV...", export_menu)
        csv_act.triggered.connect(self.export_week_csv)
        export_menu.addAction(csv_act)
        html_act = QAction("HTML...", export_menu)
        html_act.triggered.connect(self.show_mode_distribution)
        export_menu.addAction(html_act)

        # Database menu with available databases
        self.admin_menu = self.menu.addMenu("Database")
        self.admin_menu.aboutToShow.connect(self._rebuild_database_menu)
        self._rebuild_database_menu()
        
        self.menu.addSeparator()
        
        # Database info at the bottom (non-clickable)
        self.action_database = QAction("", self.menu)
        self.action_database.setEnabled(False)
        self.menu.addAction(self.action_database)

        self.tray.setContextMenu(self.menu)
        
        # Set initial tooltip with today's work time
        today_work_seconds = self._get_today_work_seconds()
        today_work_str = _fmt_time_short(today_work_seconds)
        self.tray.setToolTip(f"VirtualManWeek\nToday's Total: {today_work_str}")
        
        self.tray.show()

    def _get_available_databases(self):
        """Get list of available database files in the AppData folder"""
        try:
            db_folder = appdata_root()
            if not db_folder.exists():
                return []
            
            databases = []
            for file_path in db_folder.glob("*.db"):
                if file_path.is_file():
                    databases.append({
                        'name': file_path.stem,
                        'path': str(file_path),
                        'is_current': str(file_path) == self.settings.database_path
                    })
            
            # Sort alphabetically, but put current database first
            databases.sort(key=lambda x: (not x['is_current'], x['name'].lower()))
            return databases
        except Exception:
            return []

    def _rebuild_switch_menu(self):
        """Populate the switch mode submenu with modes from the current database."""
        self.switch_menu.clear()
        # Load all modes from current database
        try:
            all_modes = models.mode_suggestions()
        except Exception:
            all_modes = []
        
        # Add all modes from database
        for mode in sorted(all_modes, key=lambda s: s.lower()):
            act = QAction(mode, self.switch_menu)
            act.triggered.connect(lambda checked=False, m=mode: self.switch_mode(m))
            self.switch_menu.addAction(act)
        # Final separator + edit modes
        self.switch_menu.addSeparator()
        edit_act = QAction("Edit...", self.switch_menu)
        edit_act.triggered.connect(self.open_modes)
        self.switch_menu.addAction(edit_act)

    def _rebuild_projects_menu(self):
        self.projects_menu.clear()
        # Build cache from DB
        try:
            rows = models.list_active_projects()
        except Exception:
            rows = []
        self._project_label_by_id = {}
        for r in rows:
            pid = r.get('id')
            code = (r.get('code') or '').strip()
            name = (r.get('name') or '').strip()
            label = code if code else name if name else str(pid)
            if code and name:
                label = f"{code} - {name}"
            if isinstance(pid, int):
                self._project_label_by_id[pid] = label
        # Action group for radio behavior
        grp = QActionGroup(self.projects_menu)
        grp.setExclusive(True)
        # None option
        none_act = QAction("(No Project)", self.projects_menu)
        none_act.setCheckable(True)
        none_act.setChecked(self.current_project_id is None)
        none_act.triggered.connect(self.select_no_project)
        grp.addAction(none_act)
        self.projects_menu.addAction(none_act)
        # Project items
        if rows:
            for r in rows:
                pid = r['id']
                label = self._project_label_by_id.get(pid, str(pid))
                act = QAction(label, self.projects_menu)
                act.setCheckable(True)
                act.setChecked(self.current_project_id == pid)
                act.triggered.connect(lambda checked=False, _pid=pid: self.select_project(_pid))
                grp.addAction(act)
                self.projects_menu.addAction(act)
        else:
            dummy = QAction("(No projects yet)", self.projects_menu)
            dummy.setEnabled(False)
            self.projects_menu.addAction(dummy)
        # Footer actions
        self.projects_menu.addSeparator()
        manage = QAction("Manage Projects...", self.projects_menu)
        manage.triggered.connect(self.open_projects)
        self.projects_menu.addAction(manage)

    def _rebuild_database_menu(self):
        """Rebuild the database menu with available databases"""
        self.admin_menu.clear()
        
        # Get available databases
        available_dbs = self._get_available_databases()
        
        # Add available databases at the top
        if available_dbs:
            for db_info in available_dbs:
                db_name = db_info['name']
                if db_info['is_current']:
                    # Mark current database with a bullet point
                    action_text = f"● {db_name} (current)"
                    action = QAction(action_text, self.admin_menu)
                    action.setEnabled(False)  # Current database is not clickable
                else:
                    action = QAction(db_name, self.admin_menu)
                    action.triggered.connect(lambda checked=False, path=db_info['path']: self._switch_to_database(path))
                
                self.admin_menu.addAction(action)
            
            self.admin_menu.addSeparator()
        
        # Database management actions
        create_db_act = QAction("Create Database...", self.admin_menu)
        create_db_act.triggered.connect(self.create_database)
        self.admin_menu.addAction(create_db_act)
        
        select_db_act = QAction("Select Database...", self.admin_menu)
        select_db_act.triggered.connect(self.select_database)
        self.admin_menu.addAction(select_db_act)
        
        self.admin_menu.addSeparator()

        reset_act = QAction("Clear Logged Entries", self.admin_menu)
        reset_act.triggered.connect(self.reset_database)
        self.admin_menu.addAction(reset_act)
        
        export_db_act = QAction("Export Database...", self.admin_menu)
        export_db_act.triggered.connect(self.export_database)
        self.admin_menu.addAction(export_db_act)
        
        import_db_act = QAction("Import Database...", self.admin_menu)
        import_db_act.triggered.connect(self.import_database)
        self.admin_menu.addAction(import_db_act)
    
    def _switch_to_database(self, db_path: str):
        """Switch to a different database"""
        try:
            # Stop current tracking
            self.stop_tracking()
            
            # Update settings
            self.settings.database_path = db_path
            self.settings.save()
            
            # Recreate tracker with new database
            self.tracker = Tracker(self.settings)
            
            # Update tray display
            self._apply_icon(force_update=True)
            self._update_database_name()
            
            # Rebuild menus to reflect new database
            self._rebuild_switch_menu()
            self._rebuild_projects_menu()
            self._rebuild_database_menu()
            
            # Show startup dialog for new database
            self._show_startup_dialog()
            
            # Show notification
            db_name = Path(db_path).stem
            self._notify(f"Switched to database: {db_name}")
            
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to switch database: {e}")

    def _project_display(self, pid: Optional[int]) -> str:
        if pid is None:
            return "None"
        return self._project_label_by_id.get(pid, str(pid))

    def _get_database_name(self) -> str:
        """Get a short display name for the current database"""
        try:
            db_path = models.db_path()
            return db_path.name
        except Exception:
            return "Unknown"

    def _setup_poll_timer(self):
        self.timer = QTimer()
        self.timer.setInterval(1000)  # 1s for live elapsed display
        self.timer.timeout.connect(self._poll_loop)
        self.timer.start()

    def _format_elapsed(self, seconds: int) -> str:
        return _fmt_time_short(seconds)

    def _poll_loop(self):
        # Poll first (with external idle seconds) so sleep gaps & idle are accounted before activity ping
        idle_secs = get_idle_seconds()
        try:
            self.tracker.poll(idle_secs=idle_secs)
        except TypeError:
            # Backward compatibility if older tracker without param
            self.tracker.poll()
        if idle_secs < self.settings.idle_timeout_seconds:
            self.tracker.activity_ping()
        self._update_current_label()

    def _update_current_label(self):
        # Update database info
        db_name = self._get_database_name()
        self.action_database.setText(f"Database: {db_name}")
        
        if self.tracker.active:
            sess = self.tracker.active
            idle_flag = " (idle)" if sess.idle_accum > 0 or sess.mode_label.lower() == "idle" else ""
            proj = self._project_display(sess.project_id)
            elapsed = int(time.time()) - sess.start_ts
            elapsed_str = self._format_elapsed(elapsed)
            self.action_current.setText(f"Current: {sess.mode_label}{idle_flag} / P:{proj} / {elapsed_str}")
            
            # Get today's total work time for tooltip
            today_work_seconds = self._get_today_work_seconds()
            today_work_str = _fmt_time_short(today_work_seconds)
            
            # Enhanced tooltip with database, project info, and today's total
            tooltip_text = f"{sess.mode_label}{idle_flag} - {elapsed_str}\nToday's Total: {today_work_str}\nDB: {db_name}\nProject: {proj}"
            self.tray.setToolTip(tooltip_text)
            
            self._apply_icon(idle=(sess.idle_accum > 0 or sess.mode_label.lower()=="idle"))
            if self.stop_act:
                self.stop_act.setEnabled(True)
                self.stop_act.setText("Stop Tracking")
        else:
            proj = self._project_display(self.current_project_id)
            self.action_current.setText("Current: (stopped)")
            
            # Get today's total work time for tooltip
            today_work_seconds = self._get_today_work_seconds()
            today_work_str = _fmt_time_short(today_work_seconds)
            
            tooltip_text = f"Tracking stopped\nToday's Total: {today_work_str}\nDB: {db_name}\nProject: {proj}"
            self.tray.setToolTip(tooltip_text)
            self._apply_icon(stopped=True)
            if self.stop_act:
                self.stop_act.setEnabled(False)
                self.stop_act.setText("Stopped")

    def _apply_icon(self, idle: bool = False, stopped: bool = False, force_update: bool = False):
        from datetime import datetime
        
        # Only update icon if the minute has changed (to avoid excessive redraws) OR if forced
        current_minute = datetime.now().minute
        if force_update or current_minute != self._last_icon_minute:
            self._last_icon_minute = current_minute
            
            # Regenerate icon with current time
            if stopped:
                icon = self._gen_clock_icon(self.stopped_bg, self.stopped_hand, self.stopped_text)
            elif idle:
                icon = self._gen_clock_icon(self.idle_bg, self.idle_hand, self.idle_text)
            else:
                icon = self._gen_clock_icon(self.active_bg, self.active_hand, self.active_text)
            
            self.tray.setIcon(icon)

    # Helper: save file dialog
    def _select_save_path(self, title: str, default_filename: str, filter_spec: str) -> Optional[Path]:
        default_dir = str(appdata_root())
        suggested = str(Path(default_dir) / default_filename)
        fname, _ = QFileDialog.getSaveFileName(None, title, suggested, filter_spec)
        if not fname:
            return None
        return Path(fname)

    # Helper: open file dialog
    def _select_open_path(self, title: str, filter_spec: str) -> Optional[Path]:
        start_dir = str(appdata_root())
        fname, _ = QFileDialog.getOpenFileName(None, title, start_dir, filter_spec)
        if not fname:
            return None
        return Path(fname)

    # Helper: switch DB and persist setting
    def _apply_database(self, path: Path, notify: bool = True) -> None:
        try:
            if hasattr(self, 'tracker') and self.tracker and self.tracker.active:
                self.tracker.flush_all()
                self.tracker.active = None
            path.parent.mkdir(parents=True, exist_ok=True)
            models.set_db_path(path)
            models.initialize()
            # Initialize default modes for new/switched database
            models.initialize_default_modes()
            self.settings.database_path = str(path)
            self.settings.save()
            if hasattr(self, 'menu') and self.menu:
                self._rebuild_switch_menu()
                if hasattr(self, 'projects_menu'):
                    self._rebuild_projects_menu()
                self._update_current_label()  # This will update database info too
                # Force icon update since tracker is now stopped after database switch
                self._apply_icon(stopped=True, force_update=True)
                # Show startup dialog for project and mode selection when switching databases
                if notify:  # Only show dialog if this is an explicit database switch
                    self._show_startup_dialog()
            if notify:
                self._notify(f"Using database: {path}")
        except Exception as e:
            self._notify(f"Database switch failed: {e}")

    # New: Admin actions to create/select a database
    def create_database(self):
        """Create a new SQLite database file and switch to it."""
        suggested = str(appdata_root() / "VirtualManWeek.sqlite3")
        fname, _ = QFileDialog.getSaveFileName(
            None,
            "Create New Database",
            suggested,
            "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*.*)",
        )
        if not fname:
            return
        self.current_project_id = None
        self._apply_database(Path(fname))

    def select_database(self):
        """Select an existing SQLite database file and switch to it."""
        start_dir = str(appdata_root())
        fname, _ = QFileDialog.getOpenFileName(
            None,
            "Select Existing Database",
            start_dir,
            "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*.*)",
        )
        if not fname:
            return
        self.current_project_id = None
        self._apply_database(Path(fname))

    def _generate_export_filename(self, extension: str) -> str:
        """Generate standardized export filename: VMW_<dbname>_<monday_date>.<ext>"""
        try:
            # Get database name (without extension)
            db_path = models.db_path()
            db_name = db_path.stem
            
            # Get Monday of current week
            today = datetime.now().date()
            days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
            monday = today - timedelta(days=days_since_monday)
            monday_str = monday.strftime('%Y_%m_%d')
            
            return f"VMW_{db_name}_{monday_str}.{extension}"
        except Exception:
            # Fallback to simple filename if something goes wrong
            return f"VMW_export.{extension}"

    # Edit Hours: open dialog to edit today's time entries
    def open_edit_hours(self):
        """Open the Edit Hours dialog"""
        try:
            dialog = EditHoursDialog(self.menu)
            dialog.exec()
        except Exception as e:
            self._notify(f"Failed to open Edit Hours: {e}")

    # Charts: show mode distribution (HTML-only export)
    def show_mode_distribution(self):
        # Show date picker dialog
        dialog = ExportDateDialog(self.menu)
        if dialog.exec() != QDialog.Accepted:
            return
        
        start_date, end_date = dialog.get_date_range()
        description = dialog.get_description()
        
        # Generate filename based on date range
        if description == "this week":
            default_filename = self._generate_export_filename("html")
        elif description == "last week":
            # Use last week's Monday for filename
            last_week_monday = start_date.strftime('%Y_%m_%d')
            try:
                db_path = models.db_path()
                db_name = db_path.stem
                default_filename = f"VMW_{db_name}_{last_week_monday}.html"
            except Exception:
                default_filename = f"VMW_export_{last_week_monday}.html"
        else:
            # Custom range
            start_str = start_date.strftime('%Y_%m_%d')
            if start_date.date() == end_date.date():
                default_filename = f"VMW_export_{start_str}.html"
            else:
                end_str = end_date.strftime('%Y_%m_%d')
                default_filename = f"VMW_export_{start_str}_to_{end_str}.html"
        
        path = self._select_save_path(
            f"Save Chart HTML ({description})", default_filename, "HTML Files (*.html);;All Files (*.*)"
        )
        if not path:
            return
        try:
            charts.export_mode_distribution_html_to(path, start_date, end_date)
            webbrowser.open(path.as_uri())
            self._notify(f"Chart exported to {path} ({description})")
        except Exception as e:
            self._notify(f"Chart export failed: {e}")

    # Export: CSV of entries in date range
    def export_week_csv(self):
        # Show date picker dialog
        dialog = ExportDateDialog(self.menu)
        if dialog.exec() != QDialog.Accepted:
            return
        
        start_date, end_date = dialog.get_date_range()
        description = dialog.get_description()
        
        try:
            rows = models.get_time_entries_for_export(start_date, end_date, limit=2000)
            
            # Generate filename based on date range
            if description == "this week":
                default_filename = self._generate_export_filename("csv")
            elif description == "last week":
                # Use last week's Monday for filename
                last_week_monday = start_date.strftime('%Y_%m_%d')
                try:
                    db_path = models.db_path()
                    db_name = db_path.stem
                    default_filename = f"VMW_{db_name}_{last_week_monday}.csv"
                except Exception:
                    default_filename = f"VMW_export_{last_week_monday}.csv"
            else:
                # Custom range
                start_str = start_date.strftime('%Y_%m_%d')
                if start_date.date() == end_date.date():
                    default_filename = f"VMW_export_{start_str}.csv"
                else:
                    end_str = end_date.strftime('%Y_%m_%d')
                    default_filename = f"VMW_export_{start_str}_to_{end_str}.csv"
            
            path = self._select_save_path(f"Save Time Entries CSV ({description})", default_filename, "CSV Files (*.csv);;All Files (*.*)")
            if not path:
                return
            
            with path.open("w", encoding="utf-8") as f:
                f.write("date,project_id,mode,active_seconds,idle_seconds,manual_seconds,description\n")
                for r in rows:
                    desc = r["description"] or ""
                    if '"' in desc:
                        desc = desc.replace('"', '""')
                    if any(c in desc for c in [',', '\n', '"']):
                        desc_out = f'"{desc}"'
                    else:
                        desc_out = desc
                    manual_secs = r.get("manual_seconds", 0) or 0
                    f.write(
                        f"{r['date']},{r['project_id'] if r['project_id'] is not None else ''},{r['mode_label']},{r['active_seconds']},{r['idle_seconds']},{manual_secs},{desc_out}\n"
                    )
            self._notify(f"Exported {len(rows)} rows to {path} ({description})")
        except Exception as e:
            self._notify(f"Export failed: {e}")

    # Restored handlers and admin actions
    def stop_tracking(self):
        try:
            self.tracker.stop()
        except Exception:
            pass
        self._update_current_label()
        # Force icon update immediately when stopping
        self._apply_icon(stopped=True, force_update=True)

    def switch_mode(self, mode_label: str):
        dialog = ModeSwitchDialog(mode_label)
        if dialog.exec() != QDialog.Accepted:
            return
        
        description, manual_seconds = dialog.get_result()
        proj = getattr(self, 'current_project_id', None)
        
        if self.tracker.active is None:
            self.tracker.start(project_id=proj, mode_label=mode_label, description=description, manual_seconds=manual_seconds)
        else:
            self.tracker.switch(project_id=proj, mode_label=mode_label, description=description, manual_seconds=manual_seconds)
        self._update_current_label()
        # Force icon update immediately when switching modes
        if self.tracker.active:
            self._apply_icon(idle=(self.tracker.active.idle_accum > 0 or self.tracker.active.mode_label.lower()=="idle"), force_update=True)

    def _delete_mode(self, mode_id: int):
        # First get the mode name for the confirmation dialog
        try:
            all_modes = models.list_modes()
            mode_name = None
            for m in all_modes:
                if m['id'] == mode_id:
                    mode_name = m['label']
                    break
            
            if not mode_name:
                self._notify("Mode not found")
                return
                
            # Show confirmation dialog
            resp = QMessageBox.question(
                None,
                "Confirm Mode Deletion",
                f"Are you sure you want to delete the mode '{mode_name}'?\n\nThis will remove the mode from the list but won't affect existing time entries.",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            
            if resp != QMessageBox.Yes:
                return
                
            # Proceed with deletion
            models.delete_mode(mode_id)
            self._notify(f"Mode '{mode_name}' removed")
            
        except Exception as e:
            self._notify(f"Delete failed: {e}")
            return
            
        self._rebuild_switch_menu()

    def _notify(self, message: str):
        self.tray.showMessage("VirtualManWeek", message, QSystemTrayIcon.Information, 4000)

    def open_projects(self):
        dlg = ProjectDialog()
        dlg.exec()
        self._rebuild_projects_menu()

    def open_modes(self):
        dlg = ModeDialog()
        dlg.exec()
        # Refresh mode-related menus after editing
        self._rebuild_switch_menu()

    def select_no_project(self):
        self.current_project_id = None
        if self.tracker.active:
            mode = self.tracker.active.mode_label
            self.tracker.switch(project_id=None, mode_label=mode, description=None)
            # Force icon update when switching projects
            self._apply_icon(idle=(self.tracker.active.idle_accum > 0 or self.tracker.active.mode_label.lower()=="idle"), force_update=True)
        self._update_current_label()

    def select_project(self, project_id: int):
        self.current_project_id = project_id
        if self.tracker.active:
            mode = self.tracker.active.mode_label
            self.tracker.switch(project_id=project_id, mode_label=mode, description=None)
            # Force icon update when switching projects
            self._apply_icon(idle=(self.tracker.active.idle_accum > 0 or self.tracker.active.mode_label.lower()=="idle"), force_update=True)
        self._update_current_label()

    def reset_database(self):
        try:
            _ = models.db_path()
        except Exception as e:
            self._notify(f"DB path error: {e}")
            return
        resp = QMessageBox.question(
            None,
            "Confirm Clear",
            "Are you sure you want to remove ALL the logged entries?\n\nProjects and modes remain, usage counts reset.\nThis cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            self.tracker.flush_all()
        except Exception:
            pass
        try:
            stats = models.clear_logged_entries()
        except Exception as e:
            self._notify(f"Clear failed: {e}")
            return
        self.tracker.active = None
        self._update_current_label()
        self._rebuild_switch_menu()
        self._notify(f"Cleared: {stats['time_entries']} entries, {stats['weeks']} weeks. Modes reset: {stats['modes_reset']}")

    def export_database(self):
        try:
            src = models.db_path()
            if not src.exists():
                self._notify("Database file not found")
                return
        except Exception as e:
            self._notify(f"DB path error: {e}")
            return
        dest = self._select_save_path("Export Database", src.name, "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*.*)")
        if not dest:
            return
        try:
            shutil.copy2(src, dest)
            self._notify(f"Database exported to {dest}")
        except Exception as e:
            self._notify(f"Export failed: {e}")

    def import_database(self):
        """Import a database by copying it to AppData and switching to it."""
        # Select the database file to import
        fname, _ = QFileDialog.getOpenFileName(
            None,
            "Select Database to Import",
            str(Path.home()),  # Start from user's home directory
            "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*.*)"
        )
        if not fname:
            return
        
        src = Path(fname)
        if not src.exists():
            self._notify("Selected file missing")
            return
        
        # Destination will be in AppData with the same filename
        appdata_dir = appdata_root()
        dest = appdata_dir / src.name
        
        # Check if destination already exists
        if dest.exists():
            resp = QMessageBox.question(
                None,
                "Database Already Exists",
                f"A database named '{src.name}' already exists in your AppData folder.\n\nDo you want to overwrite it?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resp != QMessageBox.Yes:
                return
        
        try:
            # Flush current tracker before switching
            self.tracker.flush_all()
        except Exception:
            pass
        
        try:
            # Copy the database to AppData
            shutil.copy2(src, dest)
            
            # Switch to the imported database (don't overwrite current, just switch)
            self.current_project_id = None
            self._apply_database(dest, notify=False)
            
            self._notify(f"Database '{src.name}' imported and switched to successfully")
        except Exception as e:
            self._notify(f"Import failed: {e}")

    def quit(self):
        # Show confirmation dialog
        resp = QMessageBox.question(
            None,
            "Confirm Exit",
            "Are you sure you want to exit VirtualManWeek?\n\n"
            "This will stop time tracking and close the application.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # Default to No for safety
        )
        
        if resp != QMessageBox.Yes:
            return  # User cancelled, don't quit
        
        # User confirmed, proceed with quit
        self.tracker.flush_all()
        self.tray.hide()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.menu.popup(QCursor.pos())

def run_tray():  # entry helper for main.py
    app = TrayApp()
    app.run()
