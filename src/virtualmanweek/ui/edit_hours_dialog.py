from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QTimeEdit, QLabel, QWidget
)
from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QFont, QColor
from datetime import datetime, timedelta
from typing import List, Dict, Any
from ..db import models


class EditHoursDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Hours - Today")
        self.setModal(True)
        self.resize(1200, 700)  # Made wider for better column spacing
        
        self.entries = []
        self.changed_entries = set()  # Track which entries have been modified
        self.setup_ui()
        self.load_today_entries()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel("Edit Today's Time Entries")
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "Adjust end times as needed. When you shorten an entry, the next entry will "
            "automatically start earlier if they're within 3 minutes of each other.\n"
            "Modified entries will be highlighted in dark gray."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("color: #666; margin-bottom: 10px;")
        layout.addWidget(instructions)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Mode", "Project", "Start Time", "End Time", "Duration", "Description"
        ])
        
        # Make table fill width
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Mode
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Project
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Start Time - fixed width
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # End Time - fixed width for editing
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Duration
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Description
        
        # Set specific widths for time columns to ensure QTimeEdit fits comfortably
        header.resizeSection(2, 120)  # Start Time - wider
        header.resizeSection(3, 140)  # End Time - extra wide for editing
        
        layout.addWidget(self.table)
        
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
    
    def load_today_entries(self):
        """Load today's time entries"""
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Get entries for today, ordered by start time
            query = """
                SELECT te.id, te.mode_label, p.code as project_code, p.name as project_name,
                       te.start_ts, te.end_ts, te.active_seconds, te.idle_seconds, te.manual_seconds, te.description
                FROM time_entries te
                LEFT JOIN projects p ON te.project_id = p.id
                WHERE te.date = ?
                ORDER BY te.start_ts ASC
            """
            
            with models.connect() as conn:
                cur = conn.cursor()
                cur.execute(query, (today,))
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
                    'original_end_ts': row[5],  # Keep original for reference
                    'original_start_ts': row[4]  # Keep original start too
                }
                self.entries.append(entry)
            
            self.populate_table()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load entries: {e}")
    
    def populate_table(self):
        """Populate the table with current entries"""
        self.table.setRowCount(len(self.entries))
        
        for row, entry in enumerate(self.entries):
            # Mode
            mode_item = QTableWidgetItem(entry['mode_label'])
            mode_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 0, mode_item)
            
            # Project
            project_text = f"{entry['project_code']} - {entry['project_name']}" if entry['project_code'] else "No Project"
            project_item = QTableWidgetItem(project_text)
            project_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, project_item)
            
            # Start Time (read-only)
            start_time = datetime.fromtimestamp(entry['start_ts']).strftime('%H:%M:%S')
            start_item = QTableWidgetItem(start_time)
            start_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 2, start_item)
            
            # End Time (editable)
            end_time_widget = QTimeEdit()
            end_dt = datetime.fromtimestamp(entry['end_ts'])
            end_time_widget.setTime(QTime(end_dt.hour, end_dt.minute, end_dt.second))
            end_time_widget.timeChanged.connect(lambda time, r=row: self.on_end_time_changed(r, time))
            self.table.setCellWidget(row, 3, end_time_widget)
            
            # Duration
            duration = self.format_duration(entry['elapsed_seconds'])
            duration_item = QTableWidgetItem(duration)
            duration_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 4, duration_item)
            
            # Description
            desc_item = QTableWidgetItem(entry['description'])
            desc_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 5, desc_item)
    
    def format_duration(self, seconds: int) -> str:
        """Format duration in a readable way"""
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def highlight_changed_row(self, row: int):
        """Highlight a row to show it has been modified"""
        dark_gray = QColor(169, 169, 169)  # Dark gray background for better contrast
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item:
                item.setBackground(dark_gray)
        
        # Also highlight the time edit widget with dark gray
        time_widget = self.table.cellWidget(row, 3)
        if time_widget:
            time_widget.setStyleSheet("background-color: #A9A9A9;")
    
    def on_end_time_changed(self, row: int, new_time: QTime):
        """Handle end time change and adjust subsequent entries if needed"""
        if row >= len(self.entries):
            return
        
        entry = self.entries[row]
        
        # Convert new time to timestamp
        start_dt = datetime.fromtimestamp(entry['start_ts'])
        new_end_dt = start_dt.replace(
            hour=new_time.hour(),
            minute=new_time.minute(),
            second=new_time.second()
        )
        
        # Handle day boundary crossing
        if new_end_dt < start_dt:
            new_end_dt += timedelta(days=1)
        
        new_end_ts = int(new_end_dt.timestamp())
        
        # Validation: End time cannot be before start time
        if new_end_ts <= entry['start_ts']:
            QMessageBox.warning(
                self, 
                "Invalid Time", 
                "End time cannot be before or equal to start time. Please choose a later time."
            )
            # Reset to original time
            original_end_dt = datetime.fromtimestamp(entry['end_ts'])
            time_widget = self.table.cellWidget(row, 3)
            if time_widget:
                time_widget.setTime(QTime(original_end_dt.hour, original_end_dt.minute, original_end_dt.second))
            return
        
        old_end_ts = entry['end_ts']
        
        # Calculate new duration
        new_duration = new_end_ts - entry['start_ts']
        old_duration = entry['elapsed_seconds']
        
        # Update entry - proportionally adjust active/idle/manual seconds
        if old_duration > 0:
            ratio = new_duration / old_duration
            entry['active_seconds'] = int(entry['active_seconds'] * ratio)
            entry['idle_seconds'] = int(entry['idle_seconds'] * ratio)
            entry['manual_seconds'] = int(entry['manual_seconds'] * ratio)
        else:
            # If old duration was 0, just set everything to 0
            entry['active_seconds'] = 0
            entry['idle_seconds'] = 0
            entry['manual_seconds'] = 0
        
        # Update timestamps and total elapsed time
        entry['end_ts'] = new_end_ts
        entry['elapsed_seconds'] = entry['active_seconds'] + entry['idle_seconds'] + entry['manual_seconds']
        
        # Mark this entry as changed
        self.changed_entries.add(row)
        
        # Update duration display
        duration = self.format_duration(entry['elapsed_seconds'])
        duration_item = QTableWidgetItem(duration)
        duration_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.table.setItem(row, 4, duration_item)
        
        # Highlight the changed row
        self.highlight_changed_row(row)
        
        # Check if we need to adjust the next entry
        if row + 1 < len(self.entries):
            next_entry = self.entries[row + 1]
            time_gap = next_entry['start_ts'] - old_end_ts
            
            # If the gap was 3 minutes or less, adjust the next entry's start time
            if 0 <= time_gap <= 180:  # 3 minutes = 180 seconds
                time_difference = new_end_ts - old_end_ts
                new_next_start = next_entry['start_ts'] + time_difference
                
                # Make sure we don't make the next entry negative duration
                if new_next_start < next_entry['end_ts']:
                    # Calculate the new duration for the next entry
                    new_next_duration = next_entry['end_ts'] - new_next_start
                    old_next_duration = next_entry['elapsed_seconds']
                    
                    # Proportionally adjust the time components for the next entry
                    if old_next_duration > 0:
                        ratio = new_next_duration / old_next_duration
                        next_entry['active_seconds'] = int(next_entry['active_seconds'] * ratio)
                        next_entry['idle_seconds'] = int(next_entry['idle_seconds'] * ratio)
                        next_entry['manual_seconds'] = int(next_entry['manual_seconds'] * ratio)
                    
                    # Update the next entry's timestamps and total elapsed time
                    next_entry['start_ts'] = new_next_start
                    next_entry['elapsed_seconds'] = next_entry['active_seconds'] + next_entry['idle_seconds'] + next_entry['manual_seconds']
                    
                    # Mark next entry as changed too
                    self.changed_entries.add(row + 1)
                    
                    # Update the display for the next entry
                    start_time = datetime.fromtimestamp(next_entry['start_ts']).strftime('%H:%M:%S')
                    start_item = QTableWidgetItem(start_time)
                    start_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row + 1, 2, start_item)
                    
                    # Update duration for next entry using the properly calculated elapsed_seconds
                    duration = self.format_duration(next_entry['elapsed_seconds'])
                    duration_item = QTableWidgetItem(duration)
                    duration_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                    self.table.setItem(row + 1, 4, duration_item)
                    
                    # Highlight the next row too
                    self.highlight_changed_row(row + 1)
    
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
                original_start = datetime.fromtimestamp(entry['original_start_ts']).strftime('%H:%M:%S')
                original_end = datetime.fromtimestamp(entry['original_end_ts']).strftime('%H:%M:%S')
                new_start = datetime.fromtimestamp(entry['start_ts']).strftime('%H:%M:%S')
                new_end = datetime.fromtimestamp(entry['end_ts']).strftime('%H:%M:%S')
                
                original_duration = self.format_duration(entry['original_end_ts'] - entry['original_start_ts'])
                new_duration = self.format_duration(entry['elapsed_seconds'])
                
                mode_project = f"{entry['mode_label']}"
                if entry['project_code']:
                    mode_project += f" ({entry['project_code']})"
                
                summary.append(f"• {mode_project}")
                
                if entry['start_ts'] != entry['original_start_ts']:
                    summary.append(f"  Start: {original_start} → {new_start}")
                
                if entry['end_ts'] != entry['original_end_ts']:
                    summary.append(f"  End: {original_end} → {new_end}")
                
                summary.append(f"  Duration: {original_duration} → {new_duration}")
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
                    # Update the database with all time components
                    cur.execute(
                        """UPDATE time_entries 
                           SET start_ts = ?, end_ts = ?, active_seconds = ?, idle_seconds = ?, manual_seconds = ? 
                           WHERE id = ?""",
                        (entry['start_ts'], entry['end_ts'], entry['active_seconds'], 
                         entry['idle_seconds'], entry['manual_seconds'], entry['id'])
                    )
            
            QMessageBox.information(self, "Success", f"Successfully updated {len(self.changed_entries)} time entries!")
            self.accept()
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save changes: {e}")
