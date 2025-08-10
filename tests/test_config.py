import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from dataclasses import asdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virtualmanweek.config import (
    appdata_root, 
    settings_path, 
    Settings, 
    DEFAULT_SETTINGS,
    APP_NAME
)


class TestAppdataRoot:
    def test_appdata_root_uses_appdata_env(self):
        """Test that appdata_root uses APPDATA environment variable when available"""
        with patch.dict('os.environ', {'APPDATA': 'C:\\TestAppData'}):
            with patch('pathlib.Path.mkdir') as mock_mkdir:
                result = appdata_root()
                expected = Path('C:\\TestAppData') / APP_NAME
                assert result == expected
                mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_appdata_root_fallback_to_home(self):
        """Test that appdata_root falls back to home directory when APPDATA not set"""
        with patch.dict('os.environ', {}, clear=True):
            with patch('pathlib.Path.home') as mock_home:
                with patch('pathlib.Path.mkdir') as mock_mkdir:
                    mock_home.return_value = Path('/home/user')
                    result = appdata_root()
                    expected = Path('/home/user/AppData/Roaming') / APP_NAME
                    assert result == expected
                    mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    def test_settings_path(self):
        """Test that settings_path returns correct path"""
        with patch('virtualmanweek.config.appdata_root') as mock_appdata:
            mock_appdata.return_value = Path('/test/appdata')
            result = settings_path()
            assert result == Path('/test/appdata/settings.json')


class TestSettings:
    def test_settings_default_values(self):
        """Test that Settings class has correct default values"""
        settings = Settings()
        assert settings.idle_timeout_seconds == DEFAULT_SETTINGS["idle_timeout_seconds"]
        assert settings.tag_cloud_limit == DEFAULT_SETTINGS["tag_cloud_limit"]
        assert settings.discard_sub_10s_entries == DEFAULT_SETTINGS["discard_sub_10s_entries"]
        assert settings.language == DEFAULT_SETTINGS["language"]
        assert settings.database_path == DEFAULT_SETTINGS["database_path"]

    def test_settings_load_nonexistent_file(self):
        """Test loading settings when file doesn't exist returns defaults"""
        with patch('virtualmanweek.config.settings_path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = False
            mock_path.return_value = mock_file
            
            settings = Settings.load()
            
            # Should return default settings
            assert settings.idle_timeout_seconds == DEFAULT_SETTINGS["idle_timeout_seconds"]
            assert settings.tag_cloud_limit == DEFAULT_SETTINGS["tag_cloud_limit"]

    def test_settings_load_existing_file(self):
        """Test loading settings from existing file"""
        test_data = {
            "idle_timeout_seconds": 600,
            "tag_cloud_limit": 5,
            "language": "zh"
        }
        
        with patch('virtualmanweek.config.settings_path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = json.dumps(test_data)
            mock_path.return_value = mock_file
            
            settings = Settings.load()
            
            assert settings.idle_timeout_seconds == 600
            assert settings.tag_cloud_limit == 5
            assert settings.language == "zh"
            # Should keep defaults for missing values
            assert settings.discard_sub_10s_entries == DEFAULT_SETTINGS["discard_sub_10s_entries"]

    def test_settings_load_corrupted_file(self):
        """Test loading settings from corrupted JSON file falls back to defaults"""
        with patch('virtualmanweek.config.settings_path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = "invalid json"
            mock_path.return_value = mock_file
            
            settings = Settings.load()
            
            # Should return default settings on parse error
            assert settings.idle_timeout_seconds == DEFAULT_SETTINGS["idle_timeout_seconds"]

    def test_settings_save(self):
        """Test saving settings to file"""
        settings = Settings(idle_timeout_seconds=900, language="en")
        
        with patch('virtualmanweek.config.settings_path') as mock_path:
            mock_file = MagicMock()
            mock_open = MagicMock()
            mock_file.open.return_value.__enter__.return_value = mock_open
            mock_path.return_value = mock_file
            
            with patch('json.dump') as mock_dump:
                settings.save()
                
                mock_file.open.assert_called_once_with("w", encoding="utf-8")
                mock_dump.assert_called_once_with(asdict(settings), mock_open, indent=2)

    def test_settings_custom_values(self):
        """Test creating Settings with custom values"""
        settings = Settings(
            idle_timeout_seconds=1200,
            tag_cloud_limit=15,
            discard_sub_10s_entries=False,
            language="zh",
            database_path="/custom/path/db.sqlite"
        )
        
        assert settings.idle_timeout_seconds == 1200
        assert settings.tag_cloud_limit == 15
        assert settings.discard_sub_10s_entries is False
        assert settings.language == "zh"
        assert settings.database_path == "/custom/path/db.sqlite"

    def test_settings_load_partial_data(self):
        """Test loading settings with only some fields present merges with defaults"""
        partial_data = {"idle_timeout_seconds": 450}
        
        with patch('virtualmanweek.config.settings_path') as mock_path:
            mock_file = MagicMock()
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = json.dumps(partial_data)
            mock_path.return_value = mock_file
            
            settings = Settings.load()
            
            # Should use loaded value
            assert settings.idle_timeout_seconds == 450
            # Should use defaults for missing fields
            assert settings.tag_cloud_limit == DEFAULT_SETTINGS["tag_cloud_limit"]
            assert settings.language == DEFAULT_SETTINGS["language"]
