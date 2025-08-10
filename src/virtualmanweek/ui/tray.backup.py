from __future__ import annotations
import sys
import time
from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox, QStyle, QInputDialog, QFileDialog
from PySide6.QtGui import QIcon, QAction, QCursor, QPixmap, QPainter, QColor, QPen, QFont
from PySide6.QtCore import QTimer, QRect, Qt
import time  # ensure time available for formatting
import webbrowser  # new for HTML fallback
from datetime import datetime

from ..config import Settings, appdata_root
from ..tracking.engine import Tracker
from ..db import models
from ..utils.constants import QUICK_MODES  # added import
from .project_dialog import ProjectDialog  # new import
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
        self.tracker = Tracker(self.settings)
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)  # keep running with only tray
        self._active_icon = None
        self._idle_icon = None
        self._stopped_icon = None  # new stopped icon
        self._create_tray()
        self._setup_poll_timer()
        # Start with default project none and Idle mode
        self.tracker.start(project_id=None, mode_label="Idle")
        self._apply_icon(idle=True)

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

        self.action_current = QAction("Current: Idle", self.menu)
        self.action_current.setEnabled(False)
        self.menu.addAction(self.action_current)
        self.menu.addSeparator()

        # Dynamic switch menu
        self.switch_menu = self.menu.addMenu("Switch Mode")
        self._rebuild_switch_menu()

        # Modes management menu
        self.modes_manage_menu = self.menu.addMenu("Modes")
        self._rebuild_modes_manage_menu()

        idle_act = QAction("Set Idle", self.menu)
        idle_act.triggered.connect(lambda: self.switch_mode("Idle"))
        self.menu.addAction(idle_act)

        # Insert project management before export
        proj_act = QAction("Projects", self.menu)
        proj_act.triggered.connect(self.open_projects)
        self.menu.addAction(proj_act)
        self.menu.addSeparator()

        export_act = QAction("Export Week (CSV)", self.menu)
        export_act.triggered.connect(self.export_week_csv)
        self.menu.addAction(export_act)

        # Statistics menu
        stats_menu = self.menu.addMenu("Statistics")
        modes_bar = QAction("Mode Distribution", stats_menu)
        modes_bar.triggered.connect(self.show_mode_distribution)
        stats_menu.addAction(modes_bar)

        # Admin menu
        admin_menu = self.menu.addMenu("Admin")
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
        """Populate the switch mode submenu with quick modes + stored custom modes + Custom... entry."""
        self.switch_menu.clear()
        # Quick modes (fixed order)
        for mode in QUICK_MODES:
            act = QAction(mode, self.switch_menu)
            act.triggered.connect(lambda checked=False, m=mode: self.switch_mode(m))
            self.switch_menu.addAction(act)
        # Load custom modes from DB (exclude quick modes, case-insensitive)
        try:
            quick_set = {q.lower() for q in QUICK_MODES}
            custom_modes = [m for m in models.mode_suggestions() if m.lower() not in quick_set]
        except Exception:
            custom_modes = []
        if custom_modes:
            self.switch_menu.addSeparator()
            for mode in sorted(custom_modes, key=lambda s: s.lower()):
                act = QAction(mode, self.switch_menu)
                act.triggered.connect(lambda checked=False, m=mode: self.switch_mode(m))
                self.switch_menu.addAction(act)
        # Final separator + custom creator
        self.switch_menu.addSeparator()
        custom_act = QAction("Custom...", self.switch_menu)
        custom_act.triggered.connect(self.custom_switch_dialog)
        self.switch_menu.addAction(custom_act)

    def _rebuild_modes_manage_menu(self):
        self.modes_manage_menu.clear()
        try:
            quick_set = {q.lower() for q in QUICK_MODES}
            all_modes = models.list_modes()
        except Exception:
            all_modes = []
        # Only show deletable for non-quick modes
        deletable = [m for m in all_modes if m['label'].lower() not in quick_set]
        if not deletable:
            dummy = QAction("(No custom modes)", self.modes_manage_menu)
            dummy.setEnabled(False)
            self.modes_manage_menu.addAction(dummy)
        else:
            for m in deletable:
                label = f"Delete: {m['label']}"
                act = QAction(label, self.modes_manage_menu)
                act.triggered.connect(lambda checked=False, mid=m['id']: self._delete_mode(mid))
                self.modes_manage_menu.addAction(act)
        self.modes_manage_menu.addSeparator()
        refresh_act = QAction("Refresh", self.modes_manage_menu)
        refresh_act.triggered.connect(self._rebuild_modes_manage_menu)
        self.modes_manage_menu.addAction(refresh_act)

    def _setup_poll_timer(self):
        self.timer = QTimer()
        self.timer.setInterval(1000)  # 1s for live elapsed display
        self.timer.timeout.connect(self._poll_loop)
        self.timer.start()

    def _format_elapsed(self, seconds: int) -> str:
        if seconds < 60:
            return f"{seconds}s"
        m, s = divmod(seconds, 60)
        if m < 60:
            return f"{m}m{s:02d}s"
        h, m = divmod(m, 60)
        return f"{h}h{m:02d}m{s:02d}s"

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
        if self.tracker.active:
            sess = self.tracker.active
            idle_flag = " (idle)" if sess.idle_accum > 0 or sess.mode_label.lower() == "idle" else ""
            proj = "None" if sess.project_id is None else str(sess.project_id)
            elapsed = int(time.time()) - sess.start_ts
            elapsed_str = self._format_elapsed(elapsed)
            self.action_current.setText(f"Current: {sess.mode_label}{idle_flag} / P:{proj} / {elapsed_str}")
            self.tray.setToolTip(f"{sess.mode_label}{idle_flag} - {elapsed_str}")
            self._apply_icon(idle=(sess.idle_accum > 0 or sess.mode_label.lower()=="idle"))
            if self.stop_act:
                self.stop_act.setEnabled(True)
                self.stop_act.setText("Stop Tracking")
        else:
            self.action_current.setText("Current: (stopped)")
            self.tray.setToolTip("Tracking stopped")
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

    def stop_tracking(self):
        """Force stop current tracking session without exiting app."""
        try:
            self.tracker.stop()
        except Exception:
            pass
        self._update_current_label()

    def switch_mode(self, mode_label: str):
        # Ask optional description for each switch (quick dismiss allowed)
        desc, ok = QInputDialog.getMultiLineText(None, "Description", f"Details for '{mode_label}' (optional):", "")
        if not ok:
            desc = None
        self.tracker.switch(project_id=None, mode_label=mode_label, description=desc)
        self._update_current_label()

    def open_projects(self):
        dlg = ProjectDialog()
        dlg.exec()

    def _delete_mode(self, mode_id: int):
        try:
            models.delete_mode(mode_id)
        except Exception as e:
            self._notify(f"Delete failed: {e}")
            return
        self._notify("Mode removed")
        self._rebuild_switch_menu()
        self._rebuild_modes_manage_menu()

    def custom_switch_dialog(self):
        # Revised: ask for new mode label first, then optional description. No project selection.
        mode, okm = QInputDialog.getText(None, "New Mode", "Mode label:")
        if not okm or not mode.strip():
            return
        desc, okd = QInputDialog.getMultiLineText(None, "Description", f"Details for '{mode.strip()}' (optional):", "")
        if not okd:
            desc = None
        self.tracker.switch(project_id=None, mode_label=mode.strip(), description=desc)
        try:
            from ..db import models as _models
            _models.upsert_mode(mode.strip())
        except Exception:
            pass
        # Rebuild menus so new mode appears
        self._rebuild_switch_menu()
        self._rebuild_modes_manage_menu()
        self._update_current_label()

    def show_mode_distribution(self):
        data = models.mode_distribution()
        if not data:
            self._notify("No data yet")
            return
        # Decide unit scaling
        max_val = max(int(r['total_active']) for r in data)
        if max_val >= 3600:  # 1h+
            divisor = 3600.0
            unit = "Hours"
            fmt = lambda v: f"{v:.2f}"  # keep 2 decimals for hours
        elif max_val >= 600:  # 10m+
            divisor = 60.0
            unit = "Minutes"
            fmt = lambda v: f"{v:.1f}"  # 1 decimal for minutes
        else:
            divisor = 1.0
            unit = "Seconds"
            fmt = lambda v: f"{int(v)}"
        # Try QtCharts first
        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QPushButton, QHBoxLayout
            from PySide6.QtCharts import QtCharts
            dlg = QDialog()
            dlg.setWindowTitle(f"Mode Distribution (Active {unit})")
            vlayout = QVBoxLayout(dlg)
            chart = QtCharts.QChart()
            series = QtCharts.QBarSeries()
            categories = []
            barset = QtCharts.QBarSet(f"Active {unit}")
            for row in data:
                categories.append(row['mode'])
                scaled = float(row['total_active']) / divisor
                barset << scaled
            series.append(barset)
            chart.addSeries(series)
            axis_x = QtCharts.QBarCategoryAxis()
            axis_x.append(categories)
            chart.addAxis(axis_x, Qt.AlignBottom)
            series.attachAxis(axis_x)
            axis_y = QtCharts.QValueAxis()
            axis_y.setTitleText(unit)
            chart.addAxis(axis_y, Qt.AlignLeft)
            series.attachAxis(axis_y)
            chart.setTitle(f"Mode Distribution (Active {unit})")
            chart.legend().setVisible(True)
            chart.legend().setAlignment(Qt.AlignBottom)
            view = QtCharts.QChartView(chart)
            view.setRenderHint(QPainter.Antialiasing)
            vlayout.addWidget(view)
            # Export buttons row
            hl = QHBoxLayout()
            export_btn = QPushButton("Export HTML…")
            def do_export():
                path = self._select_save_path("Save Chart HTML", "mode_distribution.html", "HTML Files (*.html);;All Files (*.*)")
                if not path:
                    return
                try:
                    self._write_chart_html(path, data, divisor, unit, max_val)
                    self._notify(f"Chart saved: {path}")
                except Exception as e:
                    self._notify(f"Export failed: {e}")
            export_btn.clicked.connect(do_export)
            hl.addWidget(export_btn)
            vlayout.addLayout(hl)
            dlg.resize(780, 520)
            dlg.exec()
            return
        except Exception:
            # Fallback to pure HTML export
            pass
        # Direct HTML generation fallback
        path = self._select_save_path("Save Chart HTML", "mode_distribution.html", "HTML Files (*.html);;All Files (*.*)")
        if not path:
            return
        try:
            self._write_chart_html(path, data, divisor, unit, max_val)
            webbrowser.open(path.as_uri())
            self._notify(f"Chart opened: {path} (unit: {unit})")
        except Exception as e:
            self._notify(f"Chart export failed: {e}")

    def _write_chart_html(self, html_path: Path, data, divisor: float, unit: str, max_val: int):
        labels = [r['mode'] for r in data]
        raw_values = [int(r['total_active']) for r in data]
        values = [round(v / divisor, 2 if unit == 'Hours' else 1 if unit == 'Minutes' else 0) for v in raw_values]
        # Collect per-mode detailed entries (longest first)
        per_mode_tables = []
        daily_tables = []  # new daily summary tables
        try:
            import html as _html
            with models.connect() as conn:
                cur = conn.cursor()
                # Mode detail (existing logic, now inside same try)
                for mode in labels:
                    cur.execute(
                        "SELECT date, start_ts, end_ts, active_seconds, idle_seconds, description FROM time_entries WHERE mode_label=? ORDER BY active_seconds DESC, start_ts DESC LIMIT 200",
                        (mode,),
                    )
                    rows = cur.fetchall()
                    if not rows:
                        continue
                    def _fmt(sec: int) -> str:
                        if sec >= 3600:
                            return f"{sec/3600:.2f}h"
                        if sec >= 60:
                            return f"{sec/60:.1f}m"
                        return f"{sec}s"
                    def _fmt_dt(ts: int) -> str:
                        try:
                            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                        except Exception:
                            return str(ts)
                    row_html_parts = []
                    for r in rows:
                        desc = r["description"] or ""
                        desc = _html.escape(desc).replace('\n', '<br/>')
                        dt_str = _fmt_dt(r['start_ts'])
                        active_fmt = _fmt(r['active_seconds'])
                        idle_fmt = _fmt(r['idle_seconds']) if r['idle_seconds'] else ''
                        total_fmt = _fmt(r['active_seconds'] + (r['idle_seconds'] or 0))
                        row_html_parts.append(
                            f"<tr><td>{dt_str}</td><td class='num'>{active_fmt}</td><td class='num'>{idle_fmt}</td><td class='num'>{total_fmt}</td><td class='desc'>{desc}</td></tr>"
                        )
                    table_html = (
                        f"<h4>{_html.escape(mode)}</h4>"
                        "<table class='mode'><thead><tr><th>Date/Start Time</th><th>Active</th><th>Idle</th><th>Total</th><th>Description</th></tr></thead><tbody>"
                        + "".join(row_html_parts)
                        + "</tbody></table>"
                    )
                    per_mode_tables.append(table_html)
                # Daily summary (chronological)
                cur.execute(
                    "SELECT date, start_ts, active_seconds, idle_seconds, mode_label, description FROM time_entries ORDER BY date ASC, start_ts ASC LIMIT 2000"
                )
                daily_rows = cur.fetchall()
                if daily_rows:
                    # group by date
                    from collections import defaultdict
                    grouped = defaultdict(list)
                    for r in daily_rows:
                        grouped[r['date']].append(r)
                    def _fmt_short(sec: int) -> str:
                        if sec >= 3600:
                            return f"{sec/3600:.2f}h"
                        if sec >= 60:
                            return f"{sec/60:.1f}m"
                        return f"{sec}s"
                    for d in sorted(grouped.keys()):
                        entries = grouped[d]
                        try:
                            weekday = datetime.strptime(d, '%Y-%m-%d').strftime('%A')
                        except Exception:
                            weekday = d
                        row_parts = []
                        for r in entries:
                            t_str = datetime.fromtimestamp(r['start_ts']).strftime('%H:%M:%S') if r['start_ts'] else ''
                            desc = (r['description'] or '').replace('\n', ' ')
                            desc = _html.escape(desc)
                            active_fmt = _fmt_short(r['active_seconds'])
                            idle_fmt = _fmt_short(r['idle_seconds']) if r['idle_seconds'] else ''
                            total_fmt = _fmt_short(r['active_seconds'] + (r['idle_seconds'] or 0))
                            row_parts.append(
                                f"<tr><td>{t_str}</td><td>{_html.escape(r['mode_label'])}</td><td class='num'>{active_fmt}</td><td class='num'>{idle_fmt}</td><td class='num'>{total_fmt}</td><td class='desc'>{desc}</td></tr>"
                            )
                        daily_tables.append(
                            f"<h4>{weekday} {d}</h4><table class='mode'><thead><tr><th>Start</th><th>Mode</th><th>Active</th><th>Idle</th><th>Total</th><th>Description</th></tr></thead><tbody>{''.join(row_parts)}</tbody></table>"
                        )
        except Exception as e:  # pragma: no cover
            per_mode_tables.append(f"<p><em>Detail section failed: {e}</em></p>")
        detail_section = "\n".join(per_mode_tables) if per_mode_tables else "<p><em>No detailed entries.</em></p>"
        daily_section = "\n".join(daily_tables) if daily_tables else "<p><em>No daily entries.</em></p>"
        html = f"""<!DOCTYPE html><html><head><meta charset='utf-8'/><title>Mode Distribution</title>
<style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f9f9fb;color:#222}}
h2{{margin-top:0}}
#meta{{font-size:12px;color:#555;margin-bottom:12px}}
canvas{{border:1px solid #ddd;background:#fff}}
section.details h3, section.daily h3{{margin-top:40px;border-bottom:2px solid #0A4F9C;padding-bottom:4px}}
table.mode{{border-collapse:collapse;margin:12px 0 28px 0;width:100%;background:#fff;font-size:13px}}
table.mode th,table.mode td{{border:1px solid #ddd;padding:4px 6px;vertical-align:top}}
table.mode th{{background:#0A4F9C;color:#fff;text-align:left}}
.num{{text-align:right;white-space:nowrap}}
.desc{{max-width:640px;}}
h4{{margin:28px 0 6px 0;color:#0A4F9C}}
</style>
<script src='https://cdn.jsdelivr.net/npm/chart.js'></script></head><body>
<h2>Mode Distribution (Active {unit})</h2>
<div id='meta'>Generated at {time.strftime('%Y-%m-%d %H:%M:%S')} &middot; Max raw seconds: {max_val}</div>
<canvas id='c' width='1000' height='500'></canvas>
<script>
const labels = {labels};
const dataVals = {values};
const unit = '{unit}';
new Chart(document.getElementById('c').getContext('2d'), {{
  type: 'bar',
  data: {{ labels: labels, datasets: [{{ label: 'Active ' + unit, data: dataVals, backgroundColor: '#0A4F9C'}}] }},
  options: {{ indexAxis: 'x', responsive: false, plugins: {{ legend: {{ position: 'bottom' }}, tooltip: {{ callbacks: {{ label: (ctx)=> ctx.parsed.y + ' ' + unit }} }} }}, scales: {{ y: {{ beginAtZero: true, title: {{ display:true, text: unit }} }} }} }}
}});
</script>
<section class='daily'>
<h3>Daily Timeline</h3>
{daily_section}
</section>
<section class='details'>
<h3>Detailed Entries (Per Mode)</h3>
{detail_section}
</section>
</body></html>"""
        html_path.write_text(html, encoding='utf-8')

    def export_week_csv(self):
        # PoC: export current ISO week aggregated raw entries including description
        try:
            with models.connect() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT date, project_id, mode_label, active_seconds, idle_seconds, description FROM time_entries ORDER BY start_ts DESC LIMIT 100"
                )
                rows = cur.fetchall()
            path = self._select_save_path("Save Time Entries CSV", "raw_entries.csv", "CSV Files (*.csv);;All Files (*.*)")
            if not path:
                return
            with path.open("w", encoding="utf-8") as f:
                f.write("date,project_id,mode,active_seconds,idle_seconds,description\n")
                for r in rows:
                    desc = r["description"] or ""
                    if '"' in desc:
                        desc = desc.replace('"', '""')
                    if any(c in desc for c in [',', '\n', '"']):
                        desc_out = f'"{desc}"'
                    else:
                        desc_out = desc
                    f.write(
                        f"{r['date']},{r['project_id'] if r['project_id'] is not None else ''},{r['mode_label']},{r['active_seconds']},{r['idle_seconds']},{desc_out}\n"
                    )
            self._notify(f"Exported {len(rows)} rows to {path}")
        except Exception as e:
            self._notify(f"Export failed: {e}")

    def _select_save_path(self, title: str, default_filename: str, filter_spec: str) -> Optional[Path]:
        """Open a save dialog and return selected Path or None if cancelled."""
        # Use last used dir or appdata_root by default
        default_dir = str(appdata_root())
        suggested = str(Path(default_dir) / default_filename)
        fname, _ = QFileDialog.getSaveFileName(None, title, suggested, filter_spec)
        if not fname:
            return None
        return Path(fname)

    def _notify(self, message: str):
        self.tray.showMessage("VirtualManWeek", message, QSystemTrayIcon.Information, 4000)

    def quit(self):
        self.tracker.flush_all()
        self.tray.hide()
        self.app.quit()

    def run(self):
        sys.exit(self.app.exec())

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:  # left click
            # Show context menu at cursor
            self.menu.popup(QCursor.pos())

    def reset_database(self):
        """Clear all logged entries after user confirmation (non-destructive to modes/projects)."""
        from PySide6.QtWidgets import QMessageBox
        try:
            path = models.db_path()
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
        # Use models.clear_logged_entries instead of deleting file
        try:
            stats = models.clear_logged_entries()
        except Exception as e:
            self._notify(f"Clear failed: {e}")
            return
        self.tracker.active = None
        self._update_current_label()
        self._rebuild_switch_menu()
        self._rebuild_modes_manage_menu()
        self._notify(f"Cleared: {stats['time_entries']} entries, {stats['weeks']} weeks. Modes reset: {stats['modes_reset']}")

    def export_database(self):
        """Export (copy) the current SQLite database file to user-selected path."""
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
        """Import (replace) the current SQLite database from a user-selected file."""
        from PySide6.QtWidgets import QMessageBox, QFileDialog
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
        # Stop current tracking
        try:
            self.tracker.flush_all()
        except Exception:
            pass
        try:
            shutil.copy2(src, cur_path)
            models.initialize()  # ensure schema compatibility
            self.tracker.active = None
            self._rebuild_switch_menu()
            self._rebuild_modes_manage_menu()
            self._update_current_label()
            self._notify("Database imported successfully")
        except Exception as e:
            self._notify(f"Import failed: {e}")

def run_tray():  # entry helper
    app = TrayApp()
    app.run()
