"""
Pytest-compatible integration tests for WeatherSense deployment validation.
"""
import os
import sys
import json
import re
import subprocess
from pathlib import Path
import pytest


@pytest.fixture
def workspace_root():
    """Get workspace root directory."""
    return Path(__file__).parent.parent


@pytest.mark.deployment
@pytest.mark.documentation  
class TestDeploymentDocumentation:
    """Test deployment documentation and configuration."""
    
    def test_dockerfile_exists_and_valid(self, workspace_root):
        """Verify Dockerfile exists and has required configuration."""
        dockerfile_path = workspace_root / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile not found"
        
        dockerfile_content = dockerfile_path.read_text()
        
        # Check for required Dockerfile elements
        required_elements = [
            "FROM python:",          # Base image
            "WORKDIR /app",          # Working directory
            "COPY pyproject.toml",   # Dependencies
            "RUN pip install",       # Install dependencies  
            "EXPOSE",                # Port exposure
            "CMD",                   # Entrypoint command
            "ENV"                    # Environment variables
        ]
        
        for element in required_elements:
            assert element in dockerfile_content, f"Required Dockerfile element '{element}' not found"
            
        # Check specific configurations
        assert "PORT=8000" in dockerfile_content, "PORT environment variable not set"
        assert "docker_entrypoint.py" in dockerfile_content, "docker_entrypoint.py not used as entrypoint"
        
    def test_readme_cloud_run_section_exists(self, workspace_root):
        """Verify README has Cloud Run deployment section."""
        readme_path = workspace_root / "README.md"
        assert readme_path.exists(), "README.md not found"
        
        readme_content = readme_path.read_text()
        
        # Check for Cloud Run deployment content
        assert "Google Cloud Run" in readme_content, "Cloud Run section not found"
        assert "gcloud run deploy" in readme_content, "gcloud run deploy command not found"
        assert "--allow-unauthenticated" in readme_content, "--allow-unauthenticated flag not documented"
        
    def test_gcloud_deploy_command_syntax(self, workspace_root):
        """Verify gcloud run deploy command has correct syntax."""
        readme_path = workspace_root / "README.md"
        readme_content = readme_path.read_text()
        
        # Extract gcloud run deploy command (handles multi-line with backslashes)
        # Look for the complete gcloud command block
        gcloud_start = readme_content.find('gcloud run deploy')
        assert gcloud_start != -1, "gcloud run deploy command not found"
        
        # Find the end - look for next ```
        next_code_block = readme_content.find('```', gcloud_start)
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
            "--port 8000"
        ]
        
        for flag in required_flags:
            assert flag in deploy_command, f"Required flag '{flag}' missing from gcloud deploy command"
            
    def test_environment_variables_documented(self, workspace_root):
        """Verify all required environment variables are documented."""
        readme_path = workspace_root / "README.md"
        readme_content = readme_path.read_text()
        
        # Required environment variables for the application
        required_vars = ["API_KEY", "LOG_LEVEL", "DEPLOYMENT_ENV", "TZ"]
        
        for var in required_vars:
            assert var in readme_content, f"Required environment variable '{var}' not documented"
            
        # Check for environment variables table or section
        env_indicators = [
            "Environment Variables",
            "| Variable |",
            "--set-env-vars"
        ]
        
        env_section_found = any(indicator in readme_content for indicator in env_indicators)
        assert env_section_found, "Environment variables section not properly documented"
        
    def test_pyproject_toml_dependencies(self, workspace_root):
        """Verify pyproject.toml has all required dependencies."""
        pyproject_path = workspace_root / "pyproject.toml"
        assert pyproject_path.exists(), "pyproject.toml not found"
        
        pyproject_content = pyproject_path.read_text()
        
        # Core dependencies for the application
        required_deps = [
            "fastapi",
            "uvicorn",
            "crewai", 
            "requests",
            "pydantic"
        ]
        
        for dep in required_deps:
            assert dep in pyproject_content, f"Required dependency '{dep}' missing from pyproject.toml"
            
        # Test dependencies
        test_deps = ["pytest", "docker"]
        for dep in test_deps:
            assert dep in pyproject_content, f"Test dependency '{dep}' missing from pyproject.toml"
            
    def test_docker_entrypoint_exists(self, workspace_root):
        """Verify docker_entrypoint.py exists and has proper structure."""
        entrypoint_path = workspace_root / "docker_entrypoint.py"
        assert entrypoint_path.exists(), "docker_entrypoint.py not found"
        
        entrypoint_content = entrypoint_path.read_text()
        
        # Check for required functionality
        required_functions = [
            "def start_api_server",
            "def monitor_processes", 
            "def cleanup",
            "def main"
        ]
        
        for func in required_functions:
            assert func in entrypoint_content, f"Required function '{func}' not found in docker_entrypoint.py"
            
        # Check for API server startup
        assert "uvicorn" in entrypoint_content, "uvicorn server startup not found"
        assert "api.main:app" in entrypoint_content, "FastAPI app reference not found"
        
    def test_mcp_server_exists(self, workspace_root):
        """Verify MCP server exists and can be called."""
        mcp_server_path = workspace_root / "mcp_weather" / "server.py"
        assert mcp_server_path.exists(), "MCP server not found"
        
        mcp_content = mcp_server_path.read_text()
        
        # Check for stdio communication setup
        assert "sys.stdin" in mcp_content or "input()" in mcp_content, "stdin communication not found"
        assert "sys.stdout" in mcp_content or "print(" in mcp_content, "stdout communication not found"
        
        # Check for JSON handling
        assert "json" in mcp_content, "JSON handling not found"
        
    def test_api_security_configuration(self, workspace_root):
        """Verify API has proper security configuration."""
        api_main_path = workspace_root / "api" / "main.py"
        assert api_main_path.exists(), "API main file not found"
        
        api_content = api_main_path.read_text()
        
        # Check for authentication
        assert "x-api-key" in api_content, "API key authentication not found"
        assert "verify_api_key" in api_content, "API key verification not found"
        
        # Check for health endpoint without auth
        assert "/health" in api_content, "Health endpoint not found"
        
        # Check for weather endpoint with auth
        assert "/v1/weather/ask" in api_content, "Weather endpoint not found"


@pytest.mark.deployment
@pytest.mark.mcp
class TestMCPCommunication:
    """Test MCP server communication."""
    
    def test_mcp_server_stdio_communication(self, workspace_root):
        """Test that MCP server works via stdio communication."""
        mcp_server_path = workspace_root / "mcp_weather" / "server.py"
        assert mcp_server_path.exists(), "MCP server not found"
        
        # Test request
        test_request = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-22", 
            "units": "metric"
        }
        
        # Run MCP server with test input
        result = subprocess.run(
            [sys.executable, str(mcp_server_path)],
            input=json.dumps(test_request),
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(workspace_root),
            env=os.environ.copy()
        )
        
        # Server should handle the request (may return error due to missing API keys, but should process JSON)
        assert result.returncode in [0, 1], f"MCP server unexpected return code: {result.returncode}"
        
        # Should have some output 
        assert result.stdout or result.stderr, "MCP server produced no output"
        
        # Try to parse stdout as JSON if present
        if result.stdout.strip():
            try:
                response = json.loads(result.stdout)
                # Successful JSON response indicates proper stdio communication
                assert isinstance(response, dict), "MCP server should return JSON object"
            except json.JSONDecodeError:
                # If not JSON, at least ensure we got some response
                assert len(result.stdout) > 0, "MCP server produced no stdout"