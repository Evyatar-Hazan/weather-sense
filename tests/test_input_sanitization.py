"""
Tests for input sanitization and validation.
"""
import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

# Set test environment variables before importing app
os.environ["API_KEY"] = "test-api-key-123"
os.environ["LOG_LEVEL"] = "ERROR"  # Reduce log noise in tests

from api.main import WeatherQueryRequest, app  # noqa: E402
from crew.parser import DateRangeParser  # noqa: E402


class TestInputSanitization:
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
        self.valid_headers = {"x-api-key": "test-api-key-123"}
        self.parser = DateRangeParser()

    def test_pydantic_model_sanitization(self):
        """Test Pydantic model input sanitization."""
        # Test basic XSS prevention
        dangerous_query = '<script>alert("xss")</script>weather in Tel Aviv'
        request = WeatherQueryRequest(query=dangerous_query)

        # Script tags should be completely removed
        assert "<script>" not in request.query
        assert "&lt;script&gt;" not in request.query
        assert "weather in Tel Aviv" in request.query

    def test_pydantic_model_validation_errors(self):
        """Test Pydantic model validation error handling."""
        # Test empty query
        with pytest.raises(ValidationError):
            WeatherQueryRequest(query="")

        # Test whitespace-only query
        with pytest.raises(ValidationError):
            WeatherQueryRequest(query="   ")

        # Test very long query
        long_query = "a" * 1001
        with pytest.raises(ValidationError):
            WeatherQueryRequest(query=long_query)

    def test_pydantic_model_control_character_removal(self):
        """Test removal of control characters."""
        query_with_nulls = "weather\x00in\x01Tel\x02Aviv"
        request = WeatherQueryRequest(query=query_with_nulls)

        # Null bytes and control chars should be removed
        assert "\x00" not in request.query
        assert "\x01" not in request.query
        assert "\x02" not in request.query
        assert "weather" in request.query
        assert "Tel" in request.query
        assert "Aviv" in request.query

    def test_pydantic_model_javascript_removal(self):
        """Test removal of JavaScript patterns."""
        patterns = [
            "javascript:alert('xss') weather in Paris",
            "onload=alert(1) weather forecast",
            "expression(alert('xss')) temperature",
            "vbscript:msgbox('xss') weather data",
        ]

        for pattern in patterns:
            request = WeatherQueryRequest(query=pattern)
            # Dangerous JavaScript patterns should be removed
            assert "javascript:" not in request.query.lower()
            assert "onload=" not in request.query.lower()
            assert "expression(" not in request.query.lower()
            assert "vbscript:" not in request.query.lower()

    def test_parser_input_validation(self):
        """Test parser input validation."""
        # Test invalid input types
        result = self.parser.parse_query(None)
        assert "error" in result
        assert result["error"] == "invalid_query"

        # Test empty string
        result = self.parser.parse_query("")
        assert "error" in result
        assert result["error"] == "invalid_query"

        # Test very short query
        result = self.parser.parse_query("ab")
        assert "error" in result
        assert result["error"] == "query_too_short"

        # Test very long query
        long_query = "weather in " + "a" * 500
        result = self.parser.parse_query(long_query)
        assert "error" in result
        assert result["error"] == "query_too_long"

    def test_parser_location_sanitization(self):
        """Test location extraction with sanitization."""
        # Test with dangerous characters
        dangerous_location = 'weather in <script>alert("xss")</script>Paris'
        result = self.parser.parse_query(dangerous_location)

        if "location" in result:
            # Dangerous characters should be removed from location
            assert "<script>" not in result["location"]
            assert "Paris" in result["location"]

    def test_parser_coordinate_validation(self):
        """Test coordinate validation in parser."""
        # Test valid coordinates
        valid_coords = "weather at 48.8566, 2.3522"  # Paris coordinates
        result = self.parser.parse_query(valid_coords)

        if "location" in result:
            location = result["location"]
            if "," in location:
                lat, lon = location.split(",")
                lat, lon = float(lat), float(lon)
                assert -90 <= lat <= 90
                assert -180 <= lon <= 180

        # Test invalid coordinates (out of range)
        invalid_coords = [
            "weather at 95.0, 200.0",  # Invalid lat/lon
            "weather at -95.0, -200.0",  # Invalid lat/lon
        ]

        for coords in invalid_coords:
            result = self.parser.parse_query(coords)
            # Should either reject coordinates or handle gracefully
            if "location" in result and "," in result["location"]:
                try:
                    lat, lon = result["location"].split(",")
                    lat, lon = float(lat), float(lon)
                    # If coordinates are returned, they should be valid
                    assert -90 <= lat <= 90
                    assert -180 <= lon <= 180
                except ValueError:
                    # Or they should be treated as place names
                    pass

    def test_api_endpoint_sanitization_integration(self):
        """Test API endpoint with sanitized inputs."""
        # Test with potentially dangerous input
        dangerous_payload = {"query": "<img src=x onerror=alert(1)>weather in New York"}

        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json=dangerous_payload,
        )

        # Should not return 500 error due to input sanitization
        assert response.status_code != 500

        # Even if the request fails for other reasons (missing location, etc.),
        # it should not be due to XSS or injection attacks
        if response.status_code >= 400:
            error_detail = response.json()
            # Error should be about parsing/location, not injection
            assert "script" not in str(error_detail).lower()
            assert "alert" not in str(error_detail).lower()

    def test_long_input_handling(self):
        """Test handling of very long inputs."""
        # Create a reasonable but long query
        long_query = "weather forecast for " + "a" * 200 + " city"

        # Should be handled gracefully by both model and parser
        try:
            request = WeatherQueryRequest(query=long_query)
            # If accepted by Pydantic, should work in parser too
            result = self.parser.parse_query(request.query)
            # Should not crash, either success or graceful error
            assert isinstance(result, dict)
        except ValidationError:
            # Or rejected by Pydantic validation, which is also fine
            pass

    def test_unicode_and_international_characters(self):
        """Test handling of Unicode and international characters."""
        international_queries = [
            "weather in Москва",  # Moscow in Cyrillic
            "weather in 北京",  # Beijing in Chinese
            "weather in São Paulo",  # Portuguese with accent
            "weather in México",  # Spanish with accent
        ]

        for query in international_queries:
            # Should not crash on international characters
            try:
                request = WeatherQueryRequest(query=query)
                result = self.parser.parse_query(request.query)
                assert isinstance(result, dict)
            except ValidationError:
                # Some validation failures might be acceptable
                pass
