from __future__ import annotations
from typing import List, Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt
from ..db import models

class ProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Projects")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Manage Projects")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Main layout with list and buttons
        main_layout = QHBoxLayout()
        
        # Left side - project list
        list_container = QVBoxLayout()
        
        # Checkbox to toggle showing archived projects
        list_header = QHBoxLayout()
        list_header.addWidget(QLabel("Projects:"))
        list_header.addStretch()
        self.show_archived_cb = QCheckBox("Show archived")
        self.show_archived_cb.stateChanged.connect(self._load)
        list_header.addWidget(self.show_archived_cb)
        list_container.addLayout(list_header)
        
        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        list_container.addWidget(self.list_widget)
        
        main_layout.addLayout(list_container)
        
        # Right side - buttons and form
        button_layout = QVBoxLayout()
        
        # Add new project section
        button_layout.addWidget(QLabel("Add New Project:"))
        form_layout = QVBoxLayout()
        self.code_edit = QLineEdit(self)
        self.code_edit.setPlaceholderText("Project Code")
        self.code_edit.returnPressed.connect(self._add)
        form_layout.addWidget(self.code_edit)
        
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Project Name")
        self.name_edit.returnPressed.connect(self._add)
        form_layout.addWidget(self.name_edit)
        
        button_layout.addLayout(form_layout)

        self.add_btn = QPushButton("Add / Update", self)
        self.add_btn.clicked.connect(self._add)
        button_layout.addWidget(self.add_btn)
        
        button_layout.addWidget(QLabel(""))  # Spacer
        
        # Edit/Archive buttons
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self._edit_project)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)
        
        self.archive_btn = QPushButton("Archive Selected")
        self.archive_btn.clicked.connect(self._toggle_archive)
        self.archive_btn.setEnabled(False)
        button_layout.addWidget(self.archive_btn)
        
        button_layout.addWidget(QLabel(""))  # Spacer
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load)
        button_layout.addWidget(self.refresh_btn)
        
        button_layout.addStretch()  # Push everything to top
        
        main_layout.addLayout(button_layout)
        layout.addLayout(main_layout)

        # Bottom - close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        self.close_btn = QPushButton("Close", self)
        self.close_btn.clicked.connect(self.accept)
        close_layout.addWidget(self.close_btn)
        layout.addLayout(close_layout)

    def _on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        current_item = self.list_widget.currentItem()
        has_selection = bool(current_item)
        self.edit_btn.setEnabled(has_selection)
        self.archive_btn.setEnabled(has_selection)
        
        # Update archive button text based on project status
        if has_selection:
            project_data = current_item.data(Qt.UserRole)
            if project_data and project_data.get('archived', 0):
                self.archive_btn.setText("Unarchive Selected")
            else:
                self.archive_btn.setText("Archive Selected")

    def _load(self):
        self.list_widget.clear()
        try:
            if self.show_archived_cb.isChecked():
                projects = models.list_all_projects()
            else:
                projects = models.list_active_projects()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load projects: {e}")
            return
        
        for p in projects:
            if self.show_archived_cb.isChecked() and p.get('archived', 0):
                display_text = f"{p['code']} - {p['name']} [ARCHIVED]"
            else:
                display_text = f"{p['code']} - {p['name']}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, p)
            self.list_widget.addItem(item)

    def _add(self):
        code = self.code_edit.text().strip()
        name = self.name_edit.text().strip()
        if not code or not name:
            QMessageBox.information(self, "Validation", "Code and Name required")
            return
        try:
            pid = models.upsert_project(code, name)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to save: {e}")
            return
        self.code_edit.clear()
        self.name_edit.clear()
        self._load()
        QMessageBox.information(self, "Saved", f"Project saved (id={pid})")

    def _edit_project(self):
        """Edit the selected project"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        
        project_data = current_item.data(Qt.UserRole)
        # Pre-fill the form with selected project data
        self.code_edit.setText(project_data['code'])
        self.name_edit.setText(project_data['name'])

    def _toggle_archive(self):
        """Archive or unarchive the selected project"""
        current_item = self.list_widget.currentItem()
        if not current_item:
            return
        
        project_data = current_item.data(Qt.UserRole)
        project_name = f"{project_data['code']} - {project_data['name']}"
        is_archived = project_data.get('archived', 0)
        
        if is_archived:
            action = "unarchive"
            action_past = "unarchived"
            message = f"Are you sure you want to unarchive the project '{project_name}'?\n\n" \
                     "This will make it available in the active projects list again."
        else:
            action = "archive"
            action_past = "archived"
            message = f"Are you sure you want to archive the project '{project_name}'?\n\n" \
                     "This will remove it from the active projects list but won't affect existing time entries. " \
                     "You can still see this project in reports and exports."
        
        # Confirmation dialog
        resp = QMessageBox.question(
            self,
            f"Confirm Project {action.title()}",
            message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if resp != QMessageBox.Yes:
            return
        
        try:
            models.set_project_archived(project_data['id'], not is_archived)
            self._load()  # Refresh the list
            QMessageBox.information(self, "Success", f"Project '{project_name}' {action_past} successfully.")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to {action} project: {e}")
