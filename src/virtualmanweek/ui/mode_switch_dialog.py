from __future__ import annotations
import time
from datetime import datetime, date
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, 
    QTextEdit, QSpinBox, QMessageBox
)
from PySide6.QtCore import Qt
from ..db import models
from ..reporting.charts import _fmt_time_short  # Import time formatting function

class ModeSwitchDialog(QDialog):
    def __init__(self, mode_label: str, parent=None):
        super().__init__(parent)
        self.mode_label = mode_label
        self.description = None
        self.manual_seconds = 0
        self.setWindowTitle(f"Switch to: {mode_label}")
        self.setMinimumWidth(400)
        self._build_ui()
        self._prefill_idle_time()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Mode label (read-only)
        layout.addWidget(QLabel(f"Switching to mode: <b>{self.mode_label}</b>"))
        layout.addWidget(QLabel(""))

        # Description input
        layout.addWidget(QLabel("Description (optional):"))
        self.description_edit = QTextEdit(self)
        self.description_edit.setMaximumHeight(80)
        self.description_edit.setPlaceholderText("Enter details about this work session...")
        layout.addWidget(self.description_edit)

        # Manual time section
        layout.addWidget(QLabel("Manual time to add:"))
        
        time_row = QHBoxLayout()
        time_row.addWidget(QLabel("Hours:"))
        self.hours_spin = QSpinBox(self)
        self.hours_spin.setRange(0, 23)
        self.hours_spin.setValue(0)
        self.hours_spin.setMinimumWidth(60)
        self.hours_spin.setSuffix(" h")
        time_row.addWidget(self.hours_spin)
        
        time_row.addWidget(QLabel("Minutes:"))
        self.minutes_spin = QSpinBox(self)
        self.minutes_spin.setRange(0, 59)
        self.minutes_spin.setValue(0)
        self.minutes_spin.setMinimumWidth(60)
        self.minutes_spin.setSuffix(" m")
        time_row.addWidget(self.minutes_spin)
        
        # Fill idle time button
        self.fill_idle_btn = QPushButton("Fill Idle Time", self)
        self.fill_idle_btn.clicked.connect(self._fill_idle_time)
        time_row.addWidget(self.fill_idle_btn)
        time_row.addStretch()
        
        layout.addLayout(time_row)

        # Info label for idle time calculation
        self.idle_info_label = QLabel("")
        self.idle_info_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.idle_info_label)

        # Buttons
        btn_row = QHBoxLayout()
        self.ok_btn = QPushButton("Switch Mode", self)
        self.ok_btn.clicked.connect(self._on_ok)
        self.cancel_btn = QPushButton("Cancel", self)
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_row.addWidget(self.ok_btn)
        btn_row.addWidget(self.cancel_btn)
        layout.addLayout(btn_row)

    def _prefill_idle_time(self):
        """Check if we can calculate idle time and show info"""
        try:
            today = date.today().isoformat()
            last_end_ts = models.get_last_entry_end_time(today)
            if last_end_ts:
                current_ts = int(time.time())
                idle_seconds = current_ts - last_end_ts
                if idle_seconds > 0:
                    last_end_time = datetime.fromtimestamp(last_end_ts).strftime('%H:%M:%S')
                    current_time = datetime.fromtimestamp(current_ts).strftime('%H:%M:%S')
                    self.idle_info_label.setText(
                        f"Last work entry ended at {last_end_time}, current time {current_time} "
                        f"(idle time: {_fmt_time_short(idle_seconds)} = {idle_seconds}s total)"
                    )
                    self.fill_idle_btn.setEnabled(True)
                    return
                else:
                    self.idle_info_label.setText(
                        f"Last work entry ended at {datetime.fromtimestamp(last_end_ts).strftime('%H:%M:%S')}, "
                        f"but calculated idle time is {idle_seconds}s (negative or zero)"
                    )
                    self.fill_idle_btn.setEnabled(False)
                    return
            else:
                self.idle_info_label.setText("No previous work entries found for today (Idle entries are ignored)")
                self.fill_idle_btn.setEnabled(False)
        except Exception as e:
            self.idle_info_label.setText(f"Error calculating idle time: {e}")
            self.fill_idle_btn.setEnabled(False)

    def _fill_idle_time(self):
        """Fill the time inputs with calculated idle time"""
        try:
            today = date.today().isoformat()
            last_end_ts = models.get_last_entry_end_time(today)
            if last_end_ts:
                current_ts = int(time.time())
                idle_seconds = current_ts - last_end_ts
                if idle_seconds > 0:
                    hours = idle_seconds // 3600
                    minutes = (idle_seconds % 3600) // 60
                    self.hours_spin.setValue(min(hours, 23))  # Cap at 23 hours
                    self.minutes_spin.setValue(minutes)
                    # Update the info label with the filled values
                    self.idle_info_label.setText(
                        f"Filled: {_fmt_time_short(idle_seconds)} (total {idle_seconds}s since last entry)"
                    )
                else:
                    QMessageBox.warning(self, "Error", f"Calculated idle time is {idle_seconds} seconds (not positive)")
            else:
                QMessageBox.warning(self, "Error", "No previous entries found for today")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to calculate idle time: {e}")

    def _on_ok(self):
        # Get description
        desc_text = self.description_edit.toPlainText().strip()
        self.description = desc_text if desc_text else None
        
        # Calculate manual seconds
        hours = self.hours_spin.value()
        minutes = self.minutes_spin.value()
        self.manual_seconds = (hours * 3600) + (minutes * 60)
        
        self.accept()

    def get_result(self):
        """Returns (description, manual_seconds)"""
        return self.description, self.manual_seconds
