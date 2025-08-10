import pytest
import tempfile
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture(scope="session")
def temp_test_dir():
    """Create a temporary directory for all tests in the session"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_appdata(temp_test_dir, monkeypatch):
    """Mock the appdata directory to use a temporary location"""
    test_appdata = temp_test_dir / "appdata"
    test_appdata.mkdir(exist_ok=True)
    
    def mock_appdata_root():
        return test_appdata
    
    monkeypatch.setattr("virtualmanweek.config.appdata_root", mock_appdata_root)
    return test_appdata


@pytest.fixture(autouse=True)
def reset_db_override():
    """Automatically reset database path override after each test"""
    yield
    
    # Import here to avoid circular imports
    try:
        from virtualmanweek.db import models
        models.set_db_path(None)
    except ImportError:
        pass


@pytest.fixture
def sample_time_entries():
    """Sample time entries for testing"""
    from datetime import datetime, timedelta
    
    base_time = int(datetime(2024, 1, 1, 9, 0).timestamp())
    
    return [
        {
            'date': '2024-01-01',
            'start_ts': base_time,
            'end_ts': base_time + 3600,
            'active_seconds': 3000,
            'idle_seconds': 600,
            'project_id': 1,
            'mode_label': 'Development',
            'source': 'auto'
        },
        {
            'date': '2024-01-01',
            'start_ts': base_time + 3600,
            'end_ts': base_time + 5400,
            'active_seconds': 1500,
            'idle_seconds': 300,
            'project_id': 1,
            'mode_label': 'Meeting',
            'source': 'auto'
        },
        {
            'date': '2024-01-01',
            'start_ts': base_time + 5400,
            'end_ts': base_time + 7200,
            'active_seconds': 1800,
            'idle_seconds': 0,
            'project_id': 2,
            'mode_label': 'Testing',
            'source': 'manual'
        }
    ]
