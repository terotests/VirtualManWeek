from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QLabel, QCheckBox, QDateEdit, QFormLayout
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QFont, QColor
from datetime import datetime
from typing import List, Dict, Any
from ..db import models
from .edit_single_entry_dialog import EditSingleEntryDialog


class EditHoursDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Hours")
        self.setModal(True)
        self.resize(1000, 600)
        
        self.entries = []
        self.changed_entries = set()  # Track which entries have been modified
        self.current_date = datetime.now().date()
        self.setup_ui()
        self.load_entries_for_date()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Edit Time Entries")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # Date selection
        date_layout = QFormLayout()
        self.date_edit = QDateEdit()
        self.date_edit.setDate(QDate.fromString(self.current_date.strftime('%Y-%m-%d'), 'yyyy-MM-dd'))
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.on_date_changed)
        date_layout.addRow("Date:", self.date_edit)
        layout.addLayout(date_layout)
        
        # Instructions
        instructions = QLabel(
            "Select entries using checkboxes, then click 'Edit Selected' to modify them.\n"
            "Only one entry can be edited at a time. Modified entries will be highlighted in dark blue."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(instructions)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Select", "Mode", "Project", "Start Time", "End Time", "Duration", "Description"
        ])
        
        # Make table fill width
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Select - fixed width
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Mode
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Project
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Start Time
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # End Time
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Duration
        header.setSectionResizeMode(6, QHeaderView.Stretch)  # Description
        
        # Set specific width for checkbox column
        header.resizeSection(0, 60)
        
        layout.addWidget(self.table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_none)
        
        self.edit_selected_btn = QPushButton("Edit Selected")
        self.edit_selected_btn.clicked.connect(self.edit_selected)
        
        # Delete button (initially hidden)
        self.delete_selected_btn = QPushButton("Delete Selected")
        self.delete_selected_btn.clicked.connect(self.delete_selected)
        self.delete_selected_btn.setVisible(False)  # Hidden by default
        self.delete_selected_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
        """)
        
        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self.save_changes)
        self.save_btn.setEnabled(False)  # Disabled until changes are made
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.select_none_btn)
        button_layout.addWidget(self.edit_selected_btn)
        button_layout.addWidget(self.delete_selected_btn)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_entries_for_date(self):
        """Load time entries for the selected date"""
        try:
            selected_date = self.current_date.strftime('%Y-%m-%d')
            
            # Get entries for selected date, ordered by start time
            query = """
                SELECT te.id, te.mode_label, p.code as project_code, p.name as project_name,
                       te.start_ts, te.end_ts, te.active_seconds, te.idle_seconds, te.manual_seconds, 
                       te.description, te.project_id
                FROM time_entries te
                LEFT JOIN projects p ON te.project_id = p.id
                WHERE te.date = ?
                ORDER BY te.start_ts ASC
            """
            
            with models.connect() as conn:
                cur = conn.cursor()
                cur.execute(query, (selected_date,))
                rows = cur.fetchall()
            
            self.entries = []
            
            for row in rows:
                # Calculate total elapsed seconds from active + idle + manual
                active_seconds = row[6] or 0
                idle_seconds = row[7] or 0
                manual_seconds = row[8] or 0
                elapsed_seconds = active_seconds + idle_seconds + manual_seconds
                
                entry = {
                    'id': row[0],
                    'mode_label': row[1],
                    'project_code': row[2] or '',
                    'project_name': row[3] or '',
                    'start_ts': row[4],
                    'end_ts': row[5],
                    'active_seconds': active_seconds,
                    'idle_seconds': idle_seconds,
                    'manual_seconds': manual_seconds,
                    'elapsed_seconds': elapsed_seconds,
                    'description': row[9] or '',
                    'project_id': row[10]
                }
                self.entries.append(entry)
            
            self.populate_table()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load entries: {e}")
    
    def on_date_changed(self, new_date: QDate):
        """Handle date selection change"""
        self.current_date = new_date.toPython()
        
        # Check if there are unsaved changes
        if self.changed_entries:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to save them before changing the date?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Yes:
                # Save changes first
                self.save_changes()
                if self.changed_entries:  # If save was cancelled
                    # Revert date selection
                    self.date_edit.setDate(QDate.fromString(
                        datetime.now().date().strftime('%Y-%m-%d'), 'yyyy-MM-dd'
                    ))
                    return
            elif reply == QMessageBox.Cancel:
                # Revert date selection
                old_date = datetime.now().date() if not hasattr(self, '_last_loaded_date') else self._last_loaded_date
                self.date_edit.setDate(QDate.fromString(old_date.strftime('%Y-%m-%d'), 'yyyy-MM-dd'))
                return
        
        # Load entries for new date
        self.changed_entries.clear()
        self.save_btn.setEnabled(False)
        self._last_loaded_date = self.current_date
        self.load_entries_for_date()
    
    def populate_table(self):
        """Populate the table with current entries"""
        self.table.setRowCount(len(self.entries))
        
        for row, entry in enumerate(self.entries):
            # Checkbox for selection
            checkbox = QCheckBox()
            checkbox.setChecked(False)
            checkbox.stateChanged.connect(self.update_edit_button_state)
            self.table.setCellWidget(row, 0, checkbox)
            
            # Mode
            mode_item = QTableWidgetItem(entry['mode_label'])
            mode_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, mode_item)
            
            # Project
            project_text = f"{entry['project_code']} - {entry['project_name']}" if entry['project_code'] else "No Project"
            project_item = QTableWidgetItem(project_text)
            project_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 2, project_item)
            
            # Start Time (read-only)
            start_time = datetime.fromtimestamp(entry['start_ts']).strftime('%H:%M:%S')
            start_item = QTableWidgetItem(start_time)
            start_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 3, start_item)
            
            # End Time (read-only display)
            end_time = datetime.fromtimestamp(entry['end_ts']).strftime('%H:%M:%S')
            end_item = QTableWidgetItem(end_time)
            end_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 4, end_item)
            
            # Duration
            duration = self.format_duration(entry['elapsed_seconds'])
            duration_item = QTableWidgetItem(duration)
            duration_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 5, duration_item)
            
            # Description
            desc_item = QTableWidgetItem(entry['description'])
            desc_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 6, desc_item)
        
        # Update edit button state
        self.update_edit_button_state()
    
    def format_duration(self, seconds: int) -> str:
        """Format duration in a readable way"""
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def select_all(self):
        """Select all entries"""
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(True)
        self.update_edit_button_state()
    
    def select_none(self):
        """Deselect all entries"""
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox:
                checkbox.setChecked(False)
        self.update_edit_button_state()
    
    def update_edit_button_state(self):
        """Update the Edit Selected and Delete Selected button states based on selection"""
        selected_count = len(self.get_selected_rows())
        
        # Edit button: Enable only when exactly one row is selected
        self.edit_selected_btn.setEnabled(selected_count == 1)
        
        # Update edit button text to be more descriptive
        if selected_count == 0:
            self.edit_selected_btn.setText("Edit Selected (None)")
        elif selected_count == 1:
            self.edit_selected_btn.setText("Edit Selected (1)")
        else:
            self.edit_selected_btn.setText(f"Edit Selected ({selected_count}) - Disabled")
        
        # Delete button: Visible and enabled when any rows are selected
        if selected_count > 0:
            self.delete_selected_btn.setVisible(True)
            self.delete_selected_btn.setEnabled(True)
            if selected_count == 1:
                self.delete_selected_btn.setText("Delete Selected Entry")
            else:
                self.delete_selected_btn.setText(f"Delete Selected Entries ({selected_count})")
        else:
            self.delete_selected_btn.setVisible(False)
    
    def get_selected_rows(self) -> List[int]:
        """Get list of selected row indices"""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                selected.append(row)
        return selected
    
    def edit_selected(self):
        """Edit selected entry (only allows single selection)"""
        selected_rows = self.get_selected_rows()
        
        if len(selected_rows) == 0:
            QMessageBox.information(self, "No Selection", "Please select exactly one entry to edit.")
            return
        elif len(selected_rows) > 1:
            QMessageBox.information(
                self, "Multiple Selection", 
                f"You have selected {len(selected_rows)} entries. Please select exactly one entry to edit."
            )
            return
        
        # Edit the single selected entry
        row = selected_rows[0]
        if row >= len(self.entries):
            return
            
        entry = self.entries[row]
        
        # Create edit dialog
        dialog = EditSingleEntryDialog(entry, self)
        if dialog.exec() == QDialog.Accepted:
            # Update the entry with changes
            modified_entry = dialog.get_modified_entry()
            self.entries[row] = modified_entry
            self.changed_entries.add(row)
            self.highlight_changed_row(row)
            
            # Refresh table display
            self.refresh_table_display()
            
            # Enable save button if there are changes
            if self.changed_entries:
                self.save_btn.setEnabled(True)
    
    def delete_selected(self):
        """Delete selected entries after confirmation"""
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            return
        
        # Get selected entries for confirmation dialog
        selected_entries = [self.entries[row] for row in selected_rows]
        
        # Create confirmation dialog with details
        count = len(selected_entries)
        if count == 1:
            title = "Delete Time Entry"
            message = "Are you sure you want to delete this time entry?"
        else:
            title = "Delete Time Entries"
            message = f"Are you sure you want to delete these {count} time entries?"
        
        # Add entry details to confirmation
        details = []
        for entry in selected_entries:
            start_time = datetime.fromtimestamp(entry['start_ts']).strftime('%H:%M:%S')
            end_time = datetime.fromtimestamp(entry['end_ts']).strftime('%H:%M:%S')
            project_display = f"{entry.get('project_code', 'No Project')} - {entry.get('project_name', '')}" if entry.get('project_id') else "No Project"
            duration = self.format_duration(entry['elapsed_seconds'])
            details.append(f"• {start_time} - {end_time} | {entry['mode_label']} | {project_display} | {duration}")
        
        full_message = f"{message}\n\nEntries to be deleted:\n" + "\n".join(details[:10])
        if len(details) > 10:
            full_message += f"\n... and {len(details) - 10} more entries"
        
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            title,
            full_message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Delete entries from database
            entry_ids = [entry['id'] for entry in selected_entries]
            
            try:
                from ..db.models import delete_time_entries
                deleted_count = delete_time_entries(entry_ids)
                
                if deleted_count > 0:
                    # Remove entries from local list (in reverse order to maintain indices)
                    for row in sorted(selected_rows, reverse=True):
                        del self.entries[row]
                    
                    # Clear changed entries that were deleted
                    self.changed_entries = {i for i in self.changed_entries if i not in selected_rows}
                    # Adjust changed entries indices for remaining entries
                    new_changed_entries = set()
                    for changed_row in self.changed_entries:
                        new_index = changed_row - sum(1 for deleted_row in selected_rows if deleted_row < changed_row)
                        new_changed_entries.add(new_index)
                    self.changed_entries = new_changed_entries
                    
                    # Refresh the table display
                    self.populate_table()
                    
                    # Show success message
                    if count == 1:
                        QMessageBox.information(self, "Entry Deleted", "Time entry has been deleted successfully.")
                    else:
                        QMessageBox.information(self, "Entries Deleted", f"{deleted_count} time entries have been deleted successfully.")
                    
                    # Update button states
                    self.update_edit_button_state()
                    
                else:
                    QMessageBox.warning(self, "Delete Failed", "No entries were deleted. Please try again.")
                    
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Failed to delete entries: {str(e)}")

    def refresh_table_display(self):
        """Refresh the table display after changes"""
        for row in range(len(self.entries)):
            entry = self.entries[row]
            
            # Update mode
            self.table.item(row, 1).setText(entry['mode_label'])
            
            # Update project - look up current project info if needed
            if entry.get('project_id'):
                try:
                    projects = models.list_all_projects()
                    project_info = next((p for p in projects if p['id'] == entry['project_id']), None)
                    if project_info:
                        entry['project_code'] = project_info['code']
                        entry['project_name'] = project_info['name']
                        project_text = f"{project_info['code']} - {project_info['name']}"
                    else:
                        entry['project_code'] = ''
                        entry['project_name'] = ''
                        project_text = "No Project"
                except Exception:
                    project_text = "No Project"
            else:
                entry['project_code'] = ''
                entry['project_name'] = ''
                project_text = "No Project"
            
            self.table.item(row, 2).setText(project_text)
            
            # Update times
            start_time = datetime.fromtimestamp(entry['start_ts']).strftime('%H:%M:%S')
            self.table.item(row, 3).setText(start_time)
            
            end_time = datetime.fromtimestamp(entry['end_ts']).strftime('%H:%M:%S')
            self.table.item(row, 4).setText(end_time)
            
            # Update duration
            duration = self.format_duration(entry['elapsed_seconds'])
            self.table.item(row, 5).setText(duration)
            
            # Update description
            self.table.item(row, 6).setText(entry.get('description', ''))
    
    def highlight_changed_row(self, row: int):
        """Highlight a row to show it has been modified"""
        dark_blue = QColor(70, 130, 180)  # Steel blue for better contrast
        for col in range(1, self.table.columnCount()):  # Skip checkbox column
            item = self.table.item(row, col)
            if item:
                item.setBackground(dark_blue)
                item.setForeground(QColor(255, 255, 255))  # White text for readability
    
    def save_changes(self):
        """Save all changes to the database"""
        try:
            if not self.changed_entries:
                QMessageBox.information(self, "No Changes", "No changes have been made.")
                self.reject()
                return
            
            # Build summary of changes
            summary = []
            summary.append(f"You are about to modify {len(self.changed_entries)} time entries:")
            summary.append("")
            
            for row in sorted(self.changed_entries):
                entry = self.entries[row]
                
                # For project, we need to look up the current project info
                if entry.get('project_id'):
                    projects = models.list_all_projects()
                    project_info = next((p for p in projects if p['id'] == entry['project_id']), None)
                    if project_info:
                        entry['project_code'] = project_info['code']
                        entry['project_name'] = project_info['name']
                    else:
                        entry['project_code'] = ''
                        entry['project_name'] = ''
                else:
                    entry['project_code'] = ''
                    entry['project_name'] = ''
                
                start_time = datetime.fromtimestamp(entry['start_ts']).strftime('%H:%M:%S')
                end_time = datetime.fromtimestamp(entry['end_ts']).strftime('%H:%M:%S')
                duration = self.format_duration(entry['elapsed_seconds'])
                
                mode_project = f"{entry['mode_label']}"
                if entry['project_code']:
                    mode_project += f" ({entry['project_code']})"
                
                summary.append(f"• {mode_project}")
                summary.append(f"  Time: {start_time} - {end_time} ({duration})")
                summary.append("")
            
            summary_text = "\n".join(summary)
            
            # Show confirmation dialog
            reply = QMessageBox.question(
                self,
                "Confirm Changes",
                summary_text + "\nAre you sure you want to save these changes?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
            
            # Apply changes to database
            with models.connect() as conn:
                cur = conn.cursor()
                
                for row in self.changed_entries:
                    entry = self.entries[row]
                    # Update the database with all components
                    cur.execute(
                        """UPDATE time_entries 
                           SET start_ts = ?, end_ts = ?, active_seconds = ?, idle_seconds = ?, 
                               manual_seconds = ?, mode_label = ?, project_id = ?, description = ? 
                           WHERE id = ?""",
                        (entry['start_ts'], entry['end_ts'], entry['active_seconds'], 
                         entry['idle_seconds'], entry['manual_seconds'], entry['mode_label'],
                         entry.get('project_id'), entry.get('description', ''), entry['id'])
                    )
            
            QMessageBox.information(self, "Success", f"Successfully updated {len(self.changed_entries)} time entries!")
            self.accept()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")
