"""
Simple tests for database models - only testing functions that actually exist.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import date, datetime
import time

from virtualmanweek.db import models


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.sqlite3', delete=False) as tmp:
        temp_path = Path(tmp.name)
    
    # Set the override to use our temp database
    models.set_db_path(temp_path)
    models.initialize()
    
    yield temp_path
    
    # Cleanup
    models.set_db_path(None)
    try:
        temp_path.unlink(missing_ok=True)
    except PermissionError:
        pass  # Ignore cleanup errors


class TestBasicOperations:
    """Test basic database operations that actually exist"""
    
    def test_database_initialization(self, temp_db):
        """Test that database initializes properly"""
        conn = models.connect()
        cursor = conn.cursor()
        
        # Check that basic tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        expected_tables = ['meta', 'projects', 'modes', 'weeks', 'time_entries']
        for table in expected_tables:
            assert table in tables
        
        conn.close()
    
    def test_upsert_project(self, temp_db):
        """Test project creation with upsert_project"""
        project_id = models.upsert_project("TEST", "Test Project")
        assert project_id is not None
        
        # Verify project was created
        projects = models.list_projects()
        project_names = [p['name'] for p in projects]
        assert "Test Project" in project_names
    
    def test_list_projects(self, temp_db):
        """Test listing projects"""
        models.upsert_project("PROJ1", "Project One")
        models.upsert_project("PROJ2", "Project Two")
        
        projects = models.list_projects()
        assert len(projects) >= 2
        
        codes = [p['code'] for p in projects]
        assert "PROJ1" in codes
        assert "PROJ2" in codes
    
    def test_upsert_mode(self, temp_db):
        """Test mode creation"""
        models.upsert_mode("Development")
        
        conn = models.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT label, usage_count FROM modes WHERE label_lower = ?", ("development",))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "Development"
        assert row[1] == 1
        conn.close()
    
    def test_upsert_mode_increments_count(self, temp_db):
        """Test that using existing mode increments usage count"""
        models.upsert_mode("Testing")
        models.upsert_mode("Testing")  # Use again
        
        conn = models.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT usage_count FROM modes WHERE label_lower = ?", ("testing",))
        row = cursor.fetchone()
        assert row[0] == 2
        conn.close()
    
    def test_tag_cloud(self, temp_db):
        """Test tag cloud functionality"""
        models.upsert_mode("Development")
        models.upsert_mode("Testing")
        models.upsert_mode("Meeting")
        
        tags = models.tag_cloud(limit=5)
        assert len(tags) >= 3
        assert any(tag['label'] == "Development" for tag in tags)
    
    def test_ensure_week(self, temp_db):
        """Test week creation"""
        test_date = date(2024, 3, 15)  # A Friday
        week_id = models.ensure_week(test_date)
        assert week_id is not None
        
        # Verify week was created
        conn = models.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT iso_year, iso_week FROM weeks WHERE id = ?", (week_id,))
        row = cursor.fetchone()
        assert row is not None
        conn.close()
    
    def test_insert_time_entry(self, temp_db):
        """Test time entry insertion"""
        # Setup prerequisites
        project_id = models.upsert_project("TEST", "Test Project")
        models.upsert_mode("Development")
        week_id = models.ensure_week(date.today())
        
        start_ts = int(time.time())
        end_ts = start_ts + 3600  # 1 hour later
        
        entry_id = models.insert_time_entry(
            week_id=week_id,
            date_=date.today(),
            start_ts=start_ts,
            end_ts=end_ts,
            active_seconds=3000,  # 50 minutes active
            idle_seconds=600,     # 10 minutes idle
            project_id=project_id,
            mode_label="Development",
            source="auto"
        )
        
        assert entry_id is not None
        
        # Verify entry was created
        conn = models.connect()
        cursor = conn.cursor()
        cursor.execute("SELECT project_id, mode_label FROM time_entries WHERE id = ?", (entry_id,))
        row = cursor.fetchone()
        assert row[0] == project_id
        assert row[1] == "Development"
        conn.close()
