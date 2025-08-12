import pytest
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add the src directory to the Python path
sys.path.insert(0, 'src')

from PySide6.QtWidgets import QApplication, QCheckBox
from PySide6.QtCore import QDate, QTime
from PySide6.QtTest import QTest

from virtualmanweek.ui.edit_hours_dialog import EditHoursDialog


@pytest.fixture
def qapp():
    """Create QApplication instance for testing"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_entries():
    """Sample time entries for testing"""
    base_time = datetime(2024, 1, 15, 9, 0, 0)
    return [
        {
            'id': 1,
            'mode_label': 'Development',
            'project_code': 'PROJ1',
            'project_name': 'Test Project',
            'start_ts': int(base_time.timestamp()),
            'end_ts': int((base_time + timedelta(hours=2)).timestamp()),
            'active_seconds': 6000,
            'idle_seconds': 1200,
            'manual_seconds': 0,
            'elapsed_seconds': 7200,
            'description': 'Test task',
            'project_id': 1
        },
        {
            'id': 2,
            'mode_label': 'Meeting',
            'project_code': 'PROJ2',
            'project_name': 'Another Project',
            'start_ts': int((base_time + timedelta(hours=2)).timestamp()),
            'end_ts': int((base_time + timedelta(hours=3)).timestamp()),
            'active_seconds': 3000,
            'idle_seconds': 600,
            'manual_seconds': 0,
            'elapsed_seconds': 3600,
            'description': 'Team meeting',
            'project_id': 2
        }
    ]


@pytest.fixture
def mock_database(sample_entries):
    """Mock database connection and queries"""
    with patch('virtualmanweek.ui.edit_hours_dialog.models') as mock_models:
        # Mock the database query
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        
        # Convert entries to database row format
        rows = []
        for entry in sample_entries:
            rows.append((
                entry['id'],
                entry['mode_label'], 
                entry['project_code'],
                entry['project_name'],
                entry['start_ts'],
                entry['end_ts'],
                entry['active_seconds'],
                entry['idle_seconds'],
                entry['manual_seconds'],
                entry['description'],
                entry['project_id']
            ))
        
        mock_cur.fetchall.return_value = rows
        mock_conn.cursor.return_value = mock_cur
        mock_models.connect.return_value.__enter__.return_value = mock_conn
        
        yield mock_models


class TestEditHoursDialog:
    """Test cases for the updated Edit Hours Dialog"""
    
    def test_dialog_initialization(self, qapp, mock_database):
        """Test that the dialog initializes correctly"""
        dialog = EditHoursDialog()
        
        assert dialog.windowTitle() == "Edit Hours"
        assert dialog.isModal()
        assert len(dialog.entries) == 2  # Should load sample entries
        assert len(dialog.changed_entries) == 0  # No changes initially
        
        dialog.close()
    
    def test_table_setup(self, qapp, mock_database):
        """Test that the table is set up correctly with checkboxes"""
        dialog = EditHoursDialog()
        
        # Should have 7 columns including checkbox
        assert dialog.table.columnCount() == 7
        
        # Should have rows for each entry
        assert dialog.table.rowCount() == 2
        
        # First column should contain checkboxes
        checkbox1 = dialog.table.cellWidget(0, 0)
        checkbox2 = dialog.table.cellWidget(1, 0)
        
        assert isinstance(checkbox1, QCheckBox)
        assert isinstance(checkbox2, QCheckBox)
        assert not checkbox1.isChecked()
        assert not checkbox2.isChecked()
        
        dialog.close()
    
    def test_select_all_functionality(self, qapp, mock_database):
        """Test select all functionality"""
        dialog = EditHoursDialog()
        
        # Initially nothing selected
        selected = dialog.get_selected_rows()
        assert len(selected) == 0
        
        # Select all
        dialog.select_all()
        
        # All checkboxes should be checked
        for row in range(dialog.table.rowCount()):
            checkbox = dialog.table.cellWidget(row, 0)
            assert checkbox.isChecked()
        
        selected = dialog.get_selected_rows()
        assert len(selected) == 2
        assert selected == [0, 1]
        
        dialog.close()
    
    def test_select_none_functionality(self, qapp, mock_database):
        """Test select none functionality"""
        dialog = EditHoursDialog()
        
        # First select all
        dialog.select_all()
        assert len(dialog.get_selected_rows()) == 2
        
        # Then select none
        dialog.select_none()
        
        # All checkboxes should be unchecked
        for row in range(dialog.table.rowCount()):
            checkbox = dialog.table.cellWidget(row, 0)
            assert not checkbox.isChecked()
        
        selected = dialog.get_selected_rows()
        assert len(selected) == 0
        
        dialog.close()
    
    def test_edit_selected_no_selection(self, qapp, mock_database):
        """Test edit selected with no selection shows message"""
        dialog = EditHoursDialog()
        
        with patch('virtualmanweek.ui.edit_hours_dialog.QMessageBox') as mock_box:
            dialog.edit_selected()
            mock_box.information.assert_called_once()
        
        dialog.close()
    
    def test_edit_selected_multiple_selection(self, qapp, mock_database):
        """Test edit selected with multiple selections shows message"""
        dialog = EditHoursDialog()
        
        # Select multiple entries
        checkbox1 = dialog.table.cellWidget(0, 0)
        checkbox2 = dialog.table.cellWidget(1, 0)
        checkbox1.setChecked(True)
        checkbox2.setChecked(True)
        
        with patch('virtualmanweek.ui.edit_hours_dialog.QMessageBox') as mock_box:
            dialog.edit_selected()
            mock_box.information.assert_called_once()
            # Should mention multiple selection
            call_args = mock_box.information.call_args[0]
            assert "Multiple Selection" in call_args[1]
        
        dialog.close()
    
    def test_edit_selected_with_selection(self, qapp, mock_database):
        """Test edit selected with entries selected"""
        dialog = EditHoursDialog()
        
        # Select first entry
        checkbox = dialog.table.cellWidget(0, 0)
        checkbox.setChecked(True)
        
        # Mock the EditSingleEntryDialog
        with patch('virtualmanweek.ui.edit_hours_dialog.EditSingleEntryDialog') as mock_dialog_class:
            mock_dialog = MagicMock()
            mock_dialog.exec.return_value = EditHoursDialog.Accepted
            mock_dialog.get_modified_entry.return_value = {
                'id': 1,
                'mode_label': 'Modified Development',
                'project_code': 'PROJ1',
                'project_name': 'Test Project',
                'start_ts': 123456789,
                'end_ts': 123460389,
                'active_seconds': 3000,
                'idle_seconds': 600,
                'manual_seconds': 0,
                'elapsed_seconds': 3600,
                'description': 'Modified task',
                'project_id': 1
            }
            mock_dialog_class.return_value = mock_dialog
            
            dialog.edit_selected()
            
            # Should have created edit dialog
            mock_dialog_class.assert_called_once()
            
            # Should have marked entry as changed
            assert 0 in dialog.changed_entries
            assert dialog.save_btn.isEnabled()
        
        dialog.close()
    
    def test_highlight_changed_row(self, qapp, mock_database):
        """Test that changed rows are highlighted correctly"""
        dialog = EditHoursDialog()
        
        # Highlight row 0
        dialog.highlight_changed_row(0)
        
        # Check that items in row 0 have the correct background color (skip checkbox column)
        for col in range(1, dialog.table.columnCount()):
            item = dialog.table.item(0, col)
            if item:
                # Should have steel blue background
                bg_color = item.background().color()
                assert bg_color.red() == 70
                assert bg_color.green() == 130
                assert bg_color.blue() == 180
                
                # Should have white text
                text_color = item.foreground().color()
                assert text_color.red() == 255
                assert text_color.green() == 255
                assert text_color.blue() == 255
        
        dialog.close()
    
    def test_refresh_table_display(self, qapp, mock_database):
        """Test that table display refreshes correctly after changes"""
        dialog = EditHoursDialog()
        
        # Modify an entry
        dialog.entries[0]['mode_label'] = 'Modified Mode'
        dialog.entries[0]['elapsed_seconds'] = 5400  # 1.5 hours
        
        # Refresh display
        dialog.refresh_table_display()
        
        # Check that table shows updated values
        mode_item = dialog.table.item(0, 1)
        assert mode_item.text() == 'Modified Mode'
        
        duration_item = dialog.table.item(0, 5)
        assert duration_item.text() == '01:30:00'
        
        dialog.close()
    
    def test_save_changes_no_changes(self, qapp, mock_database):
        """Test save changes with no modifications"""
        dialog = EditHoursDialog()
        
        with patch('virtualmanweek.ui.edit_hours_dialog.QMessageBox') as mock_box:
            dialog.save_changes()
            mock_box.information.assert_called_once()
        
        dialog.close()
    
    def test_save_changes_with_modifications(self, qapp, mock_database):
        """Test save changes with modifications"""
        dialog = EditHoursDialog()
        
        # Mark an entry as changed
        dialog.changed_entries.add(0)
        dialog.entries[0]['mode_label'] = 'Modified Mode'
        
        with patch('virtualmanweek.ui.edit_hours_dialog.QMessageBox') as mock_box:
            with patch('virtualmanweek.ui.edit_hours_dialog.models') as mock_models:
                mock_conn = MagicMock()
                mock_cur = MagicMock()
                mock_conn.cursor.return_value = mock_cur
                mock_models.connect.return_value.__enter__.return_value = mock_conn
                mock_models.list_all_projects.return_value = []
                
                # Mock user clicking Yes
                mock_box.question.return_value = mock_box.Yes
                
                dialog.save_changes()
                
                # Should show confirmation dialog
                mock_box.question.assert_called_once()
                
                # Should execute database update
                mock_cur.execute.assert_called_once()
        
        dialog.close()
    
    def test_format_duration(self, qapp, mock_database):
        """Test duration formatting"""
        dialog = EditHoursDialog()
        
        # Test various durations
        assert dialog.format_duration(3661) == "01:01:01"  # 1 hour, 1 minute, 1 second
        assert dialog.format_duration(7200) == "02:00:00"  # 2 hours
        assert dialog.format_duration(0) == "00:00:00"     # 0 seconds
        assert dialog.format_duration(59) == "00:00:59"    # 59 seconds
        
        dialog.close()
