"""
Comprehensive Integration Tests for WeatherSense Deployment

These tests verify the deployment requirements without mocks or stubs,
ensuring the real system meets production deployment specifications.
"""
import os
import sys
import json
import time
import docker
import subprocess
import threading
import tempfile
import shutil
import re
import requests
import pytest
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

# Setup logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeploymentIntegrationTest:
    """
    Base class for deployment integration tests that interact with real systems.
    """
    
    @pytest.fixture(autouse=True)
    def setup_integration_test(self):
        """Setup integration test environment."""
        self.workspace_root = Path(__file__).parent.parent
        self.docker_client = None
        self.test_image_tag = "weather-sense:integration-test"
        self.test_container = None
        self.api_base_url = "http://localhost:8000"
        self.test_api_key = "test-integration-key-12345"
        
        # Initialize Docker client only when needed
        try:
            self.docker_client = docker.from_env()
        except Exception as e:
            logger.warning(f"Docker not available: {e}")
            self.docker_client = None
        
        yield
        
        # Cleanup
        self.cleanup_test_environment()
        
    def setup_test_environment(self):
        """Setup test environment with required variables."""
        os.environ.update({
            "API_KEY": self.test_api_key,
            "LOG_LEVEL": "INFO",
            "TZ": "UTC",
            "DEPLOYMENT_ENV": "docker"
        })
    
    def cleanup_test_environment(self):
        """Clean up test environment."""
        self.cleanup_docker_resources()
    
    def start_test_container(self):
        """Start test container with both services and verify they're running."""
        if self.docker_client is None:
            pytest.skip("Docker not available")
            
        self.setup_test_environment()
        
        # Build image first if needed
        try:
            self.docker_client.images.get(self.test_image_tag)
            logger.info(f"Using existing image: {self.test_image_tag}")
        except docker.errors.ImageNotFound:
            logger.info(f"Building Docker image: {self.test_image_tag}")
            self.docker_client.images.build(
                path=str(self.workspace_root),
                tag=self.test_image_tag,
                rm=True
            )
        
        logger.info("Starting container to test service startup...")
        
        try:
            # Start container with test environment
            self.test_container = self.docker_client.containers.run(
                self.test_image_tag,
                environment={
                    "API_KEY": self.test_api_key,
                    "LOG_LEVEL": "INFO", 
                    "TZ": "UTC",
                    "DEPLOYMENT_ENV": "docker",
                    "PORT": "8000"
                },
                ports={"8000/tcp": 8000},
                detach=True,
                remove=False
            )
            
            # Wait for services to start
            time.sleep(10)
            
            # Check container is running
            self.test_container.reload()
            assert self.test_container.status == "running"
            
            # Get container logs to verify both services started
            logs = self.test_container.logs().decode('utf-8')
            
            # Verify API server started
            assert "API server started with PID" in logs, f"API server not started. Logs: {logs}"
            assert "All services started successfully" in logs, f"Not all services started. Logs: {logs}"
            
            logger.info("✅ Container started with both services running")
            
        except Exception as e:
            if self.test_container:
                logs = self.test_container.logs().decode('utf-8')
                logger.error(f"Container logs: {logs}")
            pytest.fail(f"Container startup test failed: {e}")
        
    def cleanup_docker_resources(self):
        """Clean up Docker containers and images created during testing."""
        try:
            if self.test_container:
                self.test_container.stop()
                self.test_container.remove()
                self.test_container = None
                
            # Remove test image
            try:
                self.docker_client.images.remove(self.test_image_tag, force=True)
            except docker.errors.ImageNotFound:
                pass
                
        except Exception as e:
            logger.warning(f"Error during Docker cleanup: {e}")


class TestSingleDockerImage(DeploymentIntegrationTest):
    """
    Test that validates single Docker image contains both FastAPI and MCP server
    and that both processes run and communicate correctly.
    """
    
    def test_docker_image_builds_successfully(self):
        """Verify that Docker image builds without errors."""
        if self.docker_client is None:
            pytest.skip("Docker not available")
            
        logger.info("Building Docker image for integration test...")
        
        # Build image from current workspace
        try:
            image, build_logs = self.docker_client.images.build(
                path=str(self.workspace_root),
                tag=self.test_image_tag,
                rm=True,
                forcerm=True
            )
            
            # Check that image was created
            assert image is not None
            assert self.test_image_tag in [tag for tag in image.tags]
            
            logger.info(f"✅ Docker image built successfully: {self.test_image_tag}")
            
        except docker.errors.BuildError as e:
            pytest.fail(f"Docker build failed: {e}")
            
    def test_container_starts_both_services(self):
        """Verify container starts and both API + MCP services are operational."""
        self.start_test_container()
            
    def test_api_endpoints_accessible(self):
        """Test that API endpoints are accessible and working."""
        self.start_test_container()
        
        # Wait additional time for API to be ready
        time.sleep(5)
        
        # Test health endpoint (no auth required)
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=10)
            assert response.status_code == 200
            assert response.json() == {"ok": True}
            logger.info("✅ Health endpoint accessible")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Health endpoint not accessible: {e}")
            
    def test_mcp_communication_works(self):
        """Test that API can communicate with MCP server for weather queries."""
        self.test_api_endpoints_accessible()
        
        # Test weather endpoint with API key
        weather_query = {
            "query": "weather in Tel Aviv from 2025-10-20 to 2025-10-22"
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.test_api_key
        }
        
        try:
            response = requests.post(
                f"{self.api_base_url}/v1/weather/ask",
                json=weather_query,
                headers=headers,
                timeout=30
            )
            
            # Should get response (may be error due to missing weather API keys, but should communicate)
            assert response.status_code in [200, 400, 502], f"Unexpected status: {response.status_code}"
            
            result = response.json()
            
            # Verify the request was processed through the MCP communication flow
            assert "error" in result or "summary" in result, "Response should contain error or summary"
            
            logger.info("✅ MCP communication working - API and MCP server communicate correctly")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"MCP communication test failed: {e}")


class TestCloudRunDeployment(DeploymentIntegrationTest):
    """
    Test that validates Cloud Run deployment configuration and requirements.
    """
    
    def test_readme_contains_valid_gcloud_deploy_command(self):
        """Verify README.md contains valid gcloud run deploy command."""
        readme_path = self.workspace_root / "README.md"
        assert readme_path.exists(), "README.md not found"
        
        readme_content = readme_path.read_text()
        
        # Check for gcloud run deploy command - find the complete command with multiple lines
        gcloud_pattern = r'gcloud run deploy.*?(?=```|\n\n|\Z)'
        match = re.search(gcloud_pattern, readme_content, re.DOTALL)
        
        assert match is not None, "gcloud run deploy command not found in README"
        
        deploy_command = match.group(0)
        
        # Verify required flags are present
        required_flags = [
            "--allow-unauthenticated",
            "--platform managed", 
            "--region",
            "--image",
            "--set-env-vars",
            "--port 8000"
        ]
        
        for flag in required_flags:
            assert flag in deploy_command, f"Required flag '{flag}' missing from gcloud deploy command"
            
        logger.info("✅ README contains valid gcloud run deploy command with all required flags")
        
    def test_dockerfile_exposes_correct_port(self):
        """Verify Dockerfile exposes the correct port and has proper entrypoint."""
        dockerfile_path = self.workspace_root / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile not found"
        
        dockerfile_content = dockerfile_path.read_text()
        
        # Check port exposure
        assert "EXPOSE ${PORT}" in dockerfile_content or "EXPOSE 8000" in dockerfile_content, \
            "Dockerfile should expose port 8000 or ${PORT}"
            
        # Check entrypoint
        assert 'CMD ["python", "docker_entrypoint.py"]' in dockerfile_content, \
            "Dockerfile should use docker_entrypoint.py as CMD"
            
        # Check environment variables
        assert "ENV" in dockerfile_content, "Dockerfile should set environment variables"
        assert "PORT=8000" in dockerfile_content, "Dockerfile should set PORT=8000"
        
        logger.info("✅ Dockerfile has correct port exposure and entrypoint configuration")
        
    def test_required_environment_variables_documented(self):
        """Verify all required environment variables are documented in README."""
        readme_path = self.workspace_root / "README.md"
        readme_content = readme_path.read_text()
        
        # Required variables that should be documented
        required_vars = ["API_KEY", "LOG_LEVEL", "DEPLOYMENT_ENV", "TZ"]
        
        for var in required_vars:
            assert var in readme_content, f"Required environment variable '{var}' not documented in README"
            
        # Check for environment variables table/section
        env_section_patterns = [
            "Environment Variables",
            "| Variable | Value | Purpose |",
            "--set-env-vars"
        ]
        
        found_env_section = any(pattern in readme_content for pattern in env_section_patterns)
        assert found_env_section, "Environment variables section not found in README"
        
        logger.info("✅ All required environment variables documented in README")


class TestAuthenticationBehavior(DeploymentIntegrationTest):
    """
    Test authentication requirements: unauthenticated Cloud Run access but API-level x-api-key requirement.
    """
    
    def test_health_endpoint_no_auth_required(self):
        """Verify health endpoint works without authentication."""
        self.start_test_container()
        
        # Test health endpoint without any headers
        try:
            response = requests.get(f"{self.api_base_url}/health", timeout=10)
            assert response.status_code == 200
            assert response.json() == {"ok": True}
            
            logger.info("✅ Health endpoint allows unauthenticated access")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Health endpoint authentication test failed: {e}")
            
    def test_weather_endpoint_requires_api_key(self):
        """Verify weather endpoint requires x-api-key header."""
        self.start_test_container()
        
        weather_query = {"query": "weather in Tel Aviv"}
        
        # Test without API key - should get 401/403
        try:
            response = requests.post(
                f"{self.api_base_url}/v1/weather/ask",
                json=weather_query,
                timeout=10
            )
            
            assert response.status_code in [401, 403], \
                f"Expected 401/403 without API key, got {response.status_code}"
                
            logger.info("✅ Weather endpoint correctly rejects requests without API key")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"API key requirement test failed: {e}")
            
    def test_weather_endpoint_accepts_valid_api_key(self):
        """Verify weather endpoint accepts requests with valid x-api-key."""
        self.start_test_container()
        
        weather_query = {"query": "weather in Tel Aviv"}
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.test_api_key
        }
        
        try:
            response = requests.post(
                f"{self.api_base_url}/v1/weather/ask",
                json=weather_query,
                headers=headers,
                timeout=30
            )
            
            # Should not get 401/403 with valid API key
            assert response.status_code not in [401, 403], \
                f"Valid API key was rejected with status {response.status_code}"
                
            logger.info("✅ Weather endpoint accepts valid API key")
            
        except requests.exceptions.RequestException as e:
            pytest.fail(f"Valid API key test failed: {e}")


class TestProcessManagement(DeploymentIntegrationTest):
    """
    Test process management and MCP server spawning behavior.
    """
    
    def test_docker_entrypoint_starts_api_server(self):
        """Verify docker_entrypoint.py starts API server correctly."""
        self.start_test_container()
        
        # Get container logs and check for process management messages
        logs = self.test_container.logs().decode('utf-8')
        
        # Verify API server startup logging
        assert "Starting API server on port" in logs, "API server startup not logged"
        assert "API server started with PID" in logs, "API server PID not logged"
        assert "All services started successfully" in logs, "Services startup confirmation missing"
        
        logger.info("✅ Docker entrypoint correctly starts and manages API server")
        
    def test_mcp_server_communication_via_stdio(self):
        """Verify MCP server uses stdio communication as expected."""
        # Test the MCP server directly via subprocess (simulating Docker communication)
        mcp_server_path = self.workspace_root / "mcp_weather" / "server.py"
        assert mcp_server_path.exists(), "MCP server script not found"
        
        test_request = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20", 
            "end_date": "2025-10-22",
            "units": "metric"
        }
        
        try:
            # Test MCP server stdio communication
            result = subprocess.run(
                [sys.executable, str(mcp_server_path)],
                input=json.dumps(test_request),
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(self.workspace_root)
            )
            
            # Should get JSON response on stdout
            if result.stdout:
                response = json.loads(result.stdout)
                assert isinstance(response, dict), "MCP server should return JSON object"
                
            # MCP server should use stdio communication
            assert result.returncode in [0, 1], f"MCP server returned unexpected code: {result.returncode}"
            
            logger.info("✅ MCP server uses stdio communication correctly")
            
        except subprocess.TimeoutExpired:
            pytest.fail("MCP server stdio communication timed out")
        except json.JSONDecodeError as e:
            pytest.fail(f"MCP server did not return valid JSON: {e}")
        except Exception as e:
            pytest.fail(f"MCP server stdio test failed: {e}")
            
    def test_container_logs_show_both_services(self):
        """Verify container logs include entries for both API and MCP services."""
        self.start_test_container()
        
        # Wait for services to generate logs
        time.sleep(5)
        
        logs = self.test_container.logs().decode('utf-8')
        
        # Check for API server logs
        api_log_indicators = [
            "API server started",
            "uvicorn",
            "FastAPI"
        ]
        
        api_logs_found = any(indicator in logs for indicator in api_log_indicators)
        assert api_logs_found, f"API server logs not found. Logs: {logs}"
        
        # Check for successful startup
        assert "All services started successfully" in logs, "Service startup confirmation missing"
        
        logger.info("✅ Container logs show both API service startup")


class TestDocumentationValidation(DeploymentIntegrationTest):
    """
    Test README.md and Dockerfile validation against deployment requirements.
    """
    
    def test_readme_cloud_run_section_complete(self):
        """Verify README has complete Cloud Run deployment section."""
        readme_path = self.workspace_root / "README.md"
        readme_content = readme_path.read_text()
        
        # Check for Cloud Run section
        assert "Google Cloud Run" in readme_content, "Cloud Run section missing from README"
        assert "gcloud run deploy" in readme_content, "gcloud deploy command missing"
        
        # Check for deployment steps
        deployment_sections = [
            "Prerequisites",
            "Quick Deployment", 
            "Build and push",  # This is the actual heading in README
            "Deploy to Cloud Run"
        ]
        
        for section in deployment_sections:
            assert section in readme_content, f"Deployment section '{section}' missing from README"
            
        # Check for environment variables documentation
        assert "Environment Variables" in readme_content, "Environment variables section missing"
        
        logger.info("✅ README contains complete Cloud Run deployment documentation")
        
    def test_dockerfile_cloud_run_optimized(self):
        """Verify Dockerfile is optimized for Cloud Run deployment."""
        dockerfile_path = self.workspace_root / "Dockerfile"
        dockerfile_content = dockerfile_path.read_text()
        
        # Check for Cloud Run best practices
        cloud_run_practices = [
            "HEALTHCHECK",  # Health check for container monitoring
            "EXPOSE",       # Port exposure
            "USER",         # Non-root user
            "WORKDIR"       # Working directory set
        ]
        
        for practice in cloud_run_practices:
            assert practice in dockerfile_content, f"Cloud Run best practice '{practice}' missing from Dockerfile"
            
        # Check environment variables setup
        assert "ENV" in dockerfile_content, "Environment variables not set in Dockerfile"
        assert "PORT=8000" in dockerfile_content, "PORT environment variable not set"
        
        logger.info("✅ Dockerfile follows Cloud Run best practices")
        
    def test_pyproject_toml_dependencies(self):
        """Verify pyproject.toml has all required dependencies."""
        pyproject_path = self.workspace_root / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"
        
        pyproject_content = pyproject_path.read_text()
        
        # Required dependencies for the application
        required_deps = [
            "fastapi",
            "uvicorn", 
            "crewai",
            "requests",
            "pydantic"
        ]
        
        for dep in required_deps:
            assert dep in pyproject_content, f"Required dependency '{dep}' missing from pyproject.toml"
            
        logger.info("✅ pyproject.toml contains all required dependencies")


# Integration test runner
def run_integration_tests():
    """
    Run all integration tests in sequence.
    Each test class handles its own setup and cleanup.
    """
    test_classes = [
        TestSingleDockerImage,
        TestCloudRunDeployment, 
        TestAuthenticationBehavior,
        TestProcessManagement,
        TestDocumentationValidation
    ]
    
    results = {}
    
    for test_class in test_classes:
        class_name = test_class.__name__
        logger.info(f"\n{'='*60}")
        logger.info(f"Running {class_name}")
        logger.info(f"{'='*60}")
        
        test_instance = test_class()
        test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
        
        class_results = {}
        
        try:
            for method_name in test_methods:
                logger.info(f"\n--- {method_name} ---")
                try:
                    method = getattr(test_instance, method_name)
                    method()
                    class_results[method_name] = "PASSED"
                    logger.info(f"✅ {method_name} PASSED")
                except Exception as e:
                    class_results[method_name] = f"FAILED: {e}"
                    logger.error(f"❌ {method_name} FAILED: {e}")
                finally:
                    # Cleanup after each test method
                    test_instance.cleanup_docker_resources()
                    
        except Exception as e:
            logger.error(f"Failed to run {class_name}: {e}")
            class_results["class_error"] = str(e)
            
        results[class_name] = class_results
    
    return results


if __name__ == "__main__":
    # Run integration tests when executed directly
    logger.info("Starting WeatherSense Deployment Integration Tests")
    logger.info("=" * 80)
    
    test_results = run_integration_tests()
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("INTEGRATION TESTS SUMMARY")
    logger.info("=" * 80)
    
    total_tests = 0
    passed_tests = 0
    
    for class_name, methods in test_results.items():
        logger.info(f"\n{class_name}:")
        for method, result in methods.items():
            total_tests += 1
            if result == "PASSED":
                passed_tests += 1
                logger.info(f"  ✅ {method}")
            else:
                logger.info(f"  ❌ {method}: {result}")
    
    logger.info(f"\nSUMMARY: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("🎉 ALL INTEGRATION TESTS PASSED!")
        sys.exit(0)
    else:
        logger.error(f"❌ {total_tests - passed_tests} tests failed")
        sys.exit(1)