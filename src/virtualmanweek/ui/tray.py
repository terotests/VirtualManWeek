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
from ..reporting import charts  # HTML-only chart export
from ..reporting.charts import _fmt_time_short  # Import time formatting function
import shutil  # for DB export/import

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
        self._create_tray()
        self._setup_poll_timer()
        # Start with default project none and Idle mode
        self.tracker.start(project_id=None, mode_label="Idle")
        self._apply_icon(idle=True)

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

    def _gen_clock_icon(self, bg: QColor, hand: QColor, text_color: QColor, outline: QColor = QColor("#222")) -> QIcon:
        """Generate a classic analog clock style icon with tiny VM monogram."""
        size = 32
        pm = QPixmap(size, size)
        pm.fill(QColor(0, 0, 0, 0))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        # Outer circle
        p.setBrush(bg)
        p.setPen(QPen(outline, 2))
        p.drawEllipse(1, 1, size - 2, size - 2)
        center = size // 2
        # Ticks (12 / 3 / 6 / 9)
        p.setPen(QPen(hand, 2))
        for dx, dy in [(0,-12),(12,0),(0,12),(-12,0)]:
            p.drawPoint(center + dx//2, center + dy//2)
        # Hands (classic 10:10)
        p.setPen(QPen(hand, 3, ))
        # Minute hand (up)
        p.drawLine(center, center, center, center - 10)
        # Hour hand (approx 10)
        p.drawLine(center, center, center - 6, center - 2)
        # VM monogram near bottom
        p.setPen(QPen(text_color))
        f = QFont("Segoe UI", 8, QFont.Bold)
        p.setFont(f)
        rect = QRect(0, center + 2, size, size - (center + 2))
        p.drawText(rect, 0x84, "VM")  # AlignHCenter|AlignTop (0x84)
        p.end()
        return QIcon(pm)

    def _create_tray(self):
        # Replaced palette: green active, yellow idle, red stopped
        active_bg = QColor("#2E8B57")   # green
        active_hand = QColor("#FFFFFF")
        active_text = QColor("#FFFFFF")
        idle_bg = QColor("#FFC107")     # yellow
        idle_hand = QColor("#333333")
        idle_text = QColor("#333333")
        stopped_bg = QColor("#C0392B")  # red
        stopped_hand = QColor("#FFFFFF")
        stopped_text = QColor("#FFFFFF")
        self._active_icon = self._gen_clock_icon(active_bg, active_hand, active_text)
        self._idle_icon = self._gen_clock_icon(idle_bg, idle_hand, idle_text)
        self._stopped_icon = self._gen_clock_icon(stopped_bg, stopped_hand, stopped_text)
        self.tray = QSystemTrayIcon(self._idle_icon, self.app)
        self.tray.activated.connect(self._on_tray_activated)  # left-click handler
        self.menu = QMenu()

        # Database info at the top
        self.action_database = QAction("", self.menu)
        self.action_database.setEnabled(False)
        self.menu.addAction(self.action_database)
        self.menu.addSeparator()

        self.action_current = QAction("Current: Idle", self.menu)
        self.action_current.setEnabled(False)
        self.menu.addAction(self.action_current)
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
        self.menu.addSeparator()

        # Export menu
        export_menu = self.menu.addMenu("Export")
        csv_act = QAction("CSV...", export_menu)
        csv_act.triggered.connect(self.export_week_csv)
        export_menu.addAction(csv_act)
        html_act = QAction("HTML...", export_menu)
        html_act.triggered.connect(self.show_mode_distribution)
        export_menu.addAction(html_act)

        # Admin menu
        admin_menu = self.menu.addMenu("Admin")
        # New: database management first
        create_db_act = QAction("Create Database...", admin_menu)
        create_db_act.triggered.connect(self.create_database)
        admin_menu.addAction(create_db_act)
        select_db_act = QAction("Select Database...", admin_menu)
        select_db_act.triggered.connect(self.select_database)
        admin_menu.addAction(select_db_act)
        admin_menu.addSeparator()

        reset_act = QAction("Clear Logged Entries", admin_menu)
        reset_act.triggered.connect(self.reset_database)
        admin_menu.addAction(reset_act)
        export_db_act = QAction("Export Database...", admin_menu)
        export_db_act.triggered.connect(self.export_database)
        admin_menu.addAction(export_db_act)
        import_db_act = QAction("Import Database...", admin_menu)
        import_db_act.triggered.connect(self.import_database)
        admin_menu.addAction(import_db_act)

        quit_act = QAction("Exit", self.menu)
        quit_act.triggered.connect(self.quit)
        self.menu.addAction(quit_act)

        # Add Stop Tracking action (toggle style)
        self.stop_act = QAction("Stop Tracking", self.menu)
        self.stop_act.triggered.connect(self.stop_tracking)
        self.menu.addAction(self.stop_act)

        self.tray.setContextMenu(self.menu)
        self.tray.setToolTip("VirtualManWeek")
        self.tray.show()

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
            
            # Enhanced tooltip with database and project info
            tooltip_text = f"{sess.mode_label}{idle_flag} - {elapsed_str}\nDB: {db_name}\nProject: {proj}"
            self.tray.setToolTip(tooltip_text)
            
            self._apply_icon(idle=(sess.idle_accum > 0 or sess.mode_label.lower()=="idle"))
            if self.stop_act:
                self.stop_act.setEnabled(True)
                self.stop_act.setText("Stop Tracking")
        else:
            proj = self._project_display(self.current_project_id)
            self.action_current.setText("Current: (stopped)")
            tooltip_text = f"Tracking stopped\nDB: {db_name}\nProject: {proj}"
            self.tray.setToolTip(tooltip_text)
            self._apply_icon(stopped=True)
            if self.stop_act:
                self.stop_act.setEnabled(False)
                self.stop_act.setText("Stopped")

    def _apply_icon(self, idle: bool = False, stopped: bool = False):
        if stopped:
            self.tray.setIcon(self._stopped_icon)
        elif idle:
            self.tray.setIcon(self._idle_icon)
        else:
            self.tray.setIcon(self._active_icon)

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

    # Charts: show mode distribution (HTML-only export)
    def show_mode_distribution(self):
        default_filename = self._generate_export_filename("html")
        path = self._select_save_path(
            "Save Chart HTML", default_filename, "HTML Files (*.html);;All Files (*.*)"
        )
        if not path:
            return
        try:
            charts.export_mode_distribution_html_to(path)
            webbrowser.open(path.as_uri())
            self._notify(f"Chart exported to {path}")
        except Exception as e:
            self._notify(f"Chart export failed: {e}")

    # Export: CSV of recent entries
    def export_week_csv(self):
        try:
            with models.connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT date, project_id, mode_label, active_seconds, idle_seconds, manual_seconds, description FROM time_entries ORDER BY start_ts DESC LIMIT 100"
                )
                rows = cur.fetchall()
            default_filename = self._generate_export_filename("csv")
            path = self._select_save_path("Save Time Entries CSV", default_filename, "CSV Files (*.csv);;All Files (*.*)")
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
            self._notify(f"Exported {len(rows)} rows to {path}")
        except Exception as e:
            self._notify(f"Export failed: {e}")

    # Restored handlers and admin actions
    def stop_tracking(self):
        try:
            self.tracker.stop()
        except Exception:
            pass
        self._update_current_label()

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
        self._update_current_label()

    def select_project(self, project_id: int):
        self.current_project_id = project_id
        if self.tracker.active:
            mode = self.tracker.active.mode_label
            self.tracker.switch(project_id=project_id, mode_label=mode, description=None)
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
        try:
            cur_path = models.db_path()
        except Exception as e:
            self._notify(f"DB path error: {e}")
            return
        fname, _ = QFileDialog.getOpenFileName(
            None,
            "Select Database to Import",
            str(cur_path.parent),
            "SQLite DB (*.sqlite3 *.db *.sqlite);;All Files (*.*)"
        )
        if not fname:
            return
        src = Path(fname)
        if not src.exists():
            self._notify("Selected file missing")
            return
        resp = QMessageBox.question(
            None,
            "Confirm Import",
            "Importing will overwrite the existing database and all current logged data will be lost.\n\nProceed?",
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
            shutil.copy2(src, cur_path)
            models.initialize()
            self.tracker.active = None
            self._rebuild_switch_menu()
            if hasattr(self, 'projects_menu'):
                self._rebuild_projects_menu()
            self._update_current_label()
            self._notify("Database imported successfully")
        except Exception as e:
            self._notify(f"Import failed: {e}")

    def quit(self):
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
