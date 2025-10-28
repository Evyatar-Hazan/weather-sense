"""
Unit tests for natural language date range parser.
"""
import pytest
from datetime import date, timedelta
from crew.parser import DateRangeParser, parse_natural_language


class TestDateRangeParser:
    def setup_method(self):
        """Setup test fixtures."""
        self.parser = DateRangeParser()
        # Mock today for consistent testing
        self.parser.today = date(2025, 10, 28)  # Tuesday
    
    def test_extract_units_metric_default(self):
        """Test that metric is the default unit."""
        result = self.parser._extract_units("weather in tel aviv")
        assert result == "metric"
    
    def test_extract_units_imperial(self):
        """Test imperial unit detection."""
        test_cases = [
            "weather in tel aviv imperial",
            "tel aviv fahrenheit",
            "temperature in mph"
        ]
        for query in test_cases:
            result = self.parser._extract_units(query)
            assert result == "imperial"
    
    def test_extract_location_basic(self):
        """Test basic location extraction."""
        test_cases = [
            ("weather in Tel Aviv", "Tel Aviv"),
            ("Tel Aviv weather", "Tel Aviv"),
            ("from monday to friday in New York", "New York"),
            ("between Oct 10 and 15 in San Francisco", "San Francisco")
        ]
        
        for query, expected in test_cases:
            result = self.parser._extract_location(query)
            assert result == expected
    
    def test_extract_location_coordinates(self):
        """Test coordinate extraction."""
        test_cases = [
            ("weather at 32.08, 34.78", "32.08,34.78"),
            ("32.0,-74.0 weather", "32.0,-74.0"),
            ("-23.5, 46.6 from monday to friday", "-23.5,46.6")
        ]
        
        for query, expected in test_cases:
            result = self.parser._extract_location(query)
            assert result == expected
    
    def test_extract_location_none(self):
        """Test when no location is found."""
        test_cases = [
            "from monday to friday",
            "last week weather",
            "temperature data"
        ]
        
        for query in test_cases:
            result = self.parser._extract_location(query)
            assert result is None
    
    def test_get_last_week(self):
        """Test last week date range calculation."""
        # Tuesday Oct 28, 2025 -> last Monday Oct 13 to Sunday Oct 19
        start, end = self.parser._get_last_week()
        assert start == "2025-10-13"
        assert end == "2025-10-19"
    
    def test_get_this_week(self):
        """Test this week date range calculation."""
        # Tuesday Oct 28, 2025 -> Monday Oct 27 to Sunday Nov 2
        start, end = self.parser._get_this_week()
        assert start == "2025-10-27"
        assert end == "2025-11-02"
    
    def test_get_weekdays(self):
        """Test weekday range calculations."""
        # Last Monday to Friday
        start, end = self.parser._get_last_weekdays()
        assert start == "2025-10-13"
        assert end == "2025-10-17"
        
        # This Monday to Friday
        start, end = self.parser._get_this_weekdays()
        assert start == "2025-10-27"
        assert end == "2025-10-31"
    
    def test_parse_single_date_relative(self):
        """Test relative date parsing."""
        test_cases = [
            ("today", "2025-10-28"),
            ("yesterday", "2025-10-27"),
            ("tomorrow", "2025-10-29")
        ]
        
        for date_str, expected in test_cases:
            result = self.parser._parse_single_date(date_str)
            assert result == expected
    
    def test_parse_single_date_absolute(self):
        """Test absolute date parsing."""
        test_cases = [
            ("2025-10-15", "2025-10-15"),
            ("October 15, 2025", "2025-10-15"),
            ("10/15/2025", "2025-10-15")
        ]
        
        for date_str, expected in test_cases:
            result = self.parser._parse_single_date(date_str)
            assert result == expected
    
    def test_parse_query_success(self):
        """Test successful query parsing."""
        query = "weather in Tel Aviv from October 20 to October 24, metric"
        result = self.parser.parse_query(query)
        
        assert "error" not in result
        assert result["location"] == "Tel Aviv"
        assert result["start_date"] == "2025-10-20"
        assert result["end_date"] == "2025-10-24"
        assert result["units"] == "metric"
        assert result["confidence"] > 0
    
    def test_parse_query_missing_location(self):
        """Test query with missing location."""
        query = "from last monday to friday"
        result = self.parser.parse_query(query)
        
        assert "error" in result
        assert result["error"] == "missing_location"
    
    def test_parse_query_range_too_large(self):
        """Test query with date range too large."""
        query = "weather in Tel Aviv from October 1 to December 1"
        result = self.parser.parse_query(query)
        
        assert "error" in result
        assert result["error"] == "range_too_large"
    
    def test_parse_query_invalid_date_order(self):
        """Test query with end date before start date."""
        query = "weather in Tel Aviv from October 24 to October 20"
        result = self.parser.parse_query(query)
        
        assert "error" in result
        assert result["error"] == "invalid_date_order"


class TestParseNaturalLanguage:
    """Test the main parse_natural_language function."""
    
    def test_parse_natural_language_success(self):
        """Test successful parsing."""
        query_data = {"query": "weather in Tel Aviv from last Monday to Friday"}
        result = parse_natural_language(query_data)
        
        assert "error" not in result
        assert "location" in result
        assert "start_date" in result
        assert "end_date" in result
        assert "units" in result
        assert "confidence" in result
    
    def test_parse_natural_language_missing_query(self):
        """Test with missing query parameter."""
        query_data = {}
        result = parse_natural_language(query_data)
        
        assert "error" in result
        assert result["error"] == "missing_query"
    
    def test_parse_natural_language_empty_query(self):
        """Test with empty query."""
        query_data = {"query": ""}
        result = parse_natural_language(query_data)
        
        assert "error" in result
        assert result["error"] == "missing_query"


if __name__ == "__main__":
    pytest.main([__file__])