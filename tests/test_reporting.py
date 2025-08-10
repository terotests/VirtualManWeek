import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from virtualmanweek.reporting.charts import (
    compute_scale_unit,
    _fmt_time_short,
    _fmt_dt
)


class TestScaleUnit:
    def test_compute_scale_unit_seconds(self):
        """Test scale unit computation for small durations"""
        scale, unit = compute_scale_unit(500)  # 8 minutes 20 seconds
        assert scale == 1.0
        assert unit == "Seconds"

    def test_compute_scale_unit_minutes(self):
        """Test scale unit computation for medium durations"""
        scale, unit = compute_scale_unit(1800)  # 30 minutes
        assert scale == 60.0
        assert unit == "Minutes"

    def test_compute_scale_unit_hours(self):
        """Test scale unit computation for large durations"""
        scale, unit = compute_scale_unit(7200)  # 2 hours
        assert scale == 3600.0
        assert unit == "Hours"

    def test_compute_scale_unit_boundary_cases(self):
        """Test boundary cases for scale unit computation"""
        # Just under 10 minutes
        scale, unit = compute_scale_unit(599)
        assert scale == 1.0
        assert unit == "Seconds"
        
        # Exactly 10 minutes
        scale, unit = compute_scale_unit(600)
        assert scale == 60.0
        assert unit == "Minutes"
        
        # Just under 1 hour
        scale, unit = compute_scale_unit(3599)
        assert scale == 60.0
        assert unit == "Minutes"
        
        # Exactly 1 hour
        scale, unit = compute_scale_unit(3600)
        assert scale == 3600.0
        assert unit == "Hours"


class TestTimeFormatting:
    def test_fmt_time_short_seconds_only(self):
        """Test formatting seconds-only durations"""
        assert _fmt_time_short(0) == "0s"
        assert _fmt_time_short(30) == "30s"
        assert _fmt_time_short(59) == "59s"

    def test_fmt_time_short_minutes_only(self):
        """Test formatting minute-only durations"""
        assert _fmt_time_short(60) == "1min"
        assert _fmt_time_short(120) == "2min"
        assert _fmt_time_short(1800) == "30min"

    def test_fmt_time_short_minutes_and_seconds(self):
        """Test formatting minutes with seconds"""
        assert _fmt_time_short(65) == "1min 5s"
        assert _fmt_time_short(125) == "2min 5s"
        assert _fmt_time_short(1835) == "30min 35s"

    def test_fmt_time_short_hours_only(self):
        """Test formatting hour-only durations"""
        assert _fmt_time_short(3600) == "1h"
        assert _fmt_time_short(7200) == "2h"
        assert _fmt_time_short(18000) == "5h"

    def test_fmt_time_short_hours_and_minutes(self):
        """Test formatting hours with minutes"""
        assert _fmt_time_short(3660) == "1h 1min"
        assert _fmt_time_short(3900) == "1h 5min"
        assert _fmt_time_short(7800) == "2h 10min"

    def test_fmt_time_short_complex_durations(self):
        """Test formatting complex durations (seconds are ignored when hours present)"""
        # 1 hour, 5 minutes, 30 seconds -> shows as "1h 5min" (seconds ignored)
        assert _fmt_time_short(3930) == "1h 5min"
        # 2 hours, 0 minutes, 45 seconds -> shows as "2h" (minutes and seconds ignored)
        assert _fmt_time_short(7245) == "2h"


class TestDateTimeFormatting:
    def test_fmt_dt_valid_timestamp(self):
        """Test formatting valid timestamps"""
        # January 1, 2024, 12:00:00 UTC
        timestamp = int(datetime(2024, 1, 1, 12, 0, 0).timestamp())
        result = _fmt_dt(timestamp)
        
        # Should return a formatted date string
        assert "2024-01-01" in result
        assert "12:00:00" in result

    def test_fmt_dt_invalid_timestamp(self):
        """Test formatting invalid timestamps"""
        # Very large timestamp that would cause an error
        invalid_timestamp = 99999999999999
        result = _fmt_dt(invalid_timestamp)
        
        # Should return string representation when formatting fails
        assert result == str(invalid_timestamp)

    def test_fmt_dt_zero_timestamp(self):
        """Test formatting zero timestamp"""
        result = _fmt_dt(0)
        
        # Should handle epoch time (1970-01-01)
        assert "1970-01-01" in result

    def test_fmt_dt_negative_timestamp(self):
        """Test formatting negative timestamp"""
        result = _fmt_dt(-1)
        
        # Should either format correctly or fallback to string
        assert isinstance(result, str)


class TestReportingIntegration:
    """Integration tests for reporting functionality"""
    
    @patch('virtualmanweek.db.models.connect')
    def test_data_aggregation_mock(self, mock_connect):
        """Test data aggregation with mocked database"""
        # This would test the actual chart generation functions
        # when they're implemented. For now, just verify the helper functions work.
        
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [
            ('Development', 7200),  # 2 hours
            ('Meeting', 3600),      # 1 hour
            ('Testing', 1800)       # 30 minutes
        ]
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_conn
        
        # Test that our formatting functions would work with this data
        total_seconds = sum(row[1] for row in mock_cursor.fetchall.return_value)
        assert total_seconds == 12600  # 3.5 hours
        
        scale, unit = compute_scale_unit(total_seconds)
        assert scale == 3600.0
        assert unit == "Hours"

    def test_time_formatting_consistency(self):
        """Test that time formatting is consistent across different scales"""
        test_durations = [
            30,     # 30 seconds
            90,     # 1 minute 30 seconds
            3600,   # 1 hour
            3690,   # 1 hour 1 minute 30 seconds
            7200,   # 2 hours
            86400,  # 24 hours
        ]
        
        for duration in test_durations:
            formatted = _fmt_time_short(duration)
            
            # All should be strings
            assert isinstance(formatted, str)
            # Should not be empty
            assert len(formatted) > 0
            # Should contain reasonable time units
            assert any(unit in formatted for unit in ['s', 'min', 'h'])

    def test_scale_unit_and_formatting_alignment(self):
        """Test that scale units align with formatting expectations"""
        # Test various durations and ensure scale unit choice makes sense
        test_cases = [
            (30, "Seconds", "30s"),
            (300, "Seconds", "5min"),
            (1800, "Minutes", "30min"),
            (3600, "Hours", "1h"),
            (7200, "Hours", "2h")
        ]
        
        for duration, expected_unit, expected_format in test_cases:
            scale, unit = compute_scale_unit(duration)
            formatted = _fmt_time_short(duration)
            
            assert unit == expected_unit
            assert formatted == expected_format


class TestErrorHandling:
    def test_fmt_time_short_negative_input(self):
        """Test time formatting with negative input"""
        # Should handle gracefully or return expected format
        result = _fmt_time_short(-30)
        assert isinstance(result, str)

    def test_compute_scale_unit_zero_input(self):
        """Test scale unit computation with zero input"""
        scale, unit = compute_scale_unit(0)
        assert scale == 1.0
        assert unit == "Seconds"

    def test_compute_scale_unit_negative_input(self):
        """Test scale unit computation with negative input"""
        scale, unit = compute_scale_unit(-100)
        assert isinstance(scale, float)
        assert isinstance(unit, str)

    def test_fmt_dt_string_input(self):
        """Test datetime formatting with string input"""
        # Should handle non-numeric input gracefully
        result = _fmt_dt("not_a_timestamp")
        assert result == "not_a_timestamp"


class TestPerformance:
    def test_time_formatting_performance(self):
        """Test that time formatting functions perform reasonably"""
        import time
        
        # Test with a reasonable number of iterations
        durations = [i * 100 for i in range(1000)]  # 0 to 99,900 seconds
        
        start_time = time.time()
        for duration in durations:
            _fmt_time_short(duration)
        end_time = time.time()
        
        # Should complete in reasonable time (less than 1 second for 1000 iterations)
        assert end_time - start_time < 1.0

    def test_scale_unit_performance(self):
        """Test that scale unit computation performs reasonably"""
        import time
        
        durations = [i * 100 for i in range(1000)]
        
        start_time = time.time()
        for duration in durations:
            compute_scale_unit(duration)
        end_time = time.time()
        
        # Should complete very quickly
        assert end_time - start_time < 0.1
