"""
Simplified Integration Tests for WeatherSense Deployment (No Docker Required)

These tests verify deployment configuration and documentation requirements
without requiring Docker to be running. These are faster to run and validate
most of the deployment setup.
"""
import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


class TestDocumentationOnly:
    """Test deployment documentation and configuration without Docker."""

    @pytest.fixture(autouse=True)
    def setup_documentation_test(self):
        """Setup documentation test environment."""
        self.workspace_root = Path(__file__).parent.parent
        # Load README content once for all tests
        readme_path = self.workspace_root / "README.md"
        if readme_path.exists():
            self.readme_content = readme_path.read_text(encoding="utf-8")
        else:
            self.readme_content = ""

    def test_dockerfile_exists_and_valid(self):
        """Verify Dockerfile exists and has required configuration."""
        dockerfile_path = self.workspace_root / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile not found"

        dockerfile_content = dockerfile_path.read_text()

        # Check for required Dockerfile elements
        required_elements = [
            "FROM python:",  # Base image
            "WORKDIR /app",  # Working directory
            "COPY pyproject.toml",  # Dependencies
            "RUN pip install",  # Install dependencies
            "EXPOSE",  # Port exposure
            "CMD",  # Entrypoint command
            "ENV",  # Environment variables
        ]

        for element in required_elements:
            assert (
                element in dockerfile_content
            ), f"Required Dockerfile element '{element}' not found"

        # Check specific configurations
        assert "PORT=8000" in dockerfile_content, "PORT environment variable not set"
        assert (
            "docker_entrypoint.py" in dockerfile_content
        ), "docker_entrypoint.py not used as entrypoint"

        logger.info("✅ Dockerfile is properly configured")

    def test_readme_contains_deployment_section(self):
        """Test that README.md contains deployment steps."""
        content = self.readme_content

        # Check for main deployment section
        assert "## 🚀 Deployment & Production" in content
        assert "### Docker Deployment" in content
        assert (
            "#### Quick Deployment" in content
        )  # This is the actual heading in README

    def test_gcloud_deploy_command_syntax(self):
        """Verify gcloud run deploy command has correct syntax."""
        readme_path = self.workspace_root / "README.md"
        readme_content = readme_path.read_text()

        # Extract gcloud run deploy command (handles multi-line with backslashes)
        # Look for the complete gcloud command block
        gcloud_start = readme_content.find("gcloud run deploy")
        assert gcloud_start != -1, "gcloud run deploy command not found"

        # Find the end - look for next ```
        next_code_block = readme_content.find("```", gcloud_start)
        if next_code_block == -1:
            next_code_block = len(readme_content)

        deploy_command = readme_content[gcloud_start:next_code_block].strip()

        # Required flags for our deployment
        required_flags = [
            "--allow-unauthenticated",
            "--platform managed",
            "--region",
            "--image",
            "--set-env-vars",
            "--port 8000",
        ]

        for flag in required_flags:
            assert (
                flag in deploy_command
            ), f"Required flag '{flag}' missing from gcloud deploy command"

        logger.info("✅ gcloud run deploy command has correct syntax and flags")

    def test_environment_variables_documented(self):
        """Verify all required environment variables are documented."""
        readme_path = self.workspace_root / "README.md"
        readme_content = readme_path.read_text()

        # Required environment variables for the application
        required_vars = ["API_KEY", "LOG_LEVEL", "DEPLOYMENT_ENV", "TZ"]

        for var in required_vars:
            assert (
                var in readme_content
            ), f"Required environment variable '{var}' not documented"

        # Check for environment variables table or section
        env_indicators = ["Environment Variables", "| Variable |", "--set-env-vars"]

        env_section_found = any(
            indicator in readme_content for indicator in env_indicators
        )
        assert (
            env_section_found
        ), "Environment variables section not properly documented"

        logger.info("✅ All required environment variables are documented")

    def test_pyproject_toml_dependencies(self):
        """Verify pyproject.toml has all required dependencies."""
        pyproject_path = self.workspace_root / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"

        pyproject_content = pyproject_path.read_text()

        # Core dependencies for the application
        required_deps = ["fastapi", "uvicorn", "crewai", "requests", "pydantic"]

        for dep in required_deps:
            assert (
                dep in pyproject_content
            ), f"Required dependency '{dep}' missing from pyproject.toml"

        # Test dependencies
        test_deps = ["pytest", "docker"]
        for dep in test_deps:
            assert (
                dep in pyproject_content
            ), f"Test dependency '{dep}' missing from pyproject.toml"

        logger.info("✅ pyproject.toml contains all required dependencies")

    def test_docker_entrypoint_exists(self):
        """Verify docker_entrypoint.py exists and has proper structure."""
        entrypoint_path = self.workspace_root / "docker_entrypoint.py"
        assert entrypoint_path.exists(), "docker_entrypoint.py not found"

        entrypoint_content = entrypoint_path.read_text()

        # Check for required functionality
        required_functions = [
            "def start_api_server",
            "def monitor_processes",
            "def cleanup",
            "def main",
        ]

        for func in required_functions:
            assert (
                func in entrypoint_content
            ), f"Required function '{func}' not found in docker_entrypoint.py"

        # Check for API server startup
        assert "uvicorn" in entrypoint_content, "uvicorn server startup not found"
        assert "api.main:app" in entrypoint_content, "FastAPI app reference not found"

        logger.info("✅ docker_entrypoint.py is properly structured")

    def test_mcp_server_exists(self):
        """Verify MCP server exists and can be called."""
        mcp_server_path = self.workspace_root / "mcp_weather" / "server.py"
        assert mcp_server_path.exists(), "MCP server not found"

        mcp_content = mcp_server_path.read_text()

        # Check for stdio communication setup
        assert (
            "sys.stdin" in mcp_content or "input()" in mcp_content
        ), "stdin communication not found"
        assert (
            "sys.stdout" in mcp_content or "print(" in mcp_content
        ), "stdout communication not found"

        # Check for JSON handling
        assert "json" in mcp_content, "JSON handling not found"

        logger.info("✅ MCP server exists and has proper stdio communication")

    def test_api_security_configuration(self):
        """Verify API has proper security configuration."""
        api_main_path = self.workspace_root / "api" / "main.py"
        assert api_main_path.exists(), "API main file not found"

        api_content = api_main_path.read_text()

        # Check for authentication
        assert "x-api-key" in api_content, "API key authentication not found"
        assert "verify_api_key" in api_content, "API key verification not found"

        # Check for health endpoint without auth
        assert "/health" in api_content, "Health endpoint not found"

        # Check for weather endpoint with auth
        assert "/v1/weather/ask" in api_content, "Weather endpoint not found"

        logger.info("✅ API has proper security configuration")


def run_documentation_tests():
    """Run documentation-only tests."""
    logger.info("Running WeatherSense Documentation Validation Tests")
    logger.info("=" * 60)

    test_instance = TestDocumentationOnly()
    test_methods = [
        method for method in dir(test_instance) if method.startswith("test_")
    ]

    results = {}

    for method_name in test_methods:
        logger.info(f"\n--- {method_name} ---")
        try:
            method = getattr(test_instance, method_name)
            method()
            results[method_name] = "PASSED"
            logger.info(f"✅ {method_name} PASSED")
        except Exception as e:
            results[method_name] = f"FAILED: {e}"
            logger.error(f"❌ {method_name} FAILED: {e}")

    # Summary
    total = len(results)
    passed = len([r for r in results.values() if r == "PASSED"])

    logger.info(f"\nDocumentation Tests Summary: {passed}/{total} passed")

    if passed == total:
        logger.info("🎉 ALL DOCUMENTATION TESTS PASSED!")
        return True
    else:
        logger.error(f"❌ {total - passed} test(s) failed")
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    success = run_documentation_tests()
    sys.exit(0 if success else 1)
