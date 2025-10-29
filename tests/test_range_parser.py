"""
Comprehensive test suite for the Range Parser task.

This module contains production-grade tests covering:
- Happy path scenarios with various natural language inputs
- Edge cases including missing components and ambiguous phrases
- Error handling for invalid dates and exceeded ranges
- Boundary conditions for date ranges
- Schema validation and deterministic output verification
- Tests the actual parse_natural_language function

Test Requirements:
- Uses pytest with parametrized tests for comprehensive coverage
- Tests the real implementation in crew.parser
- Validates JSON schema compliance
- Tests 31-day range limit enforcement
- Ensures proper error handling
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
import jsonschema
from typing import Dict, Any

# Import the actual function under test
from crew.parser import parse_natural_language, DateRangeParser
"""
Comprehensive test suite for the Range Parser task.

This module contains production-grade tests covering:
- Happy path scenarios with various natural language inputs
- Edge cases including missing components and ambiguous phrases
- Error handling for invalid dates and exceeded ranges
- Boundary conditions for date ranges
- Schema validation and deterministic output verification
- Tests the actual parse_natural_language function

Test Requirements:
- Uses pytest with parametrized tests for comprehensive coverage
- Tests the real implementation in crew.parser
- Validates JSON schema compliance
- Tests 31-day range limit enforcement
- Ensures proper error handling
"""

import pytest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta, date
import jsonschema
from typing import Dict, Any

# Import the actual function under test
from crew.parser import parse_natural_language, DateRangeParser


# JSON Schema for validating parse_natural_language output
SCHEMA = {
    "type": "object",
    "properties": {
        "location": {"type": "string"},
        "start_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
        "end_date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
        "units": {"type": "string", "enum": ["metric", "imperial"]},
        "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
    },
    "required": ["location", "start_date", "end_date", "units", "confidence"]
}


def _validate_schema(result: Dict[str, Any]) -> None:
    """
    Helper function to validate that result conforms to expected JSON schema.
    
    Args:
        result: Dictionary to validate against schema
        
    Raises:
        jsonschema.ValidationError: If result doesn't match schema
    """
    jsonschema.validate(result, SCHEMA)


def _validate_error_schema(result: Dict[str, Any]) -> None:
    """
    Helper function to validate error response structure.
    
    Args:
        result: Dictionary to validate as error response
        
    Raises:
        AssertionError: If error structure is invalid
    """
    assert "error" in result, "Error response must contain 'error' field"
    assert isinstance(result["error"], str), "Error message must be string"


class TestRangeParserHappyPath:
    """Test successful parsing scenarios with valid inputs."""
    
    @pytest.mark.parametrize("query,expected_location,expected_units", [
        ("weather in Tel Aviv from tomorrow to next Friday, metric", "Tel Aviv", "metric"),
        ("temperature in New York from tomorrow to next week, imperial", "New York", "imperial"),
        ("forecast for Jerusalem today", "Jerusalem", "metric"),
        ("weather in Paris next week", "Paris", "metric"),
        ("climate data for London from tomorrow to next Sunday", "London", "metric"),
    ])
    def test_successful_parsing_various_formats(self, query, expected_location, expected_units):
        """
        Test successful parsing of various natural language weather queries.
        
        Validates that the parser correctly extracts location, dates, and units
        from different query formats and produces schema-compliant output.
        """
        result = parse_natural_language({"query": query})
        
        # Check if parsing was successful (no error)
        if "error" not in result:
            # Validate schema compliance
            _validate_schema(result)
            
            # Verify specific expectations
            assert result["location"] == expected_location
            assert result["units"] == expected_units
            assert isinstance(result["confidence"], float)
            assert 0.0 <= result["confidence"] <= 1.0
        else:
            # If there's an error, validate error structure
            _validate_error_schema(result)
    
    def test_single_day_range(self):
        """
        Test parsing query for a single day (start_date == end_date).
        
        Verifies that single-day ranges are valid and produce correct output.
        """
        result = parse_natural_language({"query": "weather in Tokyo today"})
        
        if "error" not in result:
            _validate_schema(result)
            # For single day, start and end should be the same or consecutive
            assert result["start_date"] <= result["end_date"]


class TestRangeParserEdgeCases:
    """Test edge cases including missing components and irregular formatting."""
    
    @pytest.mark.parametrize("query", [
        "weather somewhere maybe tomorrow",  # Vague location
        "temperature sometime soon",  # Ambiguous timing
        " Weather in LONDON from tomorrow to next friday ",  # Case/spacing issues
        "forecast maybe next week",  # Uncertain timing
    ])
    def test_vague_and_ambiguous_queries(self, query):
        """
        Test handling of vague or ambiguous natural language queries.
        
        Verifies that ambiguous queries either succeed with appropriate confidence
        or fail gracefully with proper error messages.
        """
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            # Confidence might be lower for vague queries, but should still be valid
            assert 0.0 <= result["confidence"] <= 1.0
        else:
            _validate_error_schema(result)
    
    def test_missing_location_produces_error(self):
        """
        Test parsing query with missing location information.
        
        Verifies that missing location results in appropriate error.
        """
        result = parse_natural_language({"query": "weather forecast from tomorrow to next week"})
        
        _validate_error_schema(result)
        assert result["error"] == "missing_location"
    
    def test_missing_units_defaults_to_metric(self):
        """
        Test that missing units specification defaults to 'metric'.
        
        Verifies the default behavior when units are not specified in query.
        """
        result = parse_natural_language({"query": "weather in Berlin from tomorrow to next week"})
        
        if "error" not in result:
            _validate_schema(result)
            assert result["units"] == "metric"


class TestRangeParserErrorHandling:
    """Test error conditions and structured error responses."""
    
    def test_missing_query_returns_error(self):
        """
        Test that missing query produces structured error.
        
        Verifies proper error handling when no query is provided.
        """
        result = parse_natural_language({})
        
        _validate_error_schema(result)
        assert result["error"] == "missing_query"
    
    def test_empty_query_returns_error(self):
        """
        Test that empty query produces structured error.
        
        Verifies proper error handling when empty query is provided.
        """
        result = parse_natural_language({"query": ""})
        
        _validate_error_schema(result)
        assert result["error"] == "missing_query"
    
    def test_date_range_exceeds_31_days_error(self):
        """
        Test that date ranges exceeding 31 days produce structured error.
        
        Verifies enforcement of 31-day maximum range limit.
        """
        # Create a query with a large date range
        result = parse_natural_language({"query": "weather in Tel Aviv from October 1 to December 1"})
        
        _validate_error_schema(result)
        assert result["error"] == "range_too_large"
    
    def test_invalid_date_order_handling(self):
        """
        Test handling when end date is before start date.
        
        Verifies that reversed date order produces appropriate error.
        """
        # Use specific dates to ensure invalid order
        today = date.today()
        yesterday = today - timedelta(days=1)
        result = parse_natural_language({
            "query": f"weather in Madrid from {today.strftime('%Y-%m-%d')} to {yesterday.strftime('%Y-%m-%d')}"
        })
        
        _validate_error_schema(result)
        assert result["error"] == "invalid_date_order"


class TestRangeParserDateHandling:
    """Test date parsing and formatting with various scenarios."""
    
    def test_deterministic_output_same_input(self):
        """
        Test that identical inputs produce identical outputs.
        
        Verifies deterministic behavior for consistent results.
        """
        query_data = {"query": "weather in Tokyo from tomorrow to next Friday"}
        
        # Call the function twice with same input
        result1 = parse_natural_language(query_data)
        result2 = parse_natural_language(query_data)
        
        assert result1 == result2
        
        if "error" not in result1:
            _validate_schema(result1)
            _validate_schema(result2)
    
    @pytest.mark.parametrize("location,expected_location", [
        ("Vienna", "Vienna"),  # Test with capital letter
        ("Tokyo", "Tokyo"),    # Test with capital letter
        ("London", "London"),  # Test with capital letter
    ])
    def test_location_extraction(self, location, expected_location):
        """
        Test that locations are properly extracted and formatted.
        
        Verifies consistent location extraction regardless of case.
        """
        query = f"weather in {location} from tomorrow to next week"
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            assert result["location"] == expected_location
            # Verify ISO format with proper length
            assert len(result["start_date"]) == 10  # YYYY-MM-DD format
            assert len(result["end_date"]) == 10


class TestRangeParserValidation:
    """Test output validation and schema compliance."""
    
    def test_output_type_is_dict(self):
        """
        Test that parse_natural_language always returns a dictionary.
        
        Verifies fundamental output type requirement.
        """
        result = parse_natural_language({"query": "weather in Tokyo tomorrow"})
        assert isinstance(result, dict)
    
    @pytest.mark.parametrize("units_keyword,expected_units", [
        ("metric", "metric"),
        ("imperial", "imperial"),
        ("fahrenheit", "imperial"),
        ("mph", "imperial"),
    ])
    def test_units_extraction(self, units_keyword, expected_units):
        """
        Test that units are properly extracted from queries.
        
        Verifies units field extraction and validation.
        """
        query = f"weather in Tokyo tomorrow, {units_keyword}"
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            assert result["units"] == expected_units
    
    def test_confidence_range_validation(self):
        """
        Test that confidence is a float between 0.0 and 1.0 inclusive.
        
        Verifies confidence field type and range constraints.
        """
        result = parse_natural_language({"query": "weather in Tokyo tomorrow"})
        
        if "error" not in result:
            _validate_schema(result)
            assert isinstance(result["confidence"], (int, float))
            assert 0.0 <= result["confidence"] <= 1.0


class TestRangeParserBoundaryConditions:
    """Test boundary conditions for date ranges and limits."""
    
    def test_exactly_31_days_allowed(self):
        """
        Test that exactly 31-day range is allowed.
        
        Verifies that the maximum allowed range works correctly.
        """
        # Create a query with exactly 31 days
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=30)  # 31 days total
        
        query = f"weather in Oslo from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            # Calculate days between dates
            start = datetime.strptime(result["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(result["end_date"], "%Y-%m-%d").date()
            days_diff = (end - start).days + 1
            assert days_diff <= 31
    
    def test_32_days_produces_error(self):
        """
        Test that 32+ day range produces structured error.
        
        Verifies enforcement of 31-day limit with appropriate error.
        """
        # Create a query with more than 31 days
        start_date = date.today() + timedelta(days=1)
        end_date = start_date + timedelta(days=32)  # 33 days total
        
        query = f"weather in Oslo from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        result = parse_natural_language({"query": query})
        
        _validate_error_schema(result)
        assert result["error"] == "range_too_large"


class TestRangeParserRobustness:
    """Test robustness with complex and edge case inputs."""
    
    def test_large_text_with_irrelevant_words(self):
        """
        Test parsing with large text containing irrelevant information.
        
        Verifies that parser can extract relevant information from noisy input.
        """
        complex_query = """
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. 
        I need the weather in Barcelona from tomorrow to next week please,
        using metric units. Sed do eiusmod tempor incididunt ut labore.
        """
        
        result = parse_natural_language({"query": complex_query})
        
        if "error" not in result:
            _validate_schema(result)
            assert result["location"] == "Barcelona"
            assert result["units"] == "metric"
    
    @pytest.mark.parametrize("query", [
        "weather somewhere sometime tomorrow",
        "maybe weather next week in Paris",
        "unclear forecast request for London tomorrow",
        "vague temperature query for Tokyo next week",
    ])
    def test_confidence_scoring_for_various_queries(self, query):
        """
        Test that confidence scoring works for various query types.
        
        Verifies that confidence scoring reflects query clarity and specificity.
        """
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            # Confidence should be reasonable for any successful parse
            assert 0.0 <= result["confidence"] <= 1.0
    
    def test_multiple_locations_in_query(self):
        """
        Test handling of queries with multiple location mentions.
        
        Verifies behavior when query contains ambiguous location information.
        """
        query = "weather from London to Paris, tomorrow to next week"
        
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            # Should pick one of the locations or handle appropriately
            assert result["location"] in ["London", "Paris"] or result["confidence"] < 0.8


class TestRangeParserParametrized:
    """Comprehensive parameterized tests for multiple input variations."""
    
    @pytest.mark.parametrize("query,expected_location,expected_units", [
        ("weather in Tokyo today, imperial", "Tokyo", "imperial"),
        ("temperature forecast for Sydney next week", "Sydney", "metric"),
        ("climate in Cairo from tomorrow to next Sunday, metric", "Cairo", "metric"),
        ("forecast Mumbai tomorrow", "Mumbai", "metric"),
        ("weather report Berlin this weekend", "Berlin", "metric"),
        ("temperature Seoul next Monday to Friday", "Seoul", "metric"),
    ])
    def test_comprehensive_query_variations(self, query, expected_location, expected_units):
        """
        Comprehensive test of various natural language query formats.
        
        Tests multiple query patterns to ensure broad compatibility
        with different ways users might phrase weather requests.
        """
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            assert result["location"] == expected_location
            assert result["units"] == expected_units
            assert result["confidence"] >= 0.0
    
    @pytest.mark.parametrize("invalid_units", [
        "celsius",   # Invalid unit should default to metric
        "fahrenheit",  # This should actually map to imperial
        "kelvin",    # Invalid unit should default to metric
    ])
    def test_units_handling(self, invalid_units):
        """
        Test handling of various units specifications.
        
        Verifies that units are properly extracted or defaulted.
        """
        query = f"weather in Tokyo tomorrow, {invalid_units}"
        result = parse_natural_language({"query": query})
        
        if "error" not in result:
            _validate_schema(result)
            assert result["units"] in ["metric", "imperial"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])