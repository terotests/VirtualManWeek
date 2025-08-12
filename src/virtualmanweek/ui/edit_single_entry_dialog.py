from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QComboBox, 
    QPushButton, QLabel, QTimeEdit, QDateEdit, QMessageBox, QFormLayout, QTextEdit
)
from PySide6.QtCore import Qt, QTime, QDate
from PySide6.QtGui import QFont
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from ..db import models


class EditSingleEntryDialog(QDialog):
    def __init__(self, entry: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.entry = entry.copy()  # Make a copy to avoid modifying original
        self.original_entry = entry.copy()
        self.setWindowTitle("Edit Time Entry")
        self.setModal(True)
        self.resize(500, 400)
        
        self.projects = []
        self.modes = []
        self.setup_ui()
        self.load_data()
        self.populate_fields()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Edit Time Entry")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # Form layout
        form_layout = QFormLayout()
        
        # Date selection
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        form_layout.addRow("Date:", self.date_edit)
        
        # Mode selection
        self.mode_combo = QComboBox()
        self.mode_combo.setEditable(True)
        form_layout.addRow("Mode:", self.mode_combo)
        
        # Project selection
        self.project_combo = QComboBox()
        form_layout.addRow("Project:", self.project_combo)
        
        # Start time
        self.start_time_edit = QTimeEdit()
        form_layout.addRow("Start Time:", self.start_time_edit)
        
        # End time
        self.end_time_edit = QTimeEdit()
        self.end_time_edit.timeChanged.connect(self.validate_times)
        form_layout.addRow("End Time:", self.end_time_edit)
        
        # Duration (read-only)
        self.duration_label = QLabel()
        form_layout.addRow("Duration:", self.duration_label)
        
        # Description
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)  # Limit height
        self.description_edit.setPlaceholderText("Enter description (optional)")
        form_layout.addRow("Description:", self.description_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_changes)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_data(self):
        """Load projects and modes from database"""
        try:
            # Load projects
            self.projects = models.list_all_projects()
            self.project_combo.addItem("No Project", None)
            for project in self.projects:
                self.project_combo.addItem(f"{project['code']} - {project['name']}", project['id'])
            
            # Load modes
            mode_data = models.list_modes()
            for mode in mode_data:
                if mode['label']:  # Only add non-empty labels
                    self.mode_combo.addItem(mode['label'])
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load data: {e}")
    
    def populate_fields(self):
        """Populate form fields with entry data"""
        # Date
        entry_date = datetime.fromtimestamp(self.entry['start_ts']).date()
        self.date_edit.setDate(QDate(entry_date.year, entry_date.month, entry_date.day))
        
        # Mode
        mode_index = self.mode_combo.findText(self.entry['mode_label'])
        if mode_index >= 0:
            self.mode_combo.setCurrentIndex(mode_index)
        else:
            self.mode_combo.setEditText(self.entry['mode_label'])
        
        # Project
        project_id = self.entry.get('project_id')
        if project_id:
            for i in range(self.project_combo.count()):
                if self.project_combo.itemData(i) == project_id:
                    self.project_combo.setCurrentIndex(i)
                    break
        else:
            self.project_combo.setCurrentIndex(0)  # "No Project"
        
        # Times
        start_dt = datetime.fromtimestamp(self.entry['start_ts'])
        end_dt = datetime.fromtimestamp(self.entry['end_ts'])
        
        self.start_time_edit.setTime(QTime(start_dt.hour, start_dt.minute, start_dt.second))
        self.end_time_edit.setTime(QTime(end_dt.hour, end_dt.minute, end_dt.second))
        
        # Description
        self.description_edit.setPlainText(self.entry.get('description', ''))
        
        self.update_duration()
    
    def validate_times(self):
        """Validate that end time is after start time"""
        self.update_duration()
        
        start_time = self.start_time_edit.time()
        end_time = self.end_time_edit.time()
        
        # Convert to seconds for comparison
        start_seconds = start_time.hour() * 3600 + start_time.minute() * 60 + start_time.second()
        end_seconds = end_time.hour() * 3600 + end_time.minute() * 60 + end_time.second()
        
        # If end time is before or equal to start time on the same day, it's invalid
        if end_seconds <= start_seconds:
            # Unless it's exactly the same time, we allow day boundary crossing
            if end_seconds == start_seconds:
                self.save_btn.setEnabled(False)
            else:
                self.save_btn.setEnabled(True)  # Day boundary crossing is allowed
        else:
            self.save_btn.setEnabled(True)
    
    def update_duration(self):
        """Update the duration display"""
        start_time = self.start_time_edit.time()
        end_time = self.end_time_edit.time()
        
        start_seconds = start_time.hour() * 3600 + start_time.minute() * 60 + start_time.second()
        end_seconds = end_time.hour() * 3600 + end_time.minute() * 60 + end_time.second()
        
        # Handle day boundary crossing
        if end_seconds <= start_seconds:
            end_seconds += 24 * 3600
        
        duration = end_seconds - start_seconds
        hours, remainder = divmod(duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        self.duration_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")
    
    def save_changes(self):
        """Save the changes"""
        try:
            # Get form values
            selected_date = self.date_edit.date().toPython()
            mode_label = self.mode_combo.currentText().strip()
            project_id = self.project_combo.currentData()
            
            if not mode_label:
                QMessageBox.warning(self, "Validation Error", "Mode cannot be empty.")
                return
            
            # Calculate new timestamps
            start_time = self.start_time_edit.time()
            end_time = self.end_time_edit.time()
            
            start_dt = datetime.combine(selected_date, start_time.toPython())
            end_dt = datetime.combine(selected_date, end_time.toPython())
            
            # Handle day boundary crossing
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)
            
            new_start_ts = int(start_dt.timestamp())
            new_end_ts = int(end_dt.timestamp())
            
            # Update entry data
            self.entry['start_ts'] = new_start_ts
            self.entry['end_ts'] = new_end_ts
            self.entry['mode_label'] = mode_label
            self.entry['project_id'] = project_id
            self.entry['description'] = self.description_edit.toPlainText().strip()
            
            # Calculate new duration and update time components proportionally
            new_duration = new_end_ts - new_start_ts
            old_duration = self.entry['elapsed_seconds']
            
            if old_duration > 0:
                ratio = new_duration / old_duration
                self.entry['active_seconds'] = int(self.entry['active_seconds'] * ratio)
                self.entry['idle_seconds'] = int(self.entry['idle_seconds'] * ratio)
                self.entry['manual_seconds'] = int(self.entry['manual_seconds'] * ratio)
            
            self.entry['elapsed_seconds'] = self.entry['active_seconds'] + self.entry['idle_seconds'] + self.entry['manual_seconds']
            
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")
    
    def get_modified_entry(self) -> Dict[str, Any]:
        """Return the modified entry"""
        return self.entry
