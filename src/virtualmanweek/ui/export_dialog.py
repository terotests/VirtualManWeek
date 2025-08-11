from __future__ import annotations
from datetime import datetime, timedelta
from typing import Optional, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QRadioButton, 
    QButtonGroup, QDateEdit, QGroupBox, QMessageBox
)
from PySide6.QtCore import QDate, Qt

class ExportDateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Export Date Range")
        self.setMinimumWidth(400)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Select the time period to export:")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Radio button group for quick selections
        quick_group = QGroupBox("Quick Select")
        quick_layout = QVBoxLayout(quick_group)
        
        self.radio_group = QButtonGroup()
        
        self.radio_this_week = QRadioButton("This week (Monday to Sunday)")
        self.radio_this_week.setChecked(True)
        self.radio_group.addButton(self.radio_this_week, 0)
        quick_layout.addWidget(self.radio_this_week)
        
        self.radio_last_week = QRadioButton("Last week (Monday to Sunday)")
        self.radio_group.addButton(self.radio_last_week, 1)
        quick_layout.addWidget(self.radio_last_week)
        
        self.radio_custom = QRadioButton("Custom date range")
        self.radio_group.addButton(self.radio_custom, 2)
        quick_layout.addWidget(self.radio_custom)
        
        layout.addWidget(quick_group)

        # Custom date range section
        custom_group = QGroupBox("Custom Date Range")
        custom_layout = QVBoxLayout(custom_group)
        
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-7))  # Default to a week ago
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())  # Default to today
        date_layout.addWidget(self.end_date)
        
        custom_layout.addLayout(date_layout)
        layout.addWidget(custom_group)

        # Enable/disable custom date range based on radio selection
        self.radio_group.buttonToggled.connect(self._on_radio_changed)
        self._on_radio_changed()  # Initial state

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        export_btn = QPushButton("Export")
        export_btn.clicked.connect(self._on_export)
        export_btn.setDefault(True)
        button_layout.addWidget(export_btn)
        
        layout.addLayout(button_layout)

    def _on_radio_changed(self):
        """Enable/disable custom date range controls"""
        is_custom = self.radio_custom.isChecked()
        self.start_date.setEnabled(is_custom)
        self.end_date.setEnabled(is_custom)

    def _on_export(self):
        """Validate selection and accept dialog"""
        if self.radio_custom.isChecked():
            start_date = self.start_date.date().toPython()
            end_date = self.end_date.date().toPython()
            if start_date > end_date:
                QMessageBox.warning(self, "Invalid Date Range", 
                                  "Start date must be before or equal to end date.")
                return
        self.accept()

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """Get the selected date range as datetime objects (start of start_date, end of end_date)"""
        today = datetime.now().date()
        
        if self.radio_this_week.isChecked():
            # Get Monday of this week
            days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
            monday = today - timedelta(days=days_since_monday)
            sunday = monday + timedelta(days=6)
            start_dt = datetime.combine(monday, datetime.min.time())
            end_dt = datetime.combine(sunday, datetime.max.time())
            
        elif self.radio_last_week.isChecked():
            # Get Monday of last week
            days_since_monday = today.weekday()  # 0=Monday, 6=Sunday
            this_monday = today - timedelta(days=days_since_monday)
            last_monday = this_monday - timedelta(days=7)
            last_sunday = last_monday + timedelta(days=6)
            start_dt = datetime.combine(last_monday, datetime.min.time())
            end_dt = datetime.combine(last_sunday, datetime.max.time())
            
        else:  # Custom range
            start_date = self.start_date.date().toPython()
            end_date = self.end_date.date().toPython()
            start_dt = datetime.combine(start_date, datetime.min.time())
            end_dt = datetime.combine(end_date, datetime.max.time())
        
        return start_dt, end_dt

    def get_description(self) -> str:
        """Get a human-readable description of the selected range"""
        if self.radio_this_week.isChecked():
            return "this week"
        elif self.radio_last_week.isChecked():
            return "last week"
        else:
            start_date = self.start_date.date().toPython()
            end_date = self.end_date.date().toPython()
            if start_date == end_date:
                return f"{start_date.strftime('%Y-%m-%d')}"
            else:
                return f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
