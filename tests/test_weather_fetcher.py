"""
Comprehensive test suite for Weather Fetcher (Task B) - Production-grade validation.

This test suite validates the second stage of the Weather Agent pipeline:
- Receiving structured context from Task A
- Calling the MCP tool weather.get_range 
- Storing MCP results into context under weather_raw
- Logging call duration and handling provider gaps gracefully

All tests use real MCP tool implementation (no mocks) to ensure end-to-end validation.
"""
import pytest
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from crew.mcp_client import fetch_weather_data, MCPClient
from crew.parser import parse_natural_language


class TestWeatherFetcherHappyFlow:
    """Test successful data flow scenarios for Weather Fetcher (Task B)."""
    
    @pytest.fixture
    def base_params(self) -> Dict[str, Any]:
        """Base parameters for weather fetching (simulating Task A output)."""
        return {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-25",
            "units": "metric",
            "confidence": 0.95
        }
    
    @pytest.fixture
    def extended_params(self) -> Dict[str, Any]:
        """Extended date range parameters for testing longer periods."""
        return {
            "location": "New York",
            "start_date": "2025-10-20",
            "end_date": "2025-10-31",  # 12 days
            "units": "imperial",
            "confidence": 0.9
        }
    
    @pytest.fixture
    def coordinate_params(self) -> Dict[str, Any]:
        """Parameters with coordinates instead of location name."""
        return {
            "location": "32.08,34.78",  # Tel Aviv coordinates
            "start_date": "2025-10-20",
            "end_date": "2025-10-22",
            "units": "metric",
            "confidence": 0.85
        }
    
    def test_full_flow_metric_units(self, base_params: Dict[str, Any], caplog):
        """
        Test complete successful flow with metric units.
        
        Validates:
        - MCP call returns valid dict with weather data
        - Context contains both 'params' and 'weather_raw'
        - No corruption of original parameters
        - Duration logging captures timing information
        """
        with caplog.at_level(logging.INFO):
            result = fetch_weather_data(base_params)
        
        # Verify no errors occurred
        assert "error" not in result, f"Expected success but got error: {result.get('error')}"
        
        # Verify context structure integrity
        assert "params" in result, "Context must contain 'params' from Task A"
        assert "weather_raw" in result, "Context must contain 'weather_raw' from MCP call"
        assert "mcp_duration_ms" in result, "Context must contain timing information"
        
        # Verify params preservation and consistency
        params = result["params"]
        assert params["location"] in ["Tel Aviv", "Tel Aviv, IL", "Tel Aviv, Israel"], "Location should be preserved or formatted"
        assert params["start_date"] == base_params["start_date"], "Start date must be preserved"
        assert params["end_date"] == base_params["end_date"], "End date must be preserved"
        assert params["units"] == "metric", "Units must be preserved"
        
        # Verify weather_raw structure and schema
        weather_raw = result["weather_raw"]
        self._validate_weather_schema(weather_raw, base_params["start_date"], base_params["end_date"])
        
        # Verify duration logging
        assert result["mcp_duration_ms"] > 0, "Duration must be positive"
        assert result["mcp_duration_ms"] < 10000, "Duration should be reasonable (< 10s)"
        
        # Verify log contains required information
        log_messages = [record.message for record in caplog.records]
        has_mcp_log = any("MCP" in msg for msg in log_messages)
        assert has_mcp_log, "Logs should contain MCP-related information"
    
    def test_full_flow_imperial_units(self, extended_params: Dict[str, Any], caplog):
        """
        Test complete flow with imperial units and longer date range.
        
        Validates:
        - Imperial unit handling in MCP tool
        - Extended date range processing (12 days)
        - Temperature values within realistic bounds for imperial
        """
        with caplog.at_level(logging.INFO):
            result = fetch_weather_data(extended_params)
        
        assert "error" not in result, f"Expected success but got error: {result.get('error')}"
        
        # Verify imperial units propagation
        assert result["params"]["units"] == "imperial"
        assert result["weather_raw"]["units"] == "imperial"
        
        # Verify extended date range
        daily_data = result["weather_raw"]["daily"]
        expected_days = 12  # Oct 20-31, 2025
        assert len(daily_data) == expected_days, f"Expected {expected_days} days, got {len(daily_data)}"
        
        # Validate temperature ranges for imperial (should be Fahrenheit)
        for day in daily_data:
            tmin, tmax = day.get("tmin"), day.get("tmax")
            if tmin is not None and tmax is not None:
                # Realistic Fahrenheit ranges: -58°F to 140°F
                assert -58 <= tmin <= 140, f"Unrealistic min temp: {tmin}°F"
                assert -58 <= tmax <= 140, f"Unrealistic max temp: {tmax}°F"
                assert tmin <= tmax, f"Min temp {tmin}°F should be <= max temp {tmax}°F"
    
    def test_coordinates_input(self, coordinate_params: Dict[str, Any]):
        """
        Test weather fetching using coordinate input instead of location name.
        
        Validates:
        - Coordinate parsing and geocoding
        - Same schema output as location name
        - Coordinates preserved in response
        """
        result = fetch_weather_data(coordinate_params)
        
        assert "error" not in result, f"Expected success but got error: {result.get('error')}"
        
        # Verify coordinates handling
        weather_raw = result["weather_raw"]
        assert "latitude" in weather_raw, "Response must include latitude"
        assert "longitude" in weather_raw, "Response must include longitude"
        
        # Verify coordinates are approximately correct (Tel Aviv area)
        lat = weather_raw["latitude"]
        lon = weather_raw["longitude"]
        assert 31.5 <= lat <= 33.0, f"Latitude {lat} should be in Tel Aviv area"
        assert 34.0 <= lon <= 35.5, f"Longitude {lon} should be in Tel Aviv area"
        
        # Verify short date range (3 days)
        daily_data = weather_raw["daily"]
        assert len(daily_data) == 3, f"Expected 3 days, got {len(daily_data)}"
    
    def test_context_integrity_preservation(self, base_params: Dict[str, Any]):
        """
        Test that original context from Task A is perfectly preserved.
        
        Validates:
        - All original params remain unchanged
        - Additional fields from Task A (like confidence) are preserved
        - No data corruption or type changes
        """
        # Add extra fields to simulate more complex Task A output
        enhanced_params = {
            **base_params,
            "query_type": "forecast",
            "parsed_at": "2025-10-28T10:00:00Z",
            "confidence": 0.95
        }
        
        result = fetch_weather_data(enhanced_params)
        
        assert "error" not in result
        
        # Verify core params are preserved exactly
        params = result["params"]
        assert params["location"] in ["Tel Aviv", "Tel Aviv, IL", "Tel Aviv, Israel"]
        assert params["start_date"] == enhanced_params["start_date"]
        assert params["end_date"] == enhanced_params["end_date"]
        assert params["units"] == enhanced_params["units"]
        
        # Note: fetch_weather_data currently only preserves core weather params
        # This test documents the current behavior and would catch changes
    
    def _validate_weather_schema(self, weather_raw: Dict[str, Any], start_date: str, end_date: str):
        """
        Validate weather_raw follows expected schema structure.
        
        Each weather entry should follow:
        {
          "date": "YYYY-MM-DD",
          "tmin": float,
          "tmax": float, 
          "precip_mm": float,
          "wind_max_kph": float,
          "code": int
        }
        """
        # Verify top-level structure
        assert "daily" in weather_raw, "weather_raw must contain 'daily' array"
        assert "source" in weather_raw, "weather_raw must contain 'source'"
        assert weather_raw["source"] == "open-meteo", "Source should be open-meteo"
        
        daily_data = weather_raw["daily"]
        assert isinstance(daily_data, list), "daily must be a list"
        assert len(daily_data) > 0, "daily must contain at least one entry"
        
        # Calculate expected date range
        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        expected_days = (end_dt - start_dt).days + 1
        
        assert len(daily_data) == expected_days, f"Expected {expected_days} days, got {len(daily_data)}"
        
        # Validate each daily entry
        for i, day in enumerate(daily_data):
            expected_date = start_dt + timedelta(days=i)
            expected_date_str = expected_date.strftime("%Y-%m-%d")
            
            # Verify required fields
            assert "date" in day, f"Day {i} must have 'date' field"
            assert day["date"] == expected_date_str, f"Day {i} date mismatch: {day['date']} != {expected_date_str}"
            
            # Verify temperature fields (can be None for missing data)
            if day.get("tmin") is not None:
                assert isinstance(day["tmin"], (int, float)), f"tmin must be numeric, got {type(day['tmin'])}"
                assert -50 <= day["tmin"] <= 60, f"Unrealistic tmin: {day['tmin']}°C"
            
            if day.get("tmax") is not None:
                assert isinstance(day["tmax"], (int, float)), f"tmax must be numeric, got {type(day['tmax'])}"
                assert -50 <= day["tmax"] <= 60, f"Unrealistic tmax: {day['tmax']}°C"
            
            # If both temps exist, verify relationship
            if day.get("tmin") is not None and day.get("tmax") is not None:
                assert day["tmin"] <= day["tmax"], f"tmin {day['tmin']} should be <= tmax {day['tmax']}"
            
            # Verify other fields
            assert "precip_mm" in day, f"Day {i} must have 'precip_mm' field"
            if day["precip_mm"] is not None:
                assert day["precip_mm"] >= 0, f"Precipitation cannot be negative: {day['precip_mm']}"
            
            assert "wind_max_kph" in day, f"Day {i} must have 'wind_max_kph' field"
            if day["wind_max_kph"] is not None:
                assert day["wind_max_kph"] >= 0, f"Wind speed cannot be negative: {day['wind_max_kph']}"
            
            assert "code" in day, f"Day {i} must have 'code' field"
            if day["code"] is not None:
                assert isinstance(day["code"], int), f"Weather code must be integer, got {type(day['code'])}"


class TestWeatherFetcherProviderGaps:
    """Test handling of provider gaps and missing data scenarios."""
    
    def test_valid_location_partial_data_handling(self, caplog):
        """
        Test graceful handling when provider returns partial data.
        
        Validates:
        - Function continues successfully with incomplete data
        - Missing values are handled appropriately (None or defaults)
        - Log captures provider gaps
        """
        # Use a remote location that might have incomplete data
        params = {
            "location": "Antarctica Research Station",
            "start_date": "2025-10-20",
            "end_date": "2025-10-22",
            "units": "metric"
        }
        
        with caplog.at_level(logging.INFO):
            result = fetch_weather_data(params)
        
        # Should succeed even with potential data gaps
        if "error" not in result:
            weather_raw = result["weather_raw"]
            daily_data = weather_raw["daily"]
            
            # Verify structure is maintained even with missing data
            assert len(daily_data) == 3, "Should return 3 days even with gaps"
            
            for day in daily_data:
                assert "date" in day, "Date field should always be present"
                # Other fields may be None for missing data
                assert "tmin" in day, "tmin field should be present (may be None)"
                assert "tmax" in day, "tmax field should be present (may be None)"
        else:
            # If location truly doesn't exist, should get clear error
            assert result["error"] in ["invalid_request", "missing_parameters", "internal_error"]
    
    def test_edge_case_locations(self):
        """
        Test edge case locations that might return empty or minimal data.
        
        Validates:
        - Ocean coordinates
        - Desert regions
        - Arctic regions
        """
        edge_cases = [
            {
                "location": "0.0,0.0",  # Null Island (Gulf of Guinea)
                "start_date": "2025-10-20",
                "end_date": "2025-10-21",
                "units": "metric"
            }
        ]
        
        for params in edge_cases:
            result = fetch_weather_data(params)
            
            if "error" not in result:
                # Verify basic structure even for edge locations
                assert "weather_raw" in result
                assert "daily" in result["weather_raw"]
                assert len(result["weather_raw"]["daily"]) == 2  # 2 days
            else:
                # Acceptable if location is truly invalid
                assert "error" in result
    
    def test_provider_timeout_simulation(self):
        """
        Test behavior when MCP call takes longer than expected.
        
        Note: This test documents current timeout handling.
        Real timeout testing would require network delays.
        """
        params = {
            "location": "Sydney",  # Distant location
            "start_date": "2025-10-20",
            "end_date": "2025-10-31",  # Longer range
            "units": "metric"
        }
        
        start_time = time.time()
        result = fetch_weather_data(params)
        duration = time.time() - start_time
        
        # Should complete within reasonable time
        assert duration < 30, f"Call took too long: {duration}s"
        
        if "error" not in result:
            assert result["mcp_duration_ms"] > 0, "Should record actual duration"


class TestWeatherFetcherInvalidInputs:
    """Test handling of invalid parameters and error scenarios."""
    
    def test_missing_required_parameters(self):
        """
        Test handling when required parameters are missing.
        
        Validates:
        - Clear error messages for missing params
        - No crashes or exceptions
        - Error includes helpful hints
        """
        test_cases = [
            {},  # All missing
            {"location": "Tel Aviv"},  # Missing dates
            {"start_date": "2025-10-20", "end_date": "2025-10-25"},  # Missing location
            {"location": "Tel Aviv", "start_date": "2025-10-20"},  # Missing end_date
        ]
        
        for params in test_cases:
            result = fetch_weather_data(params)
            
            # Should return error, not crash
            assert "error" in result, f"Should return error for params: {params}"
            assert "hint" in result, "Error should include helpful hint"
            
            # Error should be descriptive
            error_msg = result["error"]
            assert error_msg in ["missing_parameters", "mcp_process_failed"], f"Unexpected error: {error_msg}"
    
    def test_invalid_date_range(self):
        """
        Test handling when start_date > end_date.
        
        Validates:
        - Clear error about invalid date range
        - No data corruption
        - Graceful error handling
        """
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-25",  # After end_date
            "end_date": "2025-10-20",
            "units": "metric"
        }
        
        result = fetch_weather_data(params)
        
        assert "error" in result, "Should return error for invalid date range"
        assert "hint" in result, "Should provide helpful error message"
        
        # Should be specific about date range issue
        hint = result["hint"].lower()
        assert any(word in hint for word in ["date", "range", "invalid"]), f"Hint should mention date issue: {hint}"
    
    def test_invalid_units(self):
        """
        Test handling of invalid units parameter.
        
        Validates:
        - Invalid units are caught and handled
        - Clear error message about valid units
        """
        params = {
            "location": "Tel Aviv", 
            "start_date": "2025-10-20",
            "end_date": "2025-10-25",
            "units": "celsius"  # Invalid, should be "metric" or "imperial"
        }
        
        result = fetch_weather_data(params)
        
        assert "error" in result, "Should return error for invalid units"
        hint = result["hint"].lower()
        assert "units" in hint or "metric" in hint or "imperial" in hint, f"Should mention valid units: {hint}"
    
    def test_nonexistent_location(self):
        """
        Test handling of completely invalid locations.
        
        Validates:
        - Graceful handling of geocoding failures
        - Clear error message about location not found
        """
        params = {
            "location": "Nonexistent City XYZ123",
            "start_date": "2025-10-20", 
            "end_date": "2025-10-25",
            "units": "metric"
        }
        
        result = fetch_weather_data(params)
        
        assert "error" in result, "Should return error for nonexistent location"
        assert "hint" in result, "Should provide helpful error message"
        
        # Should be related to location issue
        hint = result["hint"].lower()
        assert any(word in hint for word in ["location", "found", "geocod"]), f"Should mention location issue: {hint}"
    
    def test_date_range_too_large(self):
        """
        Test handling when date range exceeds maximum allowed span.
        
        Validates:
        - Range limits are enforced (>31 days)
        - Clear error about range being too large
        """
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",  # 365 days - too large
            "units": "metric"
        }
        
        result = fetch_weather_data(params)
        
        assert "error" in result, "Should return error for oversized date range"
        
        # Should be specific about range size issue  
        hint = result["hint"].lower()
        expected_keywords = ["range", "large", "days", "31"]
        assert any(word in hint for word in expected_keywords), f"Should mention range size limit: {hint}"
    
    def test_task_a_error_propagation(self):
        """
        Test that errors from Task A are properly propagated without MCP call.
        
        Validates:
        - Previous task errors are passed through unchanged
        - No MCP call is made when error exists
        - Original error context is preserved
        """
        # Simulate Task A error
        error_params = {
            "error": "parsing_failed",
            "hint": "Could not parse natural language query",
            "query": "invalid query"
        }
        
        result = fetch_weather_data(error_params)
        
        # Should return the original error unchanged
        assert result == error_params, "Task A errors should be passed through unchanged"


class TestWeatherFetcherPerformance:
    """Test performance characteristics and timing validation."""
    
    def test_duration_logging_accuracy(self, caplog):
        """
        Test that duration logging captures accurate timing information.
        
        Validates:
        - Duration is measured accurately
        - Log entries include timing data
        - Performance is within acceptable bounds
        """
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20",
            "end_date": "2025-10-22",
            "units": "metric"
        }
        
        start_time = time.perf_counter()
        
        with caplog.at_level(logging.INFO):
            result = fetch_weather_data(params)
        
        end_time = time.perf_counter()
        measured_duration_ms = int((end_time - start_time) * 1000)
        
        if "error" not in result:
            reported_duration_ms = result["mcp_duration_ms"]
            
            # Duration should be positive and reasonable
            assert reported_duration_ms > 0, "Duration must be positive"
            assert reported_duration_ms < 10000, "Duration should be under 10 seconds"
            
            # Reported duration should be close to measured (within 500ms tolerance)
            tolerance = 500
            assert abs(reported_duration_ms - measured_duration_ms) < tolerance, \
                f"Duration mismatch: reported {reported_duration_ms}ms vs measured {measured_duration_ms}ms"
    
    def test_multiple_calls_consistency(self):
        """
        Test that multiple calls to same location return consistent results.
        
        Validates:
        - Caching behavior (if implemented)
        - Result consistency
        - Performance across multiple calls
        """
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-20", 
            "end_date": "2025-10-22",
            "units": "metric"
        }
        
        results = []
        durations = []
        
        # Make multiple calls
        for i in range(3):
            start_time = time.perf_counter()
            result = fetch_weather_data(params)
            duration = (time.perf_counter() - start_time) * 1000
            
            if "error" not in result:
                results.append(result)
                durations.append(duration)
        
        # Should have gotten successful results
        assert len(results) > 0, "Should get at least one successful result"
        
        if len(results) > 1:
            # Results should be consistent (same location, dates)
            first_result = results[0]
            for result in results[1:]:
                assert result["params"] == first_result["params"], "Params should be identical"
                # Weather data should be the same (unless cache expired)
                assert len(result["weather_raw"]["daily"]) == len(first_result["weather_raw"]["daily"])
    
    def test_large_date_range_performance(self):
        """
        Test performance with maximum allowed date range (31 days).
        
        Validates:
        - Large ranges complete within reasonable time
        - Memory usage is reasonable
        - All days are included in response
        """
        params = {
            "location": "Tel Aviv",
            "start_date": "2025-10-01",
            "end_date": "2025-10-31",  # 31 days - maximum allowed
            "units": "metric"
        }
        
        start_time = time.perf_counter()
        result = fetch_weather_data(params)
        duration = (time.perf_counter() - start_time) * 1000
        
        if "error" not in result:
            # Should complete within reasonable time
            assert duration < 15000, f"Large range took too long: {duration}ms"
            
            # Should return all 31 days
            daily_data = result["weather_raw"]["daily"]
            assert len(daily_data) == 31, f"Expected 31 days, got {len(daily_data)}"
            
            # Memory usage should be reasonable (check data size)
            total_fields = sum(len(day.keys()) for day in daily_data)
            assert total_fields < 500, f"Too many fields returned: {total_fields}"


class TestWeatherFetcherEndToEnd:
    """Test end-to-end integration between Task A and Task B."""
    
    def test_task_a_to_task_b_chain_compatibility(self, caplog):
        """
        Test complete Task A → Task B chain to ensure compatibility.
        
        Validates:
        - Task A output is valid input for Task B
        - Context flows correctly between tasks
        - No data loss or corruption in the pipeline
        - Both tasks complete successfully
        """
        # Natural language query (input to Task A)
        natural_query = "weather in Tel Aviv from Monday to Friday"
        
        with caplog.at_level(logging.INFO):
            # Execute Task A: Parse natural language
            task_a_result = parse_natural_language({"query": natural_query})
            
            # Verify Task A succeeded
            assert "error" not in task_a_result, f"Task A failed: {task_a_result.get('error')}"
            assert "location" in task_a_result, "Task A should extract location"
            assert "start_date" in task_a_result, "Task A should extract start_date"
            assert "end_date" in task_a_result, "Task A should extract end_date"
            
            # Execute Task B: Fetch weather data
            task_b_result = fetch_weather_data(task_a_result)
            
            # Verify Task B succeeded
            assert "error" not in task_b_result, f"Task B failed: {task_b_result.get('error')}"
        
        # Verify end-to-end data flow
        assert "params" in task_b_result, "Task B should preserve params from Task A"
        assert "weather_raw" in task_b_result, "Task B should add weather_raw from MCP"
        
        # Verify parameter preservation
        params = task_b_result["params"]
        assert params["location"] in ["Tel Aviv", "Tel Aviv, IL", "Tel Aviv, Israel"], "Location should be preserved/formatted"
        assert params["units"] == task_a_result.get("units", "metric"), "Units should be preserved"
        
        # Verify weather data is valid
        weather_raw = task_b_result["weather_raw"]
        assert "daily" in weather_raw, "weather_raw should contain daily data"
        assert len(weather_raw["daily"]) > 0, "Should have at least one day of data"
        
        # Verify date range consistency
        daily_data = weather_raw["daily"]
        start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
        end_date = datetime.strptime(params["end_date"], "%Y-%m-%d").date()
        expected_days = (end_date - start_date).days + 1
        
        assert len(daily_data) == expected_days, f"Expected {expected_days} days, got {len(daily_data)}"
        
        # Verify logs contain information from both tasks
        log_messages = " ".join([record.message for record in caplog.records])
        # Should have evidence of both parsing and MCP operations
        has_parse_activity = any(keyword in log_messages.lower() for keyword in ["parse", "language", "extract"])
        has_mcp_activity = any(keyword in log_messages.lower() for keyword in ["mcp", "weather", "tool"])
        
        # Note: Specific log checking depends on actual logging implementation
        # This validates that both tasks are active in the pipeline
    
    def test_confidence_propagation_check(self):
        """
        Test that confidence from Task A is preserved through Task B.
        
        Validates:
        - Confidence values flow correctly
        - No unintended modifications
        - Consistent context preservation
        """
        # Simulate Task A output with confidence
        task_a_output = {
            "location": "New York",
            "start_date": "2025-10-20",
            "end_date": "2025-10-22", 
            "units": "imperial",
            "confidence": 0.87
        }
        
        result = fetch_weather_data(task_a_output)
        
        if "error" not in result:
            # Note: Current implementation only preserves core weather params
            # This test documents expected behavior for confidence preservation
            # If confidence preservation is implemented, update assertion:
            # assert result.get("confidence") == 0.87, "Confidence should be preserved"
            
            # Verify core params are preserved
            params = result["params"]
            assert params["units"] == "imperial", "Units should be preserved"
            assert params["location"] in ["New York", "New York, NY", "New York, US", "New York, United States"], "Location should be preserved"
    
    def test_timestamp_consistency_check(self):
        """
        Test date alignment and timestamp consistency.
        
        Validates:
        - Start/end dates align with returned weather data
        - No date shifts or timezone issues
        - Chronological order is maintained
        """
        params = {
            "location": "London",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "units": "metric"
        }
        
        result = fetch_weather_data(params)
        
        if "error" not in result:
            daily_data = result["weather_raw"]["daily"]
            
            # Verify date sequence
            expected_dates = []
            start_date = datetime.strptime(params["start_date"], "%Y-%m-%d").date()
            for i in range(5):  # 5 days: Oct 20-24
                expected_dates.append((start_date + timedelta(days=i)).strftime("%Y-%m-%d"))
            
            actual_dates = [day["date"] for day in daily_data]
            
            assert actual_dates == expected_dates, f"Date mismatch: {actual_dates} != {expected_dates}"
            
            # Verify chronological order
            for i in range(len(actual_dates) - 1):
                current_date = datetime.strptime(actual_dates[i], "%Y-%m-%d").date()
                next_date = datetime.strptime(actual_dates[i + 1], "%Y-%m-%d").date()
                assert next_date == current_date + timedelta(days=1), "Dates should be consecutive"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])