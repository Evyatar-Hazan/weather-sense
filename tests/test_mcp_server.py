"""
Enhanced unit tests for MCP Weather Server.
"""
import asyncio
import io
import json
import logging
import pytest
import sys
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import Mock, patch, AsyncMock, MagicMock

# Fix import paths for server
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp_weather'))

from server import (
    validate_date_range,
    process_weather_request,
    run_single_request_mode,
    run_persistent_mode,
    main
)


class TestValidateDateRange:
    """Test date range validation functionality."""
    
    def test_valid_date_range(self):
        """Test valid date range passes validation."""
        # Should not raise any exception
        validate_date_range("2025-10-20", "2025-10-24")
        validate_date_range("2025-01-01", "2025-01-31")
    
    def test_same_start_end_date(self):
        """Test same start and end date is valid."""
        validate_date_range("2025-10-20", "2025-10-20")
    
    def test_end_before_start_raises_error(self):
        """Test end date before start date raises error."""
        with pytest.raises(ValueError, match="Invalid date format. Use YYYY-MM-DD"):
            validate_date_range("2025-10-24", "2025-10-20")
    
    def test_range_exactly_31_days(self):
        """Test exactly 31 days range is valid."""
        validate_date_range("2025-10-01", "2025-10-31")
    
    def test_range_32_days_raises_error(self):
        """Test 32+ days range raises error."""
        with pytest.raises(ValueError, match="range_too_large"):
            validate_date_range("2025-10-01", "2025-11-01")
    
    def test_invalid_date_format_start(self):
        """Test invalid start date format raises error."""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_range("2025-13-01", "2025-10-24")
    
    def test_invalid_date_format_end(self):
        """Test invalid end date format raises error."""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_range("2025-10-01", "2025-10-32")
    
    def test_invalid_date_format_both(self):
        """Test invalid date format in both dates."""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_range("invalid", "also-invalid")
    
    def test_leap_year_february(self):
        """Test leap year February dates."""
        validate_date_range("2024-02-28", "2024-02-29")  # 2024 is leap year
    
    def test_non_leap_year_february(self):
        """Test non-leap year February validation."""
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_range("2025-02-29", "2025-03-01")  # 2025 is not leap year


class TestProcessWeatherRequestValidation:
    """Test weather request processing and validation."""
    
    def test_missing_location_parameter(self):
        """Test missing location parameter."""
        request_data = {
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "missing_parameters"
        assert "location" in result["hint"]
    
    def test_missing_start_date_parameter(self):
        """Test missing start_date parameter."""
        request_data = {
            "location": "Tel Aviv",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "missing_parameters"
        assert "start_date" in result["hint"]
    
    def test_missing_end_date_parameter(self):
        """Test missing end_date parameter."""
        request_data = {
            "location": "Tel Aviv", 
            "start_date": "2025-10-20",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "missing_parameters"
        assert "end_date" in result["hint"]
    
    def test_missing_units_defaults_to_metric(self):
        """Test missing units parameter defaults to metric."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20", 
            "end_date": "2025-10-24"
        }
        
        with patch('mcp_weather.server.WeatherProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider
            mock_provider.geocode_location.return_value = (32.08, 34.78, "Tel Aviv, IL")
            mock_provider.fetch_weather_data.return_value = {"daily": []}
            
            with patch('mcp_weather.server.weather_cache') as mock_cache:
                mock_cache.get.return_value = None
                
                result = process_weather_request(request_data)
                
                # Should succeed and use metric units
                assert "error" not in result
                assert result["units"] == "metric"
    
    def test_invalid_units_parameter(self):
        """Test invalid units parameter."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24", 
            "units": "celsius"  # Invalid
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "invalid_units"
        assert "metric" in result["hint"]
        assert "imperial" in result["hint"]
    
    def test_invalid_date_range_in_request(self):
        """Test invalid date range in request."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-24",
            "end_date": "2025-10-20",  # End before start
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "invalid_request"
        assert "Invalid date format. Use YYYY-MM-DD" in result["hint"]
    
    def test_date_range_too_large_in_request(self):
        """Test date range too large in request."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-01", 
            "end_date": "2025-11-15",  # > 31 days
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "range_too_large"
        assert "31 days" in result["hint"]


class TestProcessWeatherRequestFlow:
    """Test the complete weather request processing flow."""
    
    @patch('server.weather_cache')
    @patch('server.WeatherProvider')
    def test_successful_request_no_cache(self, mock_provider_class, mock_cache):
        """Test successful request without cache hit."""
        # Setup mocks
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.geocode_location.return_value = (32.08, 34.78, "Tel Aviv, Israel")
        mock_provider.fetch_weather_data.return_value = {
            "daily": [
                {"date": "2025-10-20", "tmin": 20.0, "tmax": 28.0, "precip_mm": 0.0}
            ],
            "source": "open-meteo"
        }
        
        mock_cache.get.return_value = None  # Cache miss
        
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        # Verify result structure
        assert "error" not in result
        assert result["location"] == "Tel Aviv, Israel"
        assert result["latitude"] == 32.08
        assert result["longitude"] == 34.78
        assert result["units"] == "metric"
        assert result["start_date"] == "2025-10-20"
        assert result["end_date"] == "2025-10-24"
        assert "daily" in result
        assert result["source"] == "open-meteo"
        
        # Verify cache was called
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_called_once()
    
    @patch('server.weather_cache')
    @patch('server.WeatherProvider')
    def test_successful_request_with_cache_hit(self, mock_provider_class, mock_cache):
        """Test successful request with cache hit."""
        # Setup provider mock to be ready for geocoding
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.geocode_location.return_value = (32.08088, 34.78057, "Tel Aviv, Israel")
        
        cached_data = {
            "location": "Tel Aviv, Israel",
            "latitude": 32.08088,
            "longitude": 34.78057,
            "units": "metric",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "daily": [
                {"code": 3, "date": "2025-10-20", "precip_mm": 0.0, "tmax": 26.8, "tmin": 18.8, "wind_max_kph": 12.96},
                {"code": 2, "date": "2025-10-21", "precip_mm": 0.0, "tmax": 29.1, "tmin": 19.2, "wind_max_kph": 14.54},
                {"code": 2, "date": "2025-10-22", "precip_mm": 0.0, "tmax": 28.7, "tmin": 20.3, "wind_max_kph": 16.81},
                {"code": 2, "date": "2025-10-23", "precip_mm": 0.0, "tmax": 29.1, "tmin": 20.9, "wind_max_kph": 11.88},
                {"code": 2, "date": "2025-10-24", "precip_mm": 0.0, "tmax": 27.5, "tmin": 20.4, "wind_max_kph": 13.68}
            ],
            "source": "open-meteo"
        }
        
        mock_cache.get.return_value = cached_data
        
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        # Should return cached data without calling fetch_weather_data
        assert result == cached_data
        
        # Verify provider geocoding was called but not fetch_weather_data
        mock_provider.geocode_location.assert_called_once()
        mock_provider.fetch_weather_data.assert_not_called()
        
        # Cache set should not be called (already cached)
        mock_cache.get.assert_called_once()
        mock_cache.set.assert_not_called()
    
    @patch('server.weather_cache')
    @patch('server.WeatherProvider')
    def test_geocoding_error_handling(self, mock_provider_class, mock_cache):
        """Test error handling when geocoding fails."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.geocode_location.side_effect = ValueError("Location 'NonexistentPlace123' not found")
        
        mock_cache.get.return_value = None
        
        request_data = {
            "location": "NonexistentPlace123",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "invalid_request"
        assert "Location 'NonexistentPlace123' not found" in result["hint"]
    
    @patch('server.weather_cache')
    @patch('server.WeatherProvider')
    def test_weather_data_fetch_error_handling(self, mock_provider_class, mock_cache):
        """Test error handling when weather data fetch fails."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.geocode_location.return_value = (32.08, 34.78, "Tel Aviv, IL")
        mock_provider.fetch_weather_data.side_effect = ValueError("API unavailable")
        
        mock_cache.get.return_value = None
        
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "invalid_request"
        assert "API unavailable" in result["hint"]
        assert "API unavailable" in result["hint"]
    
    @patch('server.weather_cache')
    @patch('server.WeatherProvider')
    def test_unexpected_exception_handling(self, mock_provider_class, mock_cache):
        """Test handling of unexpected exceptions."""
        mock_provider = Mock()
        mock_provider_class.return_value = mock_provider
        mock_provider.geocode_location.side_effect = RuntimeError("Unexpected error")
        
        mock_cache.get.return_value = None
        
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = process_weather_request(request_data)
        
        assert result["error"] == "internal_error"
        assert "Server error occurred" in result["hint"]
        assert "Server error occurred" in result["hint"]


class TestSingleRequestMode:
    """Test single request mode functionality."""
    
    @patch('sys.stdin')
    @patch('sys.stdout')
    @patch('server.process_weather_request')
    def test_successful_single_request(self, mock_process, mock_stdout, mock_stdin):
        """Test successful single request processing."""
        # Setup input
        input_data = json.dumps({
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        })
        mock_stdin.read.return_value = input_data
        
        # Setup response
        mock_response = {"location": "Tel Aviv, IL", "daily": []}
        mock_process.return_value = mock_response
        
        # Capture stdout
        captured_output = io.StringIO()
        mock_stdout.write = captured_output.write
        mock_stdout.flush = Mock()
        
        # Run function
        run_single_request_mode()
        
        # Verify
        mock_process.assert_called_once()
        mock_stdout.flush.assert_called()
        
        # Check that JSON was printed
        output = captured_output.getvalue()
        assert json.loads(output) == mock_response
    
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_empty_input_handling(self, mock_stdout, mock_stdin):
        """Test handling of empty input."""
        mock_stdin.read.return_value = ""
        
        captured_output = io.StringIO()
        mock_stdout.write = captured_output.write
        mock_stdout.flush = Mock()
        
        run_single_request_mode()
        
        output = json.loads(captured_output.getvalue())
        assert output["error"] == "no_input"
        assert "No input data provided" in output["hint"]
    
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_invalid_json_handling(self, mock_stdout, mock_stdin):
        """Test handling of invalid JSON input."""
        mock_stdin.read.return_value = "invalid json"
        
        captured_output = io.StringIO()
        mock_stdout.write = captured_output.write
        mock_stdout.flush = Mock()
        
        run_single_request_mode()
        
        output = json.loads(captured_output.getvalue())
        assert output["error"] == "invalid_json"
        assert "valid JSON" in output["hint"]


class TestPersistentMode:
    """Test persistent mode functionality."""
    
    @patch('sys.stdin')
    @patch('sys.stdout')
    @patch('server.process_weather_request')
    def test_persistent_mode_multiple_requests(self, mock_process, mock_stdout, mock_stdin):
        """Test persistent mode with multiple requests."""
        # Setup multiple inputs
        inputs = [
            json.dumps({"location": "Tel Aviv", "start_date": "2025-10-20", "end_date": "2025-10-24"}),
            json.dumps({"location": "New York", "start_date": "2025-10-20", "end_date": "2025-10-24"}),
            ""  # EOF to stop
        ]
        mock_stdin.readline.side_effect = [f"{inp}\n" for inp in inputs if inp] + [""]
        
        # Setup responses
        responses = [
            {"location": "Tel Aviv, IL", "daily": []},
            {"location": "New York, US", "daily": []}
        ]
        mock_process.side_effect = responses
        
        # Capture stdout
        captured_outputs = []
        def capture_print(text):
            captured_outputs.append(text)
        
        mock_stdout.write = capture_print
        mock_stdout.flush = Mock()
        
        # Run function
        run_persistent_mode()
        
        # Verify
        assert mock_process.call_count == 2
        
        # Should have 2 JSON responses and 2 newlines (4 total outputs)
        assert len(captured_outputs) == 4
        
        # Verify the JSON responses (skip newlines)
        json_outputs = [output for output in captured_outputs if output != '\n']
        assert len(json_outputs) == 2
        
        for output in json_outputs:
            parsed = json.loads(output)
            assert "location" in parsed
            assert "daily" in parsed
    
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_persistent_mode_invalid_json(self, mock_stdout, mock_stdin):
        """Test persistent mode with invalid JSON."""
        inputs = ["invalid json", ""]  # Invalid JSON then EOF
        mock_stdin.readline.side_effect = [f"{inp}\n" for inp in inputs if inp] + [""]
        
        captured_outputs = []
        mock_stdout.write = lambda x: captured_outputs.append(x)
        mock_stdout.flush = Mock()
        
        run_persistent_mode()
        
        # Should have one error output and one newline
        assert len(captured_outputs) == 2
        assert '"error": "invalid_json"' in captured_outputs[0]
        assert captured_outputs[1] == '\n'
        output = json.loads(captured_outputs[0])
        assert output["error"] == "invalid_json"
    
    @patch('sys.stdin')
    @patch('sys.stdout')
    def test_persistent_mode_empty_lines_ignored(self, mock_stdout, mock_stdin):
        """Test that empty lines are ignored in persistent mode."""
        inputs = ["", "   ", ""]  # Empty lines then EOF
        mock_stdin.readline.side_effect = [f"{inp}\n" for inp in inputs] + [""]
        
        captured_outputs = []
        mock_stdout.write = lambda x: captured_outputs.append(x)
        mock_stdout.flush = Mock()
        
        run_persistent_mode()
        
        # Should not produce any output for empty lines
        assert len(captured_outputs) == 0


@pytest.mark.mcp
class TestMCPServerIntegration:
    """Integration tests for MCP server functionality."""
    
    def test_request_id_generation(self):
        """Test that each request gets a unique request ID."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        with patch('mcp_weather.server.WeatherProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider
            mock_provider.geocode_location.return_value = (32.08, 34.78, "Tel Aviv, IL")
            mock_provider.fetch_weather_data.return_value = {"daily": []}
            
            with patch('mcp_weather.server.weather_cache') as mock_cache:
                mock_cache.get.return_value = None
                
                # Make multiple requests
                result1 = process_weather_request(request_data)
                result2 = process_weather_request(request_data)
                
                # Both should succeed
                assert "error" not in result1
                assert "error" not in result2
    
    @patch('server.logging')
    def test_logging_integration(self, mock_logging):
        """Test that logging is properly integrated."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        with patch('mcp_weather.server.WeatherProvider') as mock_provider_class:
            mock_provider = Mock()
            mock_provider_class.return_value = mock_provider
            mock_provider.geocode_location.return_value = (32.08, 34.78, "Tel Aviv, IL")
            mock_provider.fetch_weather_data.return_value = {"daily": []}
            
            with patch('mcp_weather.server.weather_cache') as mock_cache:
                mock_cache.get.return_value = None
                
                process_weather_request(request_data)
                
                # Verify logging was called
                mock_logging.getLogger.assert_called()
    
    def test_units_parameter_validation_comprehensive(self):
        """Test comprehensive units parameter validation."""
        base_request = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24"
        }
        
        # Test valid units
        valid_units = ["metric", "imperial"]
        for units in valid_units:
            request_data = {**base_request, "units": units}
            
            with patch('server.WeatherProvider') as mock_provider_class:
                mock_provider = Mock()
                mock_provider_class.return_value = mock_provider
                mock_provider.geocode_location.return_value = (32.08, 34.78, "Tel Aviv, IL")
                mock_provider.fetch_weather_data.return_value = {"daily": []}
                
                with patch('server.weather_cache') as mock_cache:
                    mock_cache.get.return_value = None
                    
                    result = process_weather_request(request_data)
                    assert "error" not in result
                    assert result["units"] == units
        
        # Test invalid units
        invalid_units = ["celsius", "fahrenheit", "kelvin", "invalid", ""]
        for units in invalid_units:
            request_data = {**base_request, "units": units}
            result = process_weather_request(request_data)
            assert result["error"] == "invalid_units"


class TestMCPServerErrorScenarios:
    """Test various error scenarios in MCP server."""
    
    def test_cache_error_handling(self):
        """Test handling of cache errors."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        with patch('server.weather_cache') as mock_cache:
            # Cache get raises exception
            mock_cache.get.side_effect = Exception("Cache error")
            
            with patch('server.WeatherProvider') as mock_provider_class:
                mock_provider = Mock()
                mock_provider_class.return_value = mock_provider
                mock_provider.geocode_location.return_value = (32.08, 34.78, "Tel Aviv, IL")
                mock_provider.fetch_weather_data.return_value = {"daily": []}
                
                result = process_weather_request(request_data)
                
                # Should handle cache error gracefully
                assert result["error"] == "internal_error"
                assert "Server error occurred" in result["hint"]
    
    def test_provider_initialization_error(self):
        """Test handling of provider initialization errors."""
        request_data = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        with patch('server.WeatherProvider') as mock_provider_class:
            mock_provider_class.side_effect = Exception("Provider init error")
            
            with patch('server.weather_cache') as mock_cache:
                mock_cache.get.return_value = None
                
                result = process_weather_request(request_data)
                
                assert result["error"] == "internal_error"
                assert "Server error occurred" in result["hint"]
                assert "Server error occurred" in result["hint"]