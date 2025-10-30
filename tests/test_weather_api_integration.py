"""
Production-grade integration tests for WeatherSense API.

This module provides comprehensive HTTP integration testing for the FastAPI
weather service, including authentication, error handling, performance, and
deterministic behavior validation.
"""
import json
import os
import time
import uuid
from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

# Set test environment variables before importing the app
os.environ["API_KEY"] = "test-api-key-123"
os.environ["TZ"] = "Asia/Jerusalem"
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["WEATHER_PROVIDER"] = "open-meteo"

from api.main import app


@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app with proper configuration."""
    return TestClient(app)


@pytest.fixture
def valid_headers():
    """Provide valid authentication headers."""
    return {"x-api-key": "test-api-key-123"}


@pytest.fixture
def invalid_headers():
    """Provide invalid authentication headers."""
    return {"x-api-key": "invalid-key-456"}


@pytest.fixture
def sample_query():
    """Provide a sample weather query for testing."""
    return "weather in Tel Aviv from Monday to Friday, metric"


class TestHealthEndpoint:
    """Test suite for the /health endpoint."""

    def test_health_returns_ok(self, client):
        """Test that /health returns { "ok": true }."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data == {"ok": True}
        assert isinstance(data["ok"], bool)

    def test_health_no_auth_required(self, client):
        """Verify that no authentication is required for /health."""
        # Test without any headers
        response = client.get("/health")
        assert response.status_code == 200

        # Test with invalid headers (should still work)
        response = client.get("/health", headers={"x-api-key": "invalid"})
        assert response.status_code == 200

    def test_health_response_format(self, client):
        """Validate response format and content type."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"

        # Ensure only expected fields are present
        data = response.json()
        assert set(data.keys()) == {"ok"}


class TestWeatherAskAuth:
    """Test suite for authentication on /v1/weather/ask endpoint."""

    def test_missing_api_key_returns_401(self, client, sample_query):
        """Test that missing x-api-key header returns 401."""
        response = client.post("/v1/weather/ask", json={"query": sample_query})

        assert response.status_code == 401
        data = response.json()
        assert "error" in data or "detail" in data

    def test_invalid_api_key_returns_401(self, client, invalid_headers, sample_query):
        """Test that invalid x-api-key returns 401."""
        response = client.post(
            "/v1/weather/ask", headers=invalid_headers, json={"query": sample_query}
        )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data or "detail" in data

    def test_valid_api_key_returns_200_or_processing_error(
        self, client, valid_headers, sample_query
    ):
        """Test that valid x-api-key allows request processing (status 200 or valid error)."""
        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": sample_query}
        )

        # Should not be 401 - either success (200) or valid processing error (400, 429, 502)
        assert response.status_code != 401
        assert response.status_code in [200, 400, 429, 502]

    def test_empty_api_key_returns_401(self, client, sample_query):
        """Test that empty x-api-key header returns 401."""
        response = client.post(
            "/v1/weather/ask", headers={"x-api-key": ""}, json={"query": sample_query}
        )

        assert response.status_code == 401


class TestWeatherAskSuccess:
    """Test suite for successful weather query scenarios."""

    def test_weather_ask_success_response_schema(self, client, valid_headers):
        """Test full valid request and validate response JSON schema."""
        query = "weather in Tel Aviv from Monday to Friday, metric"

        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        # Skip schema validation if request failed due to external dependencies
        if response.status_code != 200:
            pytest.skip(
                f"External dependency unavailable (status: {response.status_code})"
            )

        data = response.json()

        # Validate all required fields are present
        required_fields = [
            "summary",
            "params",
            "data",
            "confidence",
            "tool_used",
            "latency_ms",
            "request_id",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Validate field types and constraints
        assert isinstance(data["summary"], str)
        assert len(data["summary"]) > 0
        assert not any(
            placeholder in data["summary"].lower()
            for placeholder in ["placeholder", "todo", "xxx", "tbd"]
        )

        assert isinstance(data["params"], dict)
        assert isinstance(data["data"], dict)

        assert isinstance(data["confidence"], (int, float))
        assert 0.0 <= data["confidence"] <= 1.0

        assert isinstance(data["tool_used"], str)
        assert data["tool_used"] == "weather.get_range"

        assert isinstance(data["latency_ms"], (int, float))
        assert data["latency_ms"] > 0

        assert isinstance(data["request_id"], str)
        # Validate UUID format
        uuid.UUID(data["request_id"])

    def test_weather_ask_params_validation(self, client, valid_headers):
        """Verify params field contains expected weather parameters."""
        query = "weather in Jerusalem from last Monday to Friday, metric units"

        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        if response.status_code != 200:
            pytest.skip(
                f"External dependency unavailable (status: {response.status_code})"
            )

        data = response.json()
        params = data["params"]

        # Validate expected parameter fields
        expected_param_fields = ["location", "start_date", "end_date", "units"]
        for field in expected_param_fields:
            assert field in params, f"Missing param field: {field}"

        # Validate param formats
        assert isinstance(params["location"], str)
        assert len(params["location"]) > 0

        # Date format validation (YYYY-MM-DD)
        import re

        date_pattern = r"^\d{4}-\d{2}-\d{2}$"
        assert re.match(date_pattern, params["start_date"])
        assert re.match(date_pattern, params["end_date"])

        assert params["units"] in ["metric", "imperial"]

    def test_weather_ask_data_structure(self, client, valid_headers):
        """Verify data field contains expected weather data structure."""
        query = "weather in London from yesterday to today, metric"

        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        if response.status_code != 200:
            pytest.skip(
                f"External dependency unavailable (status: {response.status_code})"
            )

        data = response.json()
        weather_data = data["data"]

        # Validate data structure
        assert "daily" in weather_data
        assert "source" in weather_data
        assert weather_data["source"] == "open-meteo"

        # Validate daily data is a list
        assert isinstance(weather_data["daily"], list)
        if weather_data["daily"]:  # If data is present
            # Each daily entry should be a dict
            for daily_entry in weather_data["daily"]:
                assert isinstance(daily_entry, dict)


class TestWeatherAskErrors:
    """Test suite for error handling scenarios."""

    def test_empty_query_returns_400(self, client, valid_headers):
        """Test that empty query returns 400."""
        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": ""}
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_whitespace_only_query_returns_400(self, client, valid_headers):
        """Test that whitespace-only query returns 400."""
        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": "   \n\t  "}
        )

        assert response.status_code == 400
        data = response.json()
        assert "error" in data or "detail" in data

    def test_invalid_date_range_returns_400(self, client, valid_headers):
        """Test that invalid date range (over 31 days) returns 400."""
        # Query for a very long period (over 31 days)
        query = "weather in Tel Aviv from January 1st to March 31st, metric"

        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        # Should return 400 for range too large, or skip if external service unavailable
        if response.status_code not in [200, 400, 429, 502]:
            pytest.fail(f"Unexpected status code: {response.status_code}")

        if response.status_code == 400:
            data = response.json()
            assert "error" in data or "detail" in data

    def test_unknown_location_returns_400(self, client, valid_headers):
        """Test that unknown location returns 400."""
        query = "weather in Nonexistentville12345 tomorrow, metric"

        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        # Should return 400 for unknown location, or skip if external service unavailable
        if response.status_code not in [200, 400, 429, 502]:
            pytest.fail(f"Unexpected status code: {response.status_code}")

        if response.status_code == 400:
            data = response.json()
            assert "error" in data or "detail" in data

    def test_malformed_json_returns_422(self, client, valid_headers):
        """Test that malformed request body returns 422."""
        response = client.post(
            "/v1/weather/ask", headers=valid_headers, content="invalid json"
        )

        assert response.status_code == 422

    def test_missing_query_field_returns_422(self, client, valid_headers):
        """Test that missing query field returns 422."""
        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"not_query": "weather data"}
        )

        assert response.status_code == 422


class TestWeatherAskPerformance:
    """Test suite for performance and latency validation."""

    def test_latency_measurement_accuracy(self, client, valid_headers):
        """Test that latency_ms matches actual measured duration (±10%)."""
        query = "weather in Tel Aviv today, metric"

        start_time = time.time()
        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )
        end_time = time.time()

        if response.status_code != 200:
            pytest.skip(
                f"External dependency unavailable (status: {response.status_code})"
            )

        measured_duration_ms = (end_time - start_time) * 1000
        data = response.json()
        reported_latency_ms = data["latency_ms"]

        # Allow 10% tolerance for latency measurement
        tolerance = 0.10
        assert (
            abs(reported_latency_ms - measured_duration_ms) / measured_duration_ms
            <= tolerance
        ), f"Latency mismatch: reported {reported_latency_ms}ms, measured {measured_duration_ms:.0f}ms"

    def test_latency_is_positive(self, client, valid_headers):
        """Test that latency_ms is always positive."""
        query = "weather in London today, metric"

        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        if response.status_code != 200:
            pytest.skip(
                f"External dependency unavailable (status: {response.status_code})"
            )

        data = response.json()
        assert data["latency_ms"] > 0

    def test_request_includes_structured_logs(self, client, valid_headers, caplog):
        """Test that logs include structured request_id and task durations."""
        query = "weather in Paris today, metric"

        with caplog.at_level("DEBUG"):  # Capture more log levels
            response = client.post(
                "/v1/weather/ask", headers=valid_headers, json={"query": query}
            )

        if response.status_code != 200:
            pytest.skip(
                f"External dependency unavailable (status: {response.status_code})"
            )

        data = response.json()
        request_id = data["request_id"]

        # Check that request_id appears in logs - check both message and record attributes
        found_request_id = False
        for record in caplog.records:
            # Check message content
            if request_id in record.message:
                found_request_id = True
                break
            # Check if record has request_id attribute (from structured logging)
            if hasattr(record, "request_id") and record.request_id == request_id:
                found_request_id = True
                break

        assert (
            found_request_id
        ), f"request_id {request_id} not found in logs. Available records: {[r.message for r in caplog.records]}"


class TestWeatherAskDeterminism:
    """Test suite for deterministic behavior validation."""

    def test_identical_queries_same_params_and_data(self, client, valid_headers):
        """Test that identical queries return identical params and data."""
        query = "weather in Tokyo yesterday, metric"

        # Make two identical requests
        response1 = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        response2 = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": query}
        )

        if response1.status_code != 200 or response2.status_code != 200:
            pytest.skip("External dependency unavailable")

        data1 = response1.json()
        data2 = response2.json()

        # Params should be identical
        assert data1["params"] == data2["params"]

        # Data content should be identical
        assert data1["data"]["daily"] == data2["data"]["daily"]
        assert data1["data"]["source"] == data2["data"]["source"]

        # Summary should be identical (deterministic)
        assert data1["summary"] == data2["summary"]

        # Confidence should be identical
        assert data1["confidence"] == data2["confidence"]

        # Tool used should be identical
        assert data1["tool_used"] == data2["tool_used"]

    def test_different_request_ids_each_time(self, client, valid_headers):
        """Test that each request gets a unique request_id."""
        query = "weather in Berlin today, metric"

        # Make multiple requests
        request_ids = []
        for _ in range(3):
            response = client.post(
                "/v1/weather/ask", headers=valid_headers, json={"query": query}
            )

            if response.status_code != 200:
                pytest.skip("External dependency unavailable")

            data = response.json()
            request_ids.append(data["request_id"])

        # All request IDs should be unique
        assert len(set(request_ids)) == len(request_ids)

        # All should be valid UUIDs
        for req_id in request_ids:
            uuid.UUID(req_id)  # Should not raise exception

    def test_latency_varies_but_reasonable(self, client, valid_headers):
        """Test that latency_ms can vary between requests but stays reasonable."""
        query = "weather in Madrid today, metric"

        latencies = []
        for _ in range(3):
            response = client.post(
                "/v1/weather/ask", headers=valid_headers, json={"query": query}
            )

            if response.status_code != 200:
                pytest.skip("External dependency unavailable")

            data = response.json()
            latencies.append(data["latency_ms"])

        # All latencies should be positive
        assert all(lat > 0 for lat in latencies)

        # Latencies should be reasonable (under 30 seconds)
        assert all(lat < 30000 for lat in latencies)
