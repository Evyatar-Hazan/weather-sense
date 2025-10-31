"""
API Endpoints Integration Tests for WeatherSense

This module provides comprehensive testing of all WeatherSense API endpoints
across different deployment environments (local, cloud, proxy).
Tests validate functionality, performance, and response formats.
"""
import os
import time
from typing import Dict, Optional, Tuple
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

# Set test environment variables
os.environ["API_KEY"] = "test-api-key-123"
os.environ["LOG_LEVEL"] = "ERROR"  # Reduce log noise in tests

# Import after environment setup
from api.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    """Create a TestClient for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def valid_headers():
    """Provide valid authentication headers for local testing."""
    return {"x-api-key": "test-api-key-123"}


@pytest.fixture
def production_config():
    """Production environment configuration."""
    return {
        "cloud": {
            "name": "Cloud Run Direct",
            "base_url": os.getenv(
                "BASE_CLOUD", "https://weather-sense-service-ektuy7j2kq-uc.a.run.app"
            ),
            "api_key": os.getenv(
                "KEY_PROD", "interview-demo-20251029-974213a2e493d09f"
            ),
            "health_endpoint": "/health",
        },
        "proxy": {
            "name": "Cloudflare Proxy",
            "base_url": os.getenv(
                "BASE_PROXY", "https://weather-sense-proxy.weather-sense.workers.dev"
            ),
            "api_key": os.getenv(
                "KEY_PROD", "interview-demo-20251029-974213a2e493d09f"
            ),
            "health_endpoint": "/healthz",
        },
    }


@pytest.fixture
def weather_test_cases():
    """Standard weather query test cases."""
    return [
        {
            "name": "Relative dates with metric units",
            "query": "Summarize weather in Tel Aviv from last Monday to Friday, metric",
            "expected_fields": ["summary", "params", "data"],
        },
        {
            "name": "Explicit dates with imperial units",
            "query": "NYC weather 2025-10-01 to 2025-10-07, imperial",
            "expected_fields": ["summary", "params", "data"],
        },
        {
            "name": "Today query",
            "query": "weather in Jerusalem today, metric",
            "expected_fields": ["summary", "params", "data"],
        },
        {
            "name": "Date range query",
            "query": "weather in Haifa from October 28 to October 30, metric",
            "expected_fields": ["summary", "params", "data"],
        },
    ]


class TestLocalHealthEndpoint:
    """Test suite for the local /health endpoint."""

    def test_health_check_success(self, client):
        """Test successful health check."""
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_health_check_with_headers(self, client, valid_headers):
        """Test health check with API key headers."""
        response = client.get("/health", headers=valid_headers)

        assert response.status_code == 200
        assert response.json() == {"ok": True}


class TestLocalWeatherEndpoint:
    """Test suite for the local /v1/weather/ask endpoint."""

    @patch("crew.flow.WeatherAnalysisFlow.process_query")
    def test_weather_endpoint_mocked(self, mock_process_query, client, valid_headers):
        """Test weather endpoint with mocked CrewAI flow."""
        # Mock successful response
        mock_process_query.return_value = {
            "summary": "Test weather summary for Tel Aviv",
            "params": {"location": "Tel Aviv", "units": "metric"},
            "data": {"daily": [{"date": "2025-10-31", "temp": 25}]},
            "confidence": 0.8,
            "tool_used": "weather.test",
        }

        response = client.post(
            "/v1/weather/ask",
            headers=valid_headers,
            json={"query": "weather in Tel Aviv today"},
        )

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "summary" in data
        assert "params" in data
        assert "data" in data
        assert "confidence" in data
        assert "tool_used" in data

    def test_weather_endpoint_missing_auth(self, client):
        """Test weather endpoint without authentication."""
        response = client.post("/v1/weather/ask", json={"query": "weather in Tel Aviv"})

        assert response.status_code == 401

    def test_weather_endpoint_invalid_auth(self, client):
        """Test weather endpoint with invalid API key."""
        response = client.post(
            "/v1/weather/ask",
            headers={"x-api-key": "invalid-key"},
            json={"query": "weather in Tel Aviv"},
        )

        assert response.status_code == 401

    def test_weather_endpoint_missing_query(self, client, valid_headers):
        """Test weather endpoint with missing query field."""
        response = client.post("/v1/weather/ask", headers=valid_headers, json={})

        assert response.status_code == 422

    def test_weather_endpoint_empty_query(self, client, valid_headers):
        """Test weather endpoint with empty query."""
        response = client.post(
            "/v1/weather/ask", headers=valid_headers, json={"query": ""}
        )

        assert response.status_code == 422


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("BASE_CLOUD") or not os.getenv("KEY_PROD"),
    reason="Production environment variables not set",
)
class TestProductionEndpoints:
    """Integration tests for production endpoints (Cloud Run and Proxy)."""

    def _make_request(
        self,
        method: str,
        url: str,
        headers: Dict,
        data: Optional[Dict] = None,
        timeout: int = 30,
    ) -> Tuple[bool, Dict]:
        """Make HTTP request with error handling."""
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=timeout)
            else:
                response = requests.post(
                    url, headers=headers, json=data, timeout=timeout
                )

            return True, {
                "status_code": response.status_code,
                "data": response.json()
                if response.headers.get("content-type", "").startswith(
                    "application/json"
                )
                else response.text,
                "duration": response.elapsed.total_seconds(),
            }
        except requests.exceptions.RequestException as e:
            return False, {"error": str(e)}

    def test_cloud_run_health_endpoint(self, production_config):
        """Test Cloud Run health endpoint."""
        config = production_config["cloud"]
        url = f"{config['base_url']}{config['health_endpoint']}"
        headers = {"x-api-key": config["api_key"]}

        success, result = self._make_request("GET", url, headers)

        assert success, f"Request failed: {result.get('error')}"
        assert result["status_code"] == 200
        assert result["data"] == {"ok": True}

    def test_proxy_health_endpoint(self, production_config):
        """Test Cloudflare proxy health endpoint."""
        config = production_config["proxy"]
        url = f"{config['base_url']}{config['health_endpoint']}"
        headers = {"x-api-key": config["api_key"]}

        success, result = self._make_request("GET", url, headers)

        assert success, f"Request failed: {result.get('error')}"
        assert result["status_code"] == 200
        assert result["data"] == {"ok": True}

    @pytest.mark.parametrize("env_name", ["cloud", "proxy"])
    def test_weather_endpoints_all_environments(
        self, production_config, weather_test_cases, env_name
    ):
        """Test weather endpoints across all production environments."""
        config = production_config[env_name]

        for test_case in weather_test_cases:
            url = f"{config['base_url']}/v1/weather/ask"
            headers = {
                "x-api-key": config["api_key"],
                "Content-Type": "application/json",
            }
            data = {"query": test_case["query"]}

            success, result = self._make_request("POST", url, headers, data, timeout=60)

            # Allow for some tolerance in production environment
            if not success:
                pytest.skip(
                    f"Production endpoint {env_name} "
                    f"not available: {result.get('error')}"
                )

            error_msg = f"Failed for {test_case['name']} /n"
            f"on {env_name}"

            assert result["status_code"] == 200, error_msg

            # Validate response structure
            response_data = result["data"]
            for field in test_case["expected_fields"]:
                assert (
                    field in response_data
                ), f"Missing {field} in {test_case['name']} response from {env_name}"

    def test_weather_response_consistency(self, production_config):
        """Test that same query returns consistent structure across environments."""
        query = "weather in Tel Aviv today, metric"
        results = {}

        for env_name, config in production_config.items():
            url = f"{config['base_url']}/v1/weather/ask"
            headers = {
                "x-api-key": config["api_key"],
                "Content-Type": "application/json",
            }
            data = {"query": query}

            success, result = self._make_request("POST", url, headers, data, timeout=60)

            if success and result["status_code"] == 200:
                results[env_name] = result["data"]

        # Skip if no environments are available
        if len(results) < 2:
            pytest.skip(
                "Not enough production environments available for consistency test"
            )

        # Check that all successful responses have the same structure
        first_env = list(results.keys())[0]
        first_response = results[first_env]

        for env_name, response in results.items():
            if env_name == first_env:
                continue

            # Check that both responses have the same top-level keys
            assert set(response.keys()) == set(
                first_response.keys()
            ), f"Response structure differs between {first_env} and {env_name}"


@pytest.mark.integration
class TestEndpointPerformance:
    """Performance tests for API endpoints."""

    def test_health_endpoint_performance(self, client):
        """Test health endpoint response time."""
        start_time = time.time()
        response = client.get("/health")
        duration = time.time() - start_time

        assert response.status_code == 200
        assert duration < 1.0, f"Health endpoint too slow: {duration:.3f}s"

    @patch("crew.flow.WeatherAnalysisFlow.process_query")
    def test_weather_endpoint_performance(
        self, mock_process_query, client, valid_headers
    ):
        """Test weather endpoint response time with mocked backend."""
        # Mock fast response
        mock_process_query.return_value = {
            "summary": "Fast test response",
            "params": {"location": "Tel Aviv"},
            "data": {"daily": []},
            "confidence": 0.8,
            "tool_used": "weather.test",
        }

        start_time = time.time()
        response = client.post(
            "/v1/weather/ask",
            headers=valid_headers,
            json={"query": "weather in Tel Aviv today"},
        )
        duration = time.time() - start_time

        assert response.status_code == 200
        assert duration < 5.0, f"Weather endpoint too slow: {duration:.3f}s"


class TestErrorHandling:
    """Test error handling across all endpoints."""

    def test_invalid_endpoint(self, client):
        """Test 404 for invalid endpoints."""
        response = client.get("/invalid-endpoint")
        assert response.status_code == 404

    def test_malformed_json(self, client, valid_headers):
        """Test handling of malformed JSON."""
        response = client.post(
            "/v1/weather/ask",
            headers={**valid_headers, "Content-Type": "application/json"},
            data="malformed json",
        )
        assert response.status_code == 422

    def test_method_not_allowed(self, client):
        """Test 405 for incorrect HTTP methods."""
        response = client.post("/health")
        assert response.status_code == 405


if __name__ == "__main__":
    """Allow running this test file directly."""
    pytest.main([__file__, "-v"])
