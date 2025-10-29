"""
CrewAI Task B - MCP client for subprocess communication.
"""
import subprocess
import json
import time
import logging
import os
import sys
from typing import Dict, Any, Tuple, Optional


logger = logging.getLogger(__name__)

# Global persistent MCP process for Docker environment
_persistent_mcp_process: Optional[subprocess.Popen] = None


class MCPClient:
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.mcp_script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "mcp_weather", 
            "server.py"
        )
        self.is_docker_env = os.getenv("DEPLOYMENT_ENV") == "docker"
    
    def call_weather_tool(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call the MCP weather tool via subprocess.
        Uses persistent process in Docker, subprocess for local development.
        """
        if self.is_docker_env:
            return self._call_persistent_process(params)
        else:
            return self._call_subprocess(params)
    
    def _call_persistent_process(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call weather tool using persistent MCP process (Docker mode)."""
        global _persistent_mcp_process
        start_time = time.time()
        
        try:
            # Validate required parameters
            required_params = ["location", "start_date", "end_date"]
            for param in required_params:
                if param not in params:
                    return {
                        "error": "missing_parameters",
                        "hint": f"Missing required parameter: {param}"
                    }
            
            # Ensure units parameter
            if "units" not in params:
                params["units"] = "metric"
            
            # Check if persistent process is available
            if _persistent_mcp_process is None or _persistent_mcp_process.poll() is not None:
                logger.error("Persistent MCP process not available")
                return {
                    "error": "mcp_process_unavailable",
                    "hint": "MCP server process is not running"
                }
            
            # Send request to persistent process
            input_json = json.dumps(params) + "\n"
            _persistent_mcp_process.stdin.write(input_json)
            _persistent_mcp_process.stdin.flush()
            
            # Read response with timeout
            response_line = _persistent_mcp_process.stdout.readline()
            if not response_line:
                logger.error("No response from persistent MCP process")
                return {
                    "error": "mcp_no_response",
                    "hint": "MCP server did not respond"
                }
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Parse response
            try:
                response = json.loads(response_line.strip())
                
                # Log successful call
                logger.info(f"MCP persistent call completed in {duration_ms}ms")
                
                # Add timing information
                if "error" not in response:
                    response["mcp_duration_ms"] = duration_ms
                
                return response
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse MCP response: {e}")
                return {
                    "error": "invalid_mcp_response",
                    "hint": f"MCP tool returned invalid JSON: {e}",
                    "duration_ms": duration_ms
                }
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Unexpected error calling persistent MCP tool: {e}")
            return {
                "error": "mcp_call_failed",
                "hint": f"Failed to call MCP tool: {str(e)}",
                "duration_ms": duration_ms
            }
    
    def _call_subprocess(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call weather tool using subprocess (local development mode)."""
        start_time = time.time()
        
        try:
            # Validate required parameters
            required_params = ["location", "start_date", "end_date"]
            for param in required_params:
                if param not in params:
                    return {
                        "error": "missing_parameters",
                        "hint": f"Missing required parameter: {param}"
                    }
            
            # Ensure units parameter
            if "units" not in params:
                params["units"] = "metric"
            
            # Prepare the subprocess command
            python_exe = sys.executable
            cmd = [python_exe, self.mcp_script_path]
            
            # Start the subprocess
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=os.path.dirname(self.mcp_script_path)
            )
            
            # Send input and get output
            input_json = json.dumps(params)
            stdout, stderr = proc.communicate(input=input_json, timeout=self.timeout)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Check return code
            if proc.returncode != 0:
                logger.error(f"MCP process failed with code {proc.returncode}: {stderr}")
                return {
                    "error": "mcp_process_failed",
                    "hint": f"MCP tool failed: {stderr}",
                    "duration_ms": duration_ms
                }
            
            # Parse response
            try:
                response = json.loads(stdout)
                
                # Log successful call
                logger.info(f"MCP subprocess call completed in {duration_ms}ms")
                
                # Add timing information
                if "error" not in response:
                    response["mcp_duration_ms"] = duration_ms
                
                return response
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse MCP response: {e}")
                return {
                    "error": "invalid_mcp_response",
                    "hint": f"MCP tool returned invalid JSON: {e}",
                    "duration_ms": duration_ms
                }
        
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"MCP call timed out after {self.timeout}s")
            
            # Kill the process
            try:
                proc.kill()
                proc.wait()
            except:
                pass
            
            return {
                "error": "mcp_timeout",
                "hint": f"MCP tool timed out after {self.timeout} seconds",
                "duration_ms": duration_ms
            }
        
        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"MCP script not found at {self.mcp_script_path}")
            return {
                "error": "mcp_script_not_found",
                "hint": f"MCP script not found at {self.mcp_script_path}",
                "duration_ms": duration_ms
            }
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Unexpected error calling MCP tool: {e}")
            return {
                "error": "mcp_call_failed",
                "hint": f"Failed to call MCP tool: {str(e)}",
                "duration_ms": duration_ms
            }
            try:
                proc.kill()
                proc.wait()
            except:
                pass
            
            return {
                "error": "mcp_timeout",
                "hint": f"MCP tool timed out after {self.timeout} seconds",
                "duration_ms": duration_ms
            }
        
        except FileNotFoundError:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"MCP script not found at {self.mcp_script_path}")
            return {
                "error": "mcp_script_not_found",
                "hint": f"MCP script not found at {self.mcp_script_path}",
                "duration_ms": duration_ms
            }
        
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Unexpected error calling MCP tool: {e}")
            return {
                "error": "mcp_call_failed",
                "hint": f"Failed to call MCP tool: {str(e)}",
                "duration_ms": duration_ms
            }


def start_persistent_mcp_server() -> bool:
    """Start persistent MCP server process (Docker mode only)."""
    global _persistent_mcp_process
    
    if not os.getenv("DEPLOYMENT_ENV") == "docker":
        logger.info("Not in Docker environment, skipping persistent MCP server startup")
        return True
    
    if _persistent_mcp_process is not None and _persistent_mcp_process.poll() is None:
        logger.info("Persistent MCP server already running")
        return True
    
    try:
        mcp_script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            "mcp_weather", 
            "server.py"
        )
        
        python_exe = sys.executable
        cmd = [python_exe, mcp_script_path, "--persistent"]
        
        logger.info(f"Starting persistent MCP server: {' '.join(cmd)}")
        
        _persistent_mcp_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
            cwd=os.path.dirname(mcp_script_path)
        )
        
        # Wait a moment for the process to start
        time.sleep(0.5)
        
        if _persistent_mcp_process.poll() is None:
            logger.info(f"Persistent MCP server started with PID {_persistent_mcp_process.pid}")
            return True
        else:
            logger.error("Persistent MCP server failed to start")
            return False
            
    except Exception as e:
        logger.error(f"Failed to start persistent MCP server: {e}")
        return False


def stop_persistent_mcp_server():
    """Stop persistent MCP server process."""
    global _persistent_mcp_process
    
    if _persistent_mcp_process is not None:
        try:
            _persistent_mcp_process.terminate()
            try:
                _persistent_mcp_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _persistent_mcp_process.kill()
                _persistent_mcp_process.wait()
            
            logger.info("Persistent MCP server stopped")
        except Exception as e:
            logger.error(f"Error stopping persistent MCP server: {e}")
        finally:
            _persistent_mcp_process = None


def fetch_weather_data(parsed_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    CrewAI Task B - Fetch weather data using MCP tool.
    """
    # Check if previous task failed
    if "error" in parsed_params:
        return parsed_params
    
    try:
        # Extract parameters from Task A
        mcp_params = {
            "location": parsed_params.get("location"),
            "start_date": parsed_params.get("start_date"),
            "end_date": parsed_params.get("end_date"),
            "units": parsed_params.get("units", "metric")
        }
        
        # Initialize MCP client
        client = MCPClient()
        
        # Call MCP tool
        weather_response = client.call_weather_tool(mcp_params)
        
        # Handle MCP errors
        if "error" in weather_response:
            return {
                "error": weather_response["error"],
                "hint": weather_response.get("hint", "MCP tool error"),
                "mcp_duration_ms": weather_response.get("duration_ms", 0)
            }
        
        # Combine parameters with weather data
        result = {
            "params": {
                "location": weather_response.get("location", mcp_params["location"]),
                "start_date": mcp_params["start_date"],
                "end_date": mcp_params["end_date"],
                "units": mcp_params["units"]
            },
            "weather_raw": weather_response,
            "mcp_duration_ms": weather_response.get("mcp_duration_ms", 0)
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Task B error: {e}")
        return {
            "error": "fetch_failed",
            "hint": f"Failed to fetch weather data: {str(e)}"
        }