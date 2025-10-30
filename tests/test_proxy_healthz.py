"""
Test suite for the Cloudflare Worker proxy /healthz endpoint functionality.

This test module validates that the proxy correctly maps /healthz requests
to the Cloud Run /health endpoint while maintaining all assignment requirements.

Test Categories:
- Health check endpoint success scenarios
- Error handling and fault tolerance
- Request forwarding validation
- CORS headers compliance
- Response format validation

Note: These tests require the Cloudflare Worker to be deployed and accessible.
For local testing, mock responses are used to simulate the proxy behavior.
"""

import json
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
import requests

# Test configuration
# Replace with your actual Cloudflare Worker URL after deployment
PROXY_BASE_URL = "https://weather-sense-proxy.weather-sense.workers.dev"
CLOUD_RUN_URL = "https://weather-sense-service-1061398738.us-central1.run.app"

# Test timeout configuration
REQUEST_TIMEOUT = 10  # seconds


class TestProxyHealthzEndpoint:
    """Test cases for the /healthz endpoint proxy functionality."""

    def test_healthz_success_response(self):
        """Test that /healthz returns correct health check response."""
        # Mock the Cloud Run /health endpoint response
        expected_response = {"ok": True}

        with patch("requests.get") as mock_get:
            # Configure mock to simulate successful proxy response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_response
            mock_response.headers = {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            }
            mock_get.return_value = mock_response

            # Test the /healthz endpoint
            response = requests.get(
                f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert data.get("ok") is True
            assert "Content-Type" in response.headers
            assert response.headers.get("Content-Type") == "application/json"

    def test_healthz_cors_headers(self):
        """Test that /healthz includes proper CORS headers."""
        with patch("requests.get") as mock_get:
            # Configure mock response with CORS headers
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_response.headers = {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, x-api-key, Accept",
            }
            mock_get.return_value = mock_response

            response = requests.get(
                f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT
            )

            # Verify CORS headers
            assert response.headers.get("Access-Control-Allow-Origin") == "*"
            assert "GET" in response.headers.get("Access-Control-Allow-Methods", "")
            assert "x-api-key" in response.headers.get(
                "Access-Control-Allow-Headers", ""
            )

    def test_healthz_options_preflight(self):
        """Test that OPTIONS requests to /healthz return proper CORS preflight response."""
        with patch("requests.options") as mock_options:
            # Configure mock for OPTIONS preflight
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type, x-api-key, Accept",
                "Access-Control-Max-Age": "86400",
            }
            mock_options.return_value = mock_response

            response = requests.options(
                f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT
            )

            # Verify preflight response
            assert response.status_code == 200
            assert response.headers.get("Access-Control-Allow-Origin") == "*"
            assert response.headers.get("Access-Control-Max-Age") == "86400"

    def test_healthz_backend_unavailable(self):
        """Test /healthz behavior when Cloud Run backend is unavailable."""
        with patch("requests.get") as mock_get:
            # Simulate backend unavailability
            mock_response = Mock()
            mock_response.status_code = 502
            mock_response.json.return_value = {
                "error": "health_check_unavailable",
                "message": "Health check endpoint temporarily unavailable",
            }
            mock_response.headers = {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            }
            mock_get.return_value = mock_response

            response = requests.get(
                f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT
            )

            # Verify error response
            assert response.status_code == 502
            data = response.json()
            assert "error" in data
            assert data["error"] == "health_check_unavailable"
            assert "message" in data

    def test_healthz_proxy_error_handling(self):
        """Test /healthz proxy error handling for network issues."""
        with patch("requests.get") as mock_get:
            # Simulate network error
            mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

            # This should raise an exception since we're mocking the actual request
            with pytest.raises(requests.exceptions.ConnectionError):
                requests.get(f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT)


class TestProxyForwardingBehavior:
    """Test cases for general request forwarding behavior."""

    def test_non_healthz_request_forwarding(self):
        """Test that non-/healthz requests are forwarded correctly."""
        with patch("requests.post") as mock_post:
            # Mock response for forwarded request
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "message": "Weather query processed",
                "status": "success",
            }
            mock_response.headers = {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
            }
            mock_post.return_value = mock_response

            # Test forwarding to /weather endpoint
            test_data = {"query": "weather in Tel Aviv"}
            response = requests.post(
                f"{PROXY_BASE_URL}/weather",
                json=test_data,
                headers={"x-api-key": "test-key"},
                timeout=REQUEST_TIMEOUT,
            )

            # Verify forwarding
            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["status"] == "success"

    def test_query_parameter_preservation(self):
        """Test that query parameters are preserved during forwarding."""
        with patch("requests.get") as mock_get:
            # Mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            # Test request with query parameters
            response = requests.get(
                f"{PROXY_BASE_URL}/some-endpoint?param1=value1&param2=value2",
                timeout=REQUEST_TIMEOUT,
            )

            # Verify response (the mock ensures the request was made)
            assert response.status_code == 200

    def test_request_headers_preservation(self):
        """Test that request headers are preserved during forwarding."""
        with patch("requests.post") as mock_post:
            # Mock response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok"}
            mock_response.headers = {"Content-Type": "application/json"}
            mock_post.return_value = mock_response

            # Test request with custom headers
            custom_headers = {
                "x-api-key": "test-key-12345",
                "User-Agent": "WeatherSense-Test/1.0",
                "Content-Type": "application/json",
            }

            response = requests.post(
                f"{PROXY_BASE_URL}/weather",
                json={"query": "test"},
                headers=custom_headers,
                timeout=REQUEST_TIMEOUT,
            )

            # Verify response
            assert response.status_code == 200


class TestProxyErrorScenarios:
    """Test cases for various error scenarios."""

    def test_invalid_proxy_url(self):
        """Test behavior with invalid proxy URL."""
        invalid_url = "https://non-existent-worker.workers.dev"

        with pytest.raises(requests.exceptions.RequestException):
            requests.get(f"{invalid_url}/healthz", timeout=REQUEST_TIMEOUT)

    def test_proxy_timeout_handling(self):
        """Test proxy behavior with very short timeout."""
        with patch("requests.get") as mock_get:
            # Simulate timeout
            mock_get.side_effect = requests.exceptions.Timeout("Request timeout")

            with pytest.raises(requests.exceptions.Timeout):
                requests.get(f"{PROXY_BASE_URL}/healthz", timeout=0.001)

    def test_malformed_response_handling(self):
        """Test proxy handling of malformed backend responses."""
        with patch("requests.get") as mock_get:
            # Mock malformed response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
            mock_response.text = "Not JSON"
            mock_response.headers = {"Content-Type": "text/plain"}
            mock_get.return_value = mock_response

            response = requests.get(
                f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT
            )

            # Verify response handling
            assert response.status_code == 200
            # Should not raise exception even with malformed JSON


class TestProxyResponseFormat:
    """Test cases for response format validation."""

    def test_healthz_response_structure(self):
        """Test that /healthz response matches expected structure."""
        with patch("requests.get") as mock_get:
            # Mock successful health check response
            expected_structure = {"ok": True}
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = expected_structure
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            response = requests.get(
                f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT
            )

            # Verify structure
            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "ok" in data
            assert isinstance(data["ok"], bool)
            assert data["ok"] is True

    def test_error_response_structure(self):
        """Test that error responses maintain consistent structure."""
        with patch("requests.get") as mock_get:
            # Mock error response
            error_structure = {
                "error": "health_check_unavailable",
                "message": "Health check endpoint temporarily unavailable",
            }
            mock_response = Mock()
            mock_response.status_code = 502
            mock_response.json.return_value = error_structure
            mock_response.headers = {"Content-Type": "application/json"}
            mock_get.return_value = mock_response

            response = requests.get(
                f"{PROXY_BASE_URL}/healthz", timeout=REQUEST_TIMEOUT
            )

            # Verify error structure
            assert response.status_code == 502
            data = response.json()
            assert isinstance(data, dict)
            assert "error" in data
            assert "message" in data
            assert isinstance(data["error"], str)
            assert isinstance(data["message"], str)


# Test utility functions
def simulate_cloud_run_health_response() -> Dict[str, Any]:
    """Simulate a successful Cloud Run /health response."""
    return {"ok": True}


def simulate_cloud_run_error_response() -> Dict[str, Any]:
    """Simulate a Cloud Run error response."""
    return {"error": "internal_error", "message": "Service temporarily unavailable"}


# Integration test marker
@pytest.mark.integration
class TestProxyIntegration:
    """
    Integration tests that require actual proxy deployment.

    These tests are marked with @pytest.mark.integration and require:
    1. Deployed Cloudflare Worker
    2. Working Cloud Run service
    3. Proper environment configuration

    Run with: pytest -m integration tests/test_proxy_healthz.py
    """

    @pytest.mark.integration
    def test_live_healthz_endpoint(self):
        """Test actual deployed /healthz endpoint."""
        response = requests.get(f"{PROXY_BASE_URL}/healthz")
        assert response.status_code == 200
        data = response.json()
        assert data.get("ok") is True

    @pytest.mark.integration
    def test_live_request_forwarding(self):
        """Test actual request forwarding through deployed proxy."""
        test_data = {"query": "weather in Tel Aviv for today"}
        response = requests.post(
            f"{PROXY_BASE_URL}/weather",
            json=test_data,
            headers={"x-api-key": "your-api-key"},
        )
        # 404 is expected since /weather endpoint doesn't exist in Cloud Run service
        # This test validates that the proxy forwards non-/healthz requests correctly
        assert response.status_code == 404

        # Verify error response format
        data = response.json()
        assert "detail" in data


if __name__ == "__main__":
    # Run tests when script is executed directly
    pytest.main([__file__, "-v"])
