import pytest
import sys
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

# Add the src directory to the Python path
sys.path.insert(0, 'src')

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDate, QTime
from PySide6.QtTest import QTest

from virtualmanweek.ui.edit_single_entry_dialog import EditSingleEntryDialog


@pytest.fixture
def qapp():
    """Create QApplication instance for testing"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_entry():
    """Sample time entry for testing"""
    base_time = datetime(2024, 1, 15, 9, 0, 0)
    return {
        'id': 1,
        'mode_label': 'Development',
        'project_id': 1,
        'project_code': 'PROJ1',
        'project_name': 'Test Project',
        'start_ts': int(base_time.timestamp()),
        'end_ts': int((base_time + timedelta(hours=2)).timestamp()),
        'active_seconds': 6000,
        'idle_seconds': 1200,
        'manual_seconds': 0,
        'elapsed_seconds': 7200,
        'description': 'Test task'
    }


@pytest.fixture
def mock_models():
    """Mock the models module"""
    with patch('virtualmanweek.ui.edit_single_entry_dialog.models') as mock:
        mock.list_all_projects.return_value = [
            {'id': 1, 'code': 'PROJ1', 'name': 'Test Project'},
            {'id': 2, 'code': 'PROJ2', 'name': 'Another Project'}
        ]
        mock.list_modes.return_value = [
            {'label': 'Development'},
            {'label': 'Meeting'},
            {'label': 'Testing'}
        ]
        yield mock


class TestEditSingleEntryDialog:
    """Test cases for the Edit Single Entry Dialog"""
    
    def test_dialog_initialization(self, qapp, sample_entry, mock_models):
        """Test that the dialog initializes correctly"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        assert dialog.windowTitle() == "Edit Time Entry"
        assert dialog.isModal()
        assert dialog.entry is not None  # Should have the entry data
        
        dialog.close()
    
    def test_populate_fields(self, qapp, sample_entry, mock_models):
        """Test that fields are populated correctly from entry data"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Check date
        expected_date = datetime.fromtimestamp(sample_entry['start_ts']).date()
        actual_date = dialog.date_edit.date().toPython()
        assert actual_date == expected_date
        
        # Check mode
        assert dialog.mode_combo.currentText() == 'Development'
        
        # Check times
        start_dt = datetime.fromtimestamp(sample_entry['start_ts'])
        end_dt = datetime.fromtimestamp(sample_entry['end_ts'])
        
        assert dialog.start_time_edit.time().hour() == start_dt.hour
        assert dialog.start_time_edit.time().minute() == start_dt.minute
        
        assert dialog.end_time_edit.time().hour() == end_dt.hour
        assert dialog.end_time_edit.time().minute() == end_dt.minute
        
        # Check description
        assert dialog.description_edit.toPlainText() == 'Test task'
        
        dialog.close()
    
    def test_duration_calculation(self, qapp, sample_entry, mock_models):
        """Test that duration is calculated correctly"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Duration should be 2 hours = 02:00:00
        assert dialog.duration_label.text() == "02:00:00"
        
        dialog.close()
    
    def test_time_validation(self, qapp, sample_entry, mock_models):
        """Test that time validation works correctly"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Set invalid time (end same as start)
        dialog.start_time_edit.setTime(QTime(10, 0, 0))
        dialog.end_time_edit.setTime(QTime(10, 0, 0))
        
        # Should disable save button
        assert not dialog.save_btn.isEnabled()
        
        # Set valid time
        dialog.end_time_edit.setTime(QTime(11, 0, 0))
        assert dialog.save_btn.isEnabled()
        
        dialog.close()
    
    def test_day_boundary_crossing(self, qapp, sample_entry, mock_models):
        """Test handling of day boundary crossing"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Set start time late and end time early (crosses midnight)
        dialog.start_time_edit.setTime(QTime(23, 0, 0))
        dialog.end_time_edit.setTime(QTime(1, 0, 0))
        
        # Should calculate 2 hours duration
        assert dialog.duration_label.text() == "02:00:00"
        assert dialog.save_btn.isEnabled()
        
        dialog.close()
    
    def test_mode_validation(self, qapp, sample_entry, mock_models):
        """Test mode validation"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Empty mode should show warning
        dialog.mode_combo.setEditText("")
        
        with patch('virtualmanweek.ui.edit_single_entry_dialog.QMessageBox') as mock_box:
            dialog.save_changes()
            # Should show warning for empty mode
            mock_box.warning.assert_called_once()
        
        dialog.close()
    
    def test_save_changes_updates_entry(self, qapp, sample_entry, mock_models):
        """Test that save changes updates the entry correctly"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Modify some values
        new_date = QDate(2024, 1, 16)
        dialog.date_edit.setDate(new_date)
        dialog.mode_combo.setEditText("Meeting")
        dialog.start_time_edit.setTime(QTime(10, 0, 0))
        dialog.end_time_edit.setTime(QTime(12, 30, 0))
        
        # Mock accept to bypass actual dialog closure
        with patch.object(dialog, 'accept'):
            dialog.save_changes()
            
        modified_entry = dialog.get_modified_entry()
        
        # Check that entry was updated
        assert modified_entry['mode_label'] == "Meeting"
        
        # Check timestamps reflect new date/times
        new_start = datetime(2024, 1, 16, 10, 0, 0)
        new_end = datetime(2024, 1, 16, 12, 30, 0)
        
        assert modified_entry['start_ts'] == int(new_start.timestamp())
        assert modified_entry['end_ts'] == int(new_end.timestamp())
        
        # Check duration calculations
        expected_duration = int((new_end - new_start).total_seconds())
        assert modified_entry['elapsed_seconds'] == expected_duration
        
        dialog.close()
    
    def test_proportional_time_adjustment(self, qapp, sample_entry, mock_models):
        """Test that time components are adjusted proportionally"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        original_duration = sample_entry['elapsed_seconds']  # 7200 seconds (2 hours)
        original_active = sample_entry['active_seconds']     # 6000 seconds
        original_idle = sample_entry['idle_seconds']         # 1200 seconds
        
        # Change duration to 1 hour (half the original)
        dialog.start_time_edit.setTime(QTime(9, 0, 0))
        dialog.end_time_edit.setTime(QTime(10, 0, 0))
        
        with patch.object(dialog, 'accept'):
            dialog.save_changes()
            
        modified_entry = dialog.get_modified_entry()
        
        # New duration should be 3600 seconds (1 hour)
        new_duration = modified_entry['elapsed_seconds']
        ratio = new_duration / original_duration
        
        # Time components should be scaled proportionally
        expected_active = int(original_active * ratio)
        expected_idle = int(original_idle * ratio)
        
        assert modified_entry['active_seconds'] == expected_active
        assert modified_entry['idle_seconds'] == expected_idle
        
        dialog.close()
    
    def test_description_editing(self, qapp, sample_entry, mock_models):
        """Test description editing functionality"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Modify description
        new_description = "Updated task description with more details"
        dialog.description_edit.setPlainText(new_description)
        
        with patch.object(dialog, 'accept'):
            dialog.save_changes()
            
        modified_entry = dialog.get_modified_entry()
        assert modified_entry['description'] == new_description
        
        dialog.close()
    
    def test_empty_description(self, qapp, sample_entry, mock_models):
        """Test handling of empty description"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Clear description
        dialog.description_edit.setPlainText("")
        
        with patch.object(dialog, 'accept'):
            dialog.save_changes()
            
        modified_entry = dialog.get_modified_entry()
        assert modified_entry['description'] == ""
        
        dialog.close()
    
    def test_project_selection(self, qapp, sample_entry, mock_models):
        """Test project selection functionality"""
        dialog = EditSingleEntryDialog(sample_entry)
        
        # Should have "No Project" plus the mocked projects
        assert dialog.project_combo.count() == 3  # No Project + 2 mocked projects
        
        # Select different project
        dialog.project_combo.setCurrentIndex(2)  # Select PROJ2
        
        with patch.object(dialog, 'accept'):
            dialog.save_changes()
            
        modified_entry = dialog.get_modified_entry()
        assert modified_entry['project_id'] == 2
        
        dialog.close()
