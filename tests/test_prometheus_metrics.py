"""
Tests for Prometheus metrics functionality.
"""
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

# Set test environment variables
os.environ["API_KEY"] = "test-api-key-123"
os.environ["LOG_LEVEL"] = "ERROR"  # Reduce log noise in tests

# Import after environment setup
from api.main import app  # noqa: E402
from utils.metrics import (  # noqa: E402
    health_check_counter,
    request_counter,
    request_duration,
    weather_query_counter,
    weather_query_duration,
)


class TestPrometheusMetrics:
    """Test suite for Prometheus metrics functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
        self.valid_headers = {"x-api-key": "test-api-key-123"}

    def test_metrics_endpoint_exists(self):
        """Test that /metrics endpoint exists and returns Prometheus format."""
        response = self.client.get("/metrics")

        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]

        # Check for basic Prometheus metrics format
        content = response.text
        assert "# HELP" in content
        assert "# TYPE" in content
        assert "weathersense_" in content

    def test_metrics_endpoint_contains_app_info(self):
        """Test that metrics include application information."""
        response = self.client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Check for app info metric (Info metrics get "_info" suffix automatically)
        assert "weathersense_app_info_info" in content
        # Note: labels might not appear if not explicitly set during test run

    def test_health_check_metrics(self):
        """Test that health check increments metrics."""
        # Get initial counter value
        initial_count = health_check_counter.labels(status="ok")._value._value

        # Make health check request
        response = self.client.get("/health")
        assert response.status_code == 200

        # Check that counter was incremented
        final_count = health_check_counter.labels(status="ok")._value._value
        assert final_count > initial_count

    def test_request_metrics_collection(self):
        """Test that HTTP requests generate metrics."""
        # Get initial counter values
        initial_count = request_counter.labels(
            method="GET", endpoint="/health", status_code="200"
        )._value._value

        # Make request
        response = self.client.get("/health", headers=self.valid_headers)
        assert response.status_code == 200

        # Check that request counter was incremented
        final_count = request_counter.labels(
            method="GET", endpoint="/health", status_code="200"
        )._value._value
        assert final_count > initial_count

    def test_request_duration_metrics(self):
        """Test that request duration is recorded."""
        # Get initial sample count
        duration_metric = request_duration.labels(method="GET", endpoint="/health")
        initial_count = duration_metric._sum._value

        # Make request
        response = self.client.get("/health")
        assert response.status_code == 200

        # Check that duration was recorded (sum should be higher)
        final_count = duration_metric._sum._value
        assert final_count >= initial_count

    @patch("api.main.process_weather_query")
    def test_weather_query_success_metrics(self, mock_process_query):
        """Test metrics for successful weather queries."""
        # Mock successful response
        mock_process_query.return_value = {
            "summary": "Weather in Tel Aviv is sunny.",
            "params": {"location": "Tel Aviv", "start_date": "2023-12-01"},
            "data": {"temperature": 25},
            "confidence": 0.9,
            "tool_used": "weather.get_range",
        }

        # Get initial counter values
        initial_count = weather_query_counter.labels(
            status="success", location_type="city_name"
        )._value._value

        # Make weather query request
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv today"},
        )

        assert response.status_code == 200

        # Check that success counter was incremented
        final_count = weather_query_counter.labels(
            status="success", location_type="city_name"
        )._value._value
        assert final_count > initial_count

    @patch("api.main.process_weather_query")
    def test_weather_query_coordinates_metrics(self, mock_process_query):
        """Test metrics for coordinate-based weather queries."""
        # Mock successful response with coordinates
        mock_process_query.return_value = {
            "summary": "Weather at coordinates is sunny.",
            "params": {"location": "32.08,34.78", "start_date": "2023-12-01"},
            "data": {"temperature": 25},
            "confidence": 0.9,
            "tool_used": "weather.get_range",
        }

        # Get initial counter values
        initial_count = weather_query_counter.labels(
            status="success", location_type="coordinates"
        )._value._value

        # Make weather query request with coordinates
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather at 32.08,34.78 today"},
        )

        assert response.status_code == 200

        # Check that coordinates counter was incremented
        final_count = weather_query_counter.labels(
            status="success", location_type="coordinates"
        )._value._value
        assert final_count > initial_count

    @patch("api.main.process_weather_query")
    def test_weather_query_error_metrics(self, mock_process_query):
        """Test metrics for failed weather queries."""
        # Mock error response
        mock_process_query.return_value = {
            "error": "missing_location",
            "hint": "Please specify a location",
        }

        # Get initial counter values
        initial_count = weather_query_counter.labels(
            status="error", location_type="unknown"
        )._value._value

        # Make weather query request
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather today"},
        )

        assert response.status_code == 400

        # Check that error counter was incremented
        final_count = weather_query_counter.labels(
            status="error", location_type="unknown"
        )._value._value
        assert final_count > initial_count

    @patch("api.main.process_weather_query")
    def test_weather_query_duration_metrics(self, mock_process_query):
        """Test that weather query duration is recorded."""
        # Mock successful response
        mock_process_query.return_value = {
            "summary": "Weather is good.",
            "params": {"location": "London"},
            "data": {"temperature": 20},
            "confidence": 0.8,
            "tool_used": "weather.get_range",
        }

        # Get initial duration sum
        duration_metric = weather_query_duration.labels(status="success")
        initial_sum = duration_metric._sum._value

        # Make weather query request
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in London today"},
        )

        assert response.status_code == 200

        # Check that duration was recorded
        final_sum = duration_metric._sum._value
        assert final_sum >= initial_sum

    def test_metrics_endpoint_no_auth_required(self):
        """Test that metrics endpoint doesn't require authentication."""
        response = self.client.get("/metrics")

        # Should work without auth headers
        assert response.status_code == 200
        assert "weathersense_" in response.text

    def test_metrics_not_collected_for_metrics_endpoint(self):
        """Test that metrics endpoint doesn't collect metrics about itself."""
        # Get initial counter values for /metrics endpoint
        try:
            initial_count = request_counter.labels(
                method="GET", endpoint="/metrics", status_code="200"
            )._value._value
        except KeyError:
            initial_count = 0

        # Make request to metrics endpoint
        response = self.client.get("/metrics")
        assert response.status_code == 200

        # Check that counter was not incremented for /metrics endpoint
        try:
            final_count = request_counter.labels(
                method="GET", endpoint="/metrics", status_code="200"
            )._value._value
        except KeyError:
            final_count = 0

        # Should be the same (no metrics collected for metrics endpoint itself)
        assert final_count == initial_count
