"""
Unit tests for MCP client subprocess communication.
"""
import pytest
import json
import subprocess
from unittest.mock import Mock, patch, MagicMock
from crew.mcp_client import MCPClient, fetch_weather_data


class TestMCPClient:
    def setup_method(self):
        """Setup test fixtures."""
        self.client = MCPClient(timeout=10)
    
    @patch('crew.mcp_client.subprocess.Popen')
    def test_call_weather_tool_success(self, mock_popen):
        """Test successful MCP tool call."""
        # Mock successful subprocess
        mock_process = Mock()
        mock_process.communicate.return_value = (
            json.dumps({
                "location": "Tel Aviv, IL",
                "latitude": 32.08,
                "longitude": 34.78,
                "units": "metric",
                "start_date": "2025-10-20",
                "end_date": "2025-10-24",
                "daily": [
                    {"date": "2025-10-20", "tmin": 20.0, "tmax": 28.0, "precip_mm": 0.0, "wind_max_kph": 15.0, "code": 1}
                ],
                "source": "open-meteo"
            }),
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = self.client.call_weather_tool(params)
        
        assert "error" not in result
        assert result["location"] == "Tel Aviv, IL"
        assert "mcp_duration_ms" in result
        assert len(result["daily"]) == 1
    
    @patch('crew.mcp_client.subprocess.Popen')
    def test_call_weather_tool_error_response(self, mock_popen):
        """Test MCP tool returning error response."""
        # Mock error response
        mock_process = Mock()
        mock_process.communicate.return_value = (
            json.dumps({
                "error": "range_too_large",
                "hint": "span must be <= 31 days"
            }),
            ""
        )
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-01",
            "end_date": "2025-12-01",
            "units": "metric"
        }
        
        result = self.client.call_weather_tool(params)
        
        assert "error" in result
        assert result["error"] == "range_too_large"
    
    @patch('crew.mcp_client.subprocess.Popen')
    def test_call_weather_tool_process_failure(self, mock_popen):
        """Test MCP process failure."""
        # Mock process failure
        mock_process = Mock()
        mock_process.communicate.return_value = ("", "Process failed")
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24"
        }
        
        result = self.client.call_weather_tool(params)
        
        assert "error" in result
        assert result["error"] == "mcp_process_failed"
    
    @patch('crew.mcp_client.subprocess.Popen')
    def test_call_weather_tool_timeout(self, mock_popen):
        """Test MCP tool timeout."""
        # Mock timeout
        mock_process = Mock()
        mock_process.communicate.side_effect = subprocess.TimeoutExpired("cmd", 10)
        mock_process.kill = Mock()
        mock_process.wait = Mock()
        mock_popen.return_value = mock_process
        
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24"
        }
        
        result = self.client.call_weather_tool(params)
        
        assert "error" in result
        assert result["error"] == "mcp_timeout"
        mock_process.kill.assert_called_once()
    
    @patch('crew.mcp_client.subprocess.Popen')
    def test_call_weather_tool_invalid_json(self, mock_popen):
        """Test MCP tool returning invalid JSON."""
        # Mock invalid JSON response
        mock_process = Mock()
        mock_process.communicate.return_value = ("invalid json", "")
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24"
        }
        
        result = self.client.call_weather_tool(params)
        
        assert "error" in result
        assert result["error"] == "invalid_mcp_response"
    
    def test_call_weather_tool_missing_params(self):
        """Test missing required parameters."""
        params = {"location": "Tel Aviv"}  # Missing dates
        
        result = self.client.call_weather_tool(params)
        
        assert "error" in result
        assert result["error"] == "missing_parameters"
    
    def test_call_weather_tool_adds_default_units(self):
        """Test that default units are added when missing."""
        with patch('crew.mcp_client.subprocess.Popen') as mock_popen:
            mock_process = Mock()
            mock_process.communicate.return_value = ('{"test": "response"}', "")
            mock_process.returncode = 0
            mock_popen.return_value = mock_process
            
            params = {
                "location": "Tel Aviv",
                "start_date": "2025-10-20",
                "end_date": "2025-10-24"
                # No units specified
            }
            
            self.client.call_weather_tool(params)
            
            # Check that the process was called with units added
            args, kwargs = mock_popen.call_args
            assert kwargs["stdin"] == subprocess.PIPE


class TestFetchWeatherData:
    """Test the fetch_weather_data function."""
    
    @patch('crew.mcp_client.MCPClient')
    def test_fetch_weather_data_success(self, mock_client_class):
        """Test successful weather data fetching."""
        # Mock MCP client
        mock_client = Mock()
        mock_client.call_weather_tool.return_value = {
            "location": "Tel Aviv, IL",
            "latitude": 32.08,
            "longitude": 34.78,
            "units": "metric",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "daily": [
                {"date": "2025-10-20", "tmin": 20.0, "tmax": 28.0, "precip_mm": 0.0, "wind_max_kph": 15.0, "code": 1}
            ],
            "source": "open-meteo",
            "mcp_duration_ms": 500
        }
        mock_client_class.return_value = mock_client
        
        parsed_params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = fetch_weather_data(parsed_params)
        
        assert "error" not in result
        assert "params" in result
        assert "weather_raw" in result
        assert result["params"]["location"] == "Tel Aviv, IL"
        assert result["mcp_duration_ms"] == 500
    
    @patch('crew.mcp_client.MCPClient')
    def test_fetch_weather_data_mcp_error(self, mock_client_class):
        """Test MCP error handling."""
        # Mock MCP client error
        mock_client = Mock()
        mock_client.call_weather_tool.return_value = {
            "error": "range_too_large",
            "hint": "span must be <= 31 days",
            "duration_ms": 100
        }
        mock_client_class.return_value = mock_client
        
        parsed_params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-01",
            "end_date": "2025-12-01",
            "units": "metric"
        }
        
        result = fetch_weather_data(parsed_params)
        
        assert "error" in result
        assert result["error"] == "range_too_large"
    
    def test_fetch_weather_data_previous_error(self):
        """Test handling previous task errors."""
        parsed_params = {
            "error": "missing_location",
            "hint": "Please specify a location"
        }
        
        result = fetch_weather_data(parsed_params)
        
        assert "error" in result
        assert result["error"] == "missing_location"
    
    @patch('crew.mcp_client.MCPClient')
    def test_fetch_weather_data_exception(self, mock_client_class):
        """Test exception handling."""
        # Mock exception
        mock_client_class.side_effect = Exception("Unexpected error")
        
        parsed_params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = fetch_weather_data(parsed_params)
        
        assert "error" in result
        assert result["error"] == "fetch_failed"


if __name__ == "__main__":
    pytest.main([__file__])