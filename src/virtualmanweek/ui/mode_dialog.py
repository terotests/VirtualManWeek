from __future__ import annotations
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit, QLabel, QMessageBox
)
from PySide6.QtCore import Qt
from ..db import models


class ModeDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Modes")
        self.setMinimumSize(500, 400)
        self.resize(600, 500)
        
        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Manage Modes")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # List of modes
        list_layout = QHBoxLayout()
        
        # Mode list
        list_container = QVBoxLayout()
        list_container.addWidget(QLabel("Existing Modes:"))
        self.mode_list = QListWidget()
        self.mode_list.setSelectionMode(QListWidget.SingleSelection)
        self.mode_list.itemSelectionChanged.connect(self._on_selection_changed)
        list_container.addWidget(self.mode_list)
        
        list_layout.addLayout(list_container)
        
        # Buttons on the right
        button_layout = QVBoxLayout()
        
        # Add new mode section
        button_layout.addWidget(QLabel("Add New Mode:"))
        self.new_mode_edit = QLineEdit()
        self.new_mode_edit.setPlaceholderText("Enter mode name...")
        self.new_mode_edit.returnPressed.connect(self._add_mode)
        button_layout.addWidget(self.new_mode_edit)
        
        self.add_btn = QPushButton("Add Mode")
        self.add_btn.clicked.connect(self._add_mode)
        button_layout.addWidget(self.add_btn)
        
        button_layout.addWidget(QLabel(""))  # Spacer
        
        # Edit/Delete buttons
        self.edit_btn = QPushButton("Edit Selected")
        self.edit_btn.clicked.connect(self._edit_mode)
        self.edit_btn.setEnabled(False)
        button_layout.addWidget(self.edit_btn)
        
        self.delete_btn = QPushButton("Delete Selected")
        self.delete_btn.clicked.connect(self._delete_mode)
        self.delete_btn.setEnabled(False)
        button_layout.addWidget(self.delete_btn)
        
        button_layout.addWidget(QLabel(""))  # Spacer
        
        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._refresh_list)
        button_layout.addWidget(self.refresh_btn)
        
        button_layout.addStretch()  # Push everything to top
        
        list_layout.addLayout(button_layout)
        layout.addLayout(list_layout)

        # Close button
        close_layout = QHBoxLayout()
        close_layout.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_layout.addWidget(close_btn)
        layout.addLayout(close_layout)

    def _refresh_list(self):
        """Refresh the mode list from database"""
        self.mode_list.clear()
        try:
            modes = models.list_modes()
            for mode in modes:
                item = QListWidgetItem()
                if mode['id'] is None:
                    # Orphaned mode (exists in time_entries but not in modes table)
                    item.setText(f"{mode['label']} (Used {mode['count']} times) [Auto-detected]")
                else:
                    item.setText(f"{mode['label']} (Used {mode['count']} times)")
                item.setData(Qt.UserRole, mode)
                self.mode_list.addItem(item)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load modes: {e}")

    def _on_selection_changed(self):
        """Enable/disable buttons based on selection"""
        has_selection = bool(self.mode_list.currentItem())
        self.edit_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

    def _add_mode(self):
        """Add a new mode"""
        mode_name = self.new_mode_edit.text().strip()
        if not mode_name:
            QMessageBox.warning(self, "Error", "Please enter a mode name.")
            return
        
        try:
            # Check if mode already exists using improved validation
            if models.check_mode_name_conflict(mode_name):
                QMessageBox.warning(
                    self, 
                    "Name Conflict", 
                    f"Cannot add '{mode_name}' because a mode with this name already exists in the database.\n\n"
                    "Mode names are compared case-insensitively and with spaces trimmed."
                )
                return
            
            models.upsert_mode(mode_name)
            self.new_mode_edit.clear()
            self._refresh_list()
            QMessageBox.information(self, "Success", f"Mode '{mode_name}' added successfully.")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to add mode: {e}")

    def _edit_mode(self):
        """Edit the selected mode"""
        current_item = self.mode_list.currentItem()
        if not current_item:
            return
        
        mode_data = current_item.data(Qt.UserRole)
        current_name = mode_data['label']
        
        # Check if this is an orphaned mode
        if mode_data['id'] is None:
            QMessageBox.warning(self, "Cannot Edit", 
                f"Cannot edit '{current_name}' because it's an auto-detected mode that exists only in time entries.\n\n"
                "You can add it as a proper mode by typing the same name in the 'Add New Mode' field.")
            return
        
        # Simple input dialog for editing
        from PySide6.QtWidgets import QInputDialog
        new_name, ok = QInputDialog.getText(
            self, 
            "Edit Mode", 
            f"Edit mode name:",
            text=current_name
        )
        
        if not ok or not new_name.strip():
            return
            
        new_name = new_name.strip()
        if new_name == current_name:
            return  # No change
        
        try:
            # Check if new name already exists using improved validation
            if models.check_mode_name_conflict(new_name, exclude_id=mode_data['id']):
                QMessageBox.warning(
                    self, 
                    "Name Conflict", 
                    f"Cannot rename to '{new_name}' because a mode with this name already exists in the database.\n\n"
                    "Mode names are compared case-insensitively and with spaces trimmed."
                )
                return
            
            # Rename the mode everywhere it appears
            models.rename_mode_everywhere(current_name, new_name)
            self._refresh_list()
            
            # Show success message with info about what was updated
            QMessageBox.information(
                self, 
                "Success", 
                f"Mode renamed from '{current_name}' to '{new_name}'.\n\n"
                "All existing time entries using this mode have been updated automatically."
            )
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to edit mode: {e}")

    def _delete_mode(self):
        """Delete the selected mode"""
        current_item = self.mode_list.currentItem()
        if not current_item:
            return
        
        mode_data = current_item.data(Qt.UserRole)
        mode_name = mode_data['label']
        usage_count = mode_data['count']
        
        # Check if this is an orphaned mode
        if mode_data['id'] is None:
            QMessageBox.warning(self, "Cannot Delete", 
                f"Cannot delete '{mode_name}' because it's an auto-detected mode that exists only in time entries.\n\n"
                "This mode will automatically disappear if you delete all time entries that use it.")
            return
        
        # Confirmation dialog
        if usage_count > 0:
            msg = f"Are you sure you want to delete the mode '{mode_name}'?\n\nThis mode has been used {usage_count} times. Deleting it will remove it from the list but won't affect existing time entries."
        else:
            msg = f"Are you sure you want to delete the mode '{mode_name}'?"
        
        resp = QMessageBox.question(
            self,
            "Confirm Mode Deletion",
            msg,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        
        if resp != QMessageBox.Yes:
            return
        
        try:
            models.delete_mode(mode_data['id'])
            self._refresh_list()
            QMessageBox.information(self, "Success", f"Mode '{mode_name}' deleted successfully.")
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to delete mode: {e}")
