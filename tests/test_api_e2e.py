"""
End-to-end tests for FastAPI weather application.
"""
import pytest
import os
import json
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient

# Set test environment variables
os.environ["API_KEY"] = "test-api-key-123"
os.environ["LOG_LEVEL"] = "ERROR"  # Reduce log noise in tests

from api.main import app


class TestWeatherAPI:
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
        self.valid_headers = {"x-api-key": "test-api-key-123"}
    
    def test_health_check(self):
        """Test health check endpoint."""
        response = self.client.get("/healthz")
        
        assert response.status_code == 200
        assert response.json() == {"ok": True}
    
    def test_weather_ask_missing_auth(self):
        """Test weather endpoint without authentication."""
        response = self.client.post(
            "/v1/weather/ask",
            json={"query": "weather in Tel Aviv"}
        )
        
        assert response.status_code == 401
    
    def test_weather_ask_invalid_auth(self):
        """Test weather endpoint with invalid API key."""
        response = self.client.post(
            "/v1/weather/ask",
            headers={"x-api-key": "invalid-key"},
            json={"query": "weather in Tel Aviv"}
        )
        
        assert response.status_code == 401
    
    def test_weather_ask_missing_query(self):
        """Test weather endpoint with missing query."""
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={}
        )
        
        assert response.status_code == 422  # Pydantic validation error
    
    def test_weather_ask_empty_query(self):
        """Test weather endpoint with empty query."""
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": ""}
        )
        
        assert response.status_code == 400
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_success(self, mock_process_query):
        """Test successful weather query."""
        # Mock successful response
        mock_process_query.return_value = {
            "summary": "Weather in Tel Aviv was generally warm with dry conditions.",
            "params": {
                "location": "Tel Aviv, Israel",
                "start_date": "2025-10-20",
                "end_date": "2025-10-24",
                "units": "metric"
            },
            "data": {
                "daily": [
                    {"date": "2025-10-20", "tmin": 20.0, "tmax": 28.0, "precip_mm": 0.0, "wind_max_kph": 15.0, "code": 1}
                ],
                "source": "open-meteo"
            },
            "confidence": 0.87,
            "tool_used": "weather.get_range",
            "latency_ms": 1234
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv from last Monday to Friday"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "summary" in data
        assert "params" in data
        assert "data" in data
        assert "confidence" in data
        assert "tool_used" in data
        assert "latency_ms" in data
        assert "request_id" in data
        
        assert data["params"]["location"] == "Tel Aviv, Israel"
        assert data["tool_used"] == "weather.get_range"
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_missing_location_error(self, mock_process_query):
        """Test weather query with missing location error."""
        mock_process_query.return_value = {
            "error": "missing_location",
            "hint": "Please specify a location"
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather from monday to friday"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "missing_location"
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_range_too_large_error(self, mock_process_query):
        """Test weather query with range too large error."""
        mock_process_query.return_value = {
            "error": "range_too_large",
            "hint": "span must be <= 31 days"
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv from January to December"}
        )
        
        assert response.status_code == 400
        data = response.json()
        assert data["error"] == "range_too_large"
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_service_unavailable_error(self, mock_process_query):
        """Test weather query with service unavailable error."""
        mock_process_query.return_value = {
            "error": "mcp_timeout",
            "hint": "MCP tool timed out"
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv"}
        )
        
        assert response.status_code == 502
        data = response.json()
        assert data["error"] == "mcp_timeout"
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_rate_limited_error(self, mock_process_query):
        """Test weather query with rate limit error."""
        mock_process_query.return_value = {
            "error": "rate_limited",
            "hint": "Too many requests"
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv"}
        )
        
        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "rate_limited"
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_internal_error(self, mock_process_query):
        """Test weather query with internal error."""
        mock_process_query.return_value = {
            "error": "unknown_error",
            "hint": "Something went wrong"
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "unknown_error"
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_exception_handling(self, mock_process_query):
        """Test exception handling in weather endpoint."""
        # Mock exception
        mock_process_query.side_effect = Exception("Unexpected error")
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv"}
        )
        
        assert response.status_code == 500
        data = response.json()
        assert data["error"] == "internal_server_error"
    
    def test_weather_ask_query_validation(self):
        """Test query parameter validation."""
        # Test with whitespace-only query
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "   "}
        )
        
        assert response.status_code == 400
    
    @patch('api.main.process_weather_query')
    def test_weather_ask_response_timing(self, mock_process_query):
        """Test that response includes timing information."""
        mock_process_query.return_value = {
            "summary": "Test summary",
            "params": {"location": "Test", "start_date": "2025-10-20", "end_date": "2025-10-24", "units": "metric"},
            "data": {"daily": [], "source": "test"},
            "confidence": 0.5,
            "tool_used": "weather.get_range",
            "latency_ms": 100
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "test query"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have both request_id and latency_ms
        assert "request_id" in data
        assert "latency_ms" in data
        assert isinstance(data["latency_ms"], int)
        assert len(data["request_id"]) > 0


class TestWeatherAPIIntegration:
    """Integration tests that test the full flow without mocking."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
        self.valid_headers = {"x-api-key": "test-api-key-123"}
    
    @pytest.mark.integration
    @patch('mcp_weather.provider.WeatherProvider.geocode_location')
    @patch('mcp_weather.provider.WeatherProvider.fetch_weather_data')
    def test_full_integration_success(self, mock_fetch_weather, mock_geocode):
        """Test full integration with mocked external APIs."""
        # Mock geocoding
        mock_geocode.return_value = (32.08, 34.78, "Tel Aviv, Israel")
        
        # Mock weather data for a full week
        mock_fetch_weather.return_value = {
            "daily": [
                {"date": "2025-10-20", "tmin": 20.0, "tmax": 28.0, "precip_mm": 0.0, "wind_max_kph": 15.0, "code": 1},
                {"date": "2025-10-21", "tmin": 19.0, "tmax": 27.0, "precip_mm": 2.0, "wind_max_kph": 18.0, "code": 61},
                {"date": "2025-10-22", "tmin": 18.0, "tmax": 26.0, "precip_mm": 1.0, "wind_max_kph": 17.0, "code": 1},
                {"date": "2025-10-23", "tmin": 21.0, "tmax": 29.0, "precip_mm": 0.0, "wind_max_kph": 16.0, "code": 1},
                {"date": "2025-10-24", "tmin": 22.0, "tmax": 30.0, "precip_mm": 0.0, "wind_max_kph": 14.0, "code": 1},
                {"date": "2025-10-25", "tmin": 20.0, "tmax": 28.0, "precip_mm": 3.0, "wind_max_kph": 19.0, "code": 61},
                {"date": "2025-10-26", "tmin": 19.0, "tmax": 27.0, "precip_mm": 1.0, "wind_max_kph": 18.0, "code": 61}
            ],
            "source": "open-meteo"
        }
        
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv last week, metric"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify full response structure
        assert "summary" in data
        assert "params" in data
        assert "data" in data
        assert "confidence" in data
        assert "tool_used" in data
        assert "latency_ms" in data
        assert "request_id" in data
        
        # Verify data content
        assert data["params"]["location"] == "Tel Aviv, Israel"
        assert data["params"]["start_date"] == "2025-10-20"
        assert data["params"]["end_date"] == "2025-10-26"
        assert data["params"]["units"] == "metric"
        assert len(data["data"]["daily"]) == 7  # Full week
        assert data["tool_used"] == "weather.get_range"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])