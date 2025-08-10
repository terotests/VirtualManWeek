"""
Simple tests for tracking engine - only testing basic functionality.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import time

from virtualmanweek.tracking.engine import Tracker, ActiveSession
from virtualmanweek.config import Settings
from virtualmanweek.db import models


@pytest.fixture
def mock_settings():
    """Create mock settings for testing"""
    return Settings(
        idle_timeout_seconds=300,
        tag_cloud_limit=10,
        discard_sub_10s_entries=True,
        language='en',
        database_path=None
    )


@pytest.fixture
def temp_db_tracker(mock_settings):
    """Create a tracker with temporary database"""
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as tmp:
        temp_path = Path(tmp.name)
    
    models.set_db_path(temp_path)
    tracker = Tracker(mock_settings)
    
    yield tracker
    
    # Cleanup
    models.set_db_path(None)
    try:
        temp_path.unlink(missing_ok=True)
    except PermissionError:
        pass  # Ignore cleanup errors


class TestActiveSession:
    def test_active_session_creation(self):
        """Test ActiveSession dataclass creation"""
        session = ActiveSession(
            project_id=1,
            mode_label="Development",
            start_ts=1000000
        )
        
        assert session.project_id == 1
        assert session.mode_label == "Development"
        assert session.start_ts == 1000000
        assert session.idle_accum == 0


class TestTracker:
    def test_tracker_initialization(self, mock_settings):
        """Test tracker initializes with settings"""
        tracker = Tracker(mock_settings)
        assert tracker.settings == mock_settings
        assert tracker.active is None
    
    def test_start_session(self, temp_db_tracker):
        """Test starting a tracking session"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development")
        
        assert tracker.active is not None
        assert tracker.active.project_id == 1
        assert tracker.active.mode_label == "Development"
        assert tracker.active.start_ts == 1000000
    
    def test_start_session_closes_previous(self, temp_db_tracker):
        """Test that starting new session closes previous one"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development")
        
        with patch('time.time', return_value=1001000):
            tracker.start(project_id=2, mode_label="Testing")
        
        assert tracker.active.project_id == 2
        assert tracker.active.mode_label == "Testing"
    
    def test_start_session_normalizes_mode(self, temp_db_tracker):
        """Test that mode labels are normalized (stripped)"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="  Development  ")
        
        assert tracker.active.mode_label == "Development"
    
    def test_activity_ping_updates_last_activity(self, temp_db_tracker):
        """Test that activity ping updates last activity timestamp"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development")
        
        with patch('time.time', return_value=1000060):
            tracker.activity_ping()
        
        assert tracker.active.last_activity_ts == 1000060
    
    def test_poll_basic_functionality(self, temp_db_tracker):
        """Test basic poll functionality"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development")
        
        with patch('time.time', return_value=1000010):
            with patch.object(tracker, '_check_24_hour_limit', return_value=False):
                tracker.poll()
        
        # Should have updated poll timestamp
        assert tracker.active.last_poll_ts == 1000010


class TestTrackerEdgeCases:
    def test_negative_gap_handling(self, temp_db_tracker):
        """Test handling of negative time gaps"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development")
        
        # Simulate time going backwards (shouldn't crash)
        with patch('time.time', return_value=999900):
            with patch.object(tracker, '_check_24_hour_limit', return_value=False):
                tracker.poll()
        
        # Should handle gracefully
        assert tracker.active is not None
    
    def test_zero_duration_entries(self, temp_db_tracker):
        """Test handling of zero-duration entries"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development")
        
        # Start new session immediately (zero duration)
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=2, mode_label="Testing")
        
        assert tracker.active.mode_label == "Testing"
    
    def test_manual_seconds_parameter(self, temp_db_tracker):
        """Test manual seconds parameter in start method"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development", manual_seconds=3600)
        
        assert tracker._active_manual_seconds == 3600
    
    def test_description_parameter(self, temp_db_tracker):
        """Test description parameter in start method"""
        tracker = temp_db_tracker
        
        with patch('time.time', return_value=1000000):
            tracker.start(project_id=1, mode_label="Development", description="Working on feature X")
        
        assert tracker._active_description == "Working on feature X"
