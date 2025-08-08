from __future__ import annotations
from typing import List, Dict
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt
from ..db import models

class ProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Projects")
        self.setMinimumWidth(360)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget(self)
        layout.addWidget(QLabel("Active Projects:"))
        layout.addWidget(self.list_widget)

        form_row = QHBoxLayout()
        self.code_edit = QLineEdit(self)
        self.code_edit.setPlaceholderText("Code")
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Name")
        form_row.addWidget(self.code_edit, 1)
        form_row.addWidget(self.name_edit, 2)
        layout.addLayout(form_row)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton("Add / Update", self)
        self.add_btn.clicked.connect(self._add)
        self.close_btn = QPushButton("Close", self)
        self.close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

    def _load(self):
        self.list_widget.clear()
        try:
            projects = models.list_active_projects()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load projects: {e}")
            return
        for p in projects:
            item = QListWidgetItem(f"{p['code']} - {p['name']}")
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
