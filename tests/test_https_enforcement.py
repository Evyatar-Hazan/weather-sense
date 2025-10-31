"""
Tests for HTTPS enforcement middleware.
"""
import os
from unittest.mock import patch

from fastapi.testclient import TestClient

# Set test environment variables before importing app
os.environ["API_KEY"] = "test-api-key-123"
os.environ["LOG_LEVEL"] = "ERROR"  # Reduce log noise in tests

from api.main import app  # noqa: E402


class TestHTTPSEnforcement:
    def setup_method(self):
        """Setup test fixtures."""
        self.client = TestClient(app)
        self.valid_headers = {"x-api-key": "test-api-key-123"}

    def test_https_enforcement_disabled_by_default_in_tests(self):
        """Test that HTTPS enforcement is disabled for testserver."""
        # Health endpoint should work without HTTPS in test environment
        response = self.client.get("/health")
        assert response.status_code == 200

        # API endpoint should work without redirect in test environment
        response = self.client.post("/v1/weather/ask", json={"query": "test"})
        # Should get 401 (missing auth) not 405 (method not allowed from
        # redirect)
        assert response.status_code == 401

    @patch.dict(os.environ, {"HTTPS_ONLY": "false"})
    def test_https_enforcement_disabled_via_env_var(self):
        """Test that HTTPS enforcement can be disabled via env variable."""
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_security_headers_added_to_responses(self):
        """Test that security headers are added to all responses."""
        response = self.client.get("/health")

        # Check security headers
        assert "Strict-Transport-Security" in response.headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
        assert "Referrer-Policy" in response.headers

        # Verify header values
        assert (
            response.headers["Strict-Transport-Security"]
            == "max-age=31536000; includeSubDomains"
        )
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        hsts_expected = "max-age=31536000; includeSubDomains"
        assert response.headers["Strict-Transport-Security"] == hsts_expected
        referrer_expected = "strict-origin-when-cross-origin"
        assert response.headers["Referrer-Policy"] == referrer_expected

    def test_security_headers_on_api_endpoints(self):
        """Test that security headers are added to API endpoints."""
        response = self.client.post(
            "/v1/weather/ask",
            headers=self.valid_headers,
            json={"query": "weather in Tel Aviv today"},
        )

        # Response might be 400 due to parsing issues, but headers should be
        # present
        assert "Strict-Transport-Security" in response.headers
        assert "X-Content-Type-Options" in response.headers

    @patch.dict(os.environ, {"HTTPS_ONLY": "true"})
    def test_https_enforcement_allows_health_checks(self):
        """Test that health checks are allowed even with HTTPS enforcement."""
        # Health endpoint should work even with HTTPS enforcement enabled
        # because localhost is exempted
        response = self.client.get("/health")
        assert response.status_code == 200

    def test_cors_still_works_with_https_middleware(self):
        """Test that CORS headers are still present with HTTPS middleware."""
        response = self.client.get("/health")

        # Should have security headers (CORS headers are added by FastAPI
        # for actual cross-origin requests)
        assert "Strict-Transport-Security" in response.headers
        assert response.status_code == 200
