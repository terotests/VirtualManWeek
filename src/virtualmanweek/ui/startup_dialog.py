from __future__ import annotations
from typing import Optional, Tuple
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, 
    QMessageBox, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ..db import models


class StartupDialog(QDialog):
    """Dialog for selecting project and mode on startup or database switch"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Project and Mode")
        self.setModal(True)
        self.setMinimumSize(400, 300)
        self.resize(500, 350)
        
        self.selected_project_id: Optional[int] = None
        self.selected_mode: str = "Idle"
        
        self._build_ui()
        self._populate_dropdowns()
        
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title_label = QLabel("Welcome to VirtualManWeek")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Please select a project and mode to begin tracking your time.")
        subtitle_label.setAlignment(Qt.AlignCenter)
        subtitle_label.setStyleSheet("color: #666; margin-bottom: 20px;")
        subtitle_label.setWordWrap(True)
        layout.addWidget(subtitle_label)
        
        # Form layout for project and mode selection
        form_layout = QFormLayout()
        
        # Project selection
        self.project_combo = QComboBox()
        self.project_combo.setMinimumHeight(30)
        form_layout.addRow("Project:", self.project_combo)
        
        # Mode selection
        self.mode_combo = QComboBox()
        self.mode_combo.setEditable(True)  # Allow custom mode entry
        self.mode_combo.setMinimumHeight(30)
        form_layout.addRow("Mode:", self.mode_combo)
        
        layout.addLayout(form_layout)
        
        # Info text
        info_label = QLabel(
            "The project and mode selected here will be used to start your first time tracking session. "
            "You can change these later using the tray menu."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 10px;")
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        self.start_btn = QPushButton("Start Tracking")
        self.start_btn.clicked.connect(self._on_start_clicked)
        self.start_btn.setDefault(True)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(self.start_btn)
        
        layout.addLayout(button_layout)
        
    def _populate_dropdowns(self):
        """Populate the project and mode dropdowns with data from the database"""
        # Populate projects
        self.project_combo.clear()
        self.project_combo.addItem("(No Project)", None)
        
        try:
            projects = models.list_active_projects()
            for project in projects:
                code = project.get('code', '')
                name = project.get('name', '')
                if code and name:
                    display_text = f"{code} - {name}"
                elif code:
                    display_text = code
                elif name:
                    display_text = name
                else:
                    display_text = f"Project {project['id']}"
                
                self.project_combo.addItem(display_text, project['id'])
        except Exception:
            pass  # Handle gracefully if no projects exist yet
        
        # Populate modes
        self.mode_combo.clear()
        
        try:
            modes = models.mode_suggestions()
            for mode in sorted(modes, key=lambda s: s.lower()):
                self.mode_combo.addItem(mode)
        except Exception:
            # Add default modes if database is empty
            default_modes = ["Work", "Meeting", "Break", "Lunch", "Idle"]
            for mode in default_modes:
                self.mode_combo.addItem(mode)
        
        # Try to pre-select based on last entry
        self._preselect_from_last_entry()
        
    def _preselect_from_last_entry(self):
        """Pre-select project and mode based on the last time entry in the database"""
        try:
            # Get the most recent time entry
            with models.connect() as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT project_id, mode_label
                    FROM time_entries 
                    ORDER BY end_ts DESC 
                    LIMIT 1
                """)
                result = cur.fetchone()
                
                if result:
                    last_project_id, last_mode = result
                    
                    # Pre-select project
                    if last_project_id:
                        for i in range(self.project_combo.count()):
                            if self.project_combo.itemData(i) == last_project_id:
                                self.project_combo.setCurrentIndex(i)
                                break
                    
                    # Pre-select mode
                    if last_mode:
                        # Find and select the mode
                        mode_index = self.mode_combo.findText(last_mode)
                        if mode_index >= 0:
                            self.mode_combo.setCurrentIndex(mode_index)
                        else:
                            # If mode not found, set it as text (since combo is editable)
                            self.mode_combo.setEditText(last_mode)
                            
        except Exception:
            # If no entries exist or any error, just use defaults
            # Set default mode to "Idle"
            idle_index = self.mode_combo.findText("Idle")
            if idle_index >= 0:
                self.mode_combo.setCurrentIndex(idle_index)
    
    def _on_start_clicked(self):
        """Handle start button click"""
        # Get selected values
        self.selected_project_id = self.project_combo.currentData()
        self.selected_mode = self.mode_combo.currentText().strip()
        
        if not self.selected_mode:
            QMessageBox.warning(self, "Validation Error", "Please enter a mode to start tracking.")
            return
        
        self.accept()
    
    def get_selection(self) -> Tuple[Optional[int], str]:
        """Return the selected project ID and mode"""
        return self.selected_project_id, self.selected_mode
