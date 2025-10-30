"""
CrewAI Flow - Orchestrates tasks A->B->C sequentially.
"""
import logging
import time
import uuid
from typing import Any, Dict

from .agents import analyze_weather
from .mcp_client import fetch_weather_data
from .parser import parse_natural_language

logger = logging.getLogger(__name__)


class WeatherAnalysisFlow:
    def __init__(self):
        self.request_id = None
        self.timing = {}

    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process weather query through the complete A->B->C flow.
        """
        self.request_id = str(uuid.uuid4())
        self.timing = {}

        logger.info(f"Starting weather analysis flow for request {self.request_id}")

        try:
            # Task A: Parse natural language query
            task_a_result = self._execute_task_a({"query": query})
            if "error" in task_a_result:
                return self._format_error_response(task_a_result)

            # Task B: Fetch weather data via MCP
            task_b_result = self._execute_task_b(task_a_result)
            if "error" in task_b_result:
                return self._format_error_response(task_b_result)

            # Task C: Analyze weather and generate summary
            task_c_result = self._execute_task_c(task_b_result)
            if "error" in task_c_result:
                return self._format_error_response(task_c_result)

            # Format successful response
            return self._format_success_response(task_c_result, task_b_result)

        except Exception as e:
            logger.error(f"Flow error for request {self.request_id}: {e}")
            return {
                "error": "flow_failed",
                "hint": f"Weather analysis flow failed: {str(e)}",
                "request_id": self.request_id,
            }

    def _execute_task_a(self, query_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Task A: Natural language parsing."""
        start_time = time.time()

        try:
            result = parse_natural_language(query_data)

            duration_ms = int((time.time() - start_time) * 1000)
            self.timing["task_a_ms"] = duration_ms

            logger.info(
                f"Task A completed in {duration_ms}ms for request {self.request_id}"
            )
            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.timing["task_a_ms"] = duration_ms

            logger.error(
                f"Task A failed in {duration_ms}ms for request {self.request_id}: {e}"
            )
            return {
                "error": "task_a_failed",
                "hint": f"Natural language parsing failed: {str(e)}",
            }

    def _execute_task_b(self, parsed_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Task B: Weather data fetching via MCP."""
        start_time = time.time()

        try:
            result = fetch_weather_data(parsed_params)

            duration_ms = int((time.time() - start_time) * 1000)
            self.timing["task_b_ms"] = duration_ms

            # Add MCP timing if available
            if "mcp_duration_ms" in result:
                self.timing["mcp_call_ms"] = result["mcp_duration_ms"]

            logger.info(
                f"Task B completed in {duration_ms}ms for request {self.request_id}"
            )
            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.timing["task_b_ms"] = duration_ms

            logger.error(
                f"Task B failed in {duration_ms}ms for request {self.request_id}: {e}"
            )
            return {
                "error": "task_b_failed",
                "hint": f"Weather data fetching failed: {str(e)}",
            }

    def _execute_task_c(self, weather_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Task C: Weather analysis and summary generation."""
        start_time = time.time()

        try:
            result = analyze_weather(weather_data)

            duration_ms = int((time.time() - start_time) * 1000)
            self.timing["task_c_ms"] = duration_ms

            logger.info(
                f"Task C completed in {duration_ms}ms for request {self.request_id}"
            )
            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            self.timing["task_c_ms"] = duration_ms

            logger.error(
                f"Task C failed in {duration_ms}ms for request {self.request_id}: {e}"
            )
            return {
                "error": "task_c_failed",
                "hint": f"Weather analysis failed: {str(e)}",
            }

    def _format_success_response(
        self, analysis_result: Dict[str, Any], weather_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format successful response according to API specification."""
        # Calculate total latency
        total_latency = sum(self.timing.values())

        # Extract data from weather_data
        params = weather_data.get("params", {})
        weather_raw = weather_data.get("weather_raw", {})

        # Build response
        response = {
            "summary": analysis_result.get("summary_text", ""),
            "params": {
                "location": params.get("location", ""),
                "start_date": params.get("start_date", ""),
                "end_date": params.get("end_date", ""),
                "units": params.get("units", "metric"),
            },
            "data": {
                "daily": weather_raw.get("daily", []),
                "source": weather_raw.get("source", "open-meteo"),
            },
            "confidence": analysis_result.get("confidence", 0.0),
            "tool_used": "weather.get_range",
            "latency_ms": int(total_latency),
            "request_id": self.request_id,
        }

        # Add timing breakdown for debugging (optional)
        if logger.isEnabledFor(logging.DEBUG):
            response["timing_breakdown"] = self.timing

        return response

    def _format_error_response(self, error_result: Dict[str, Any]) -> Dict[str, Any]:
        """Format error response."""
        # Calculate total latency so far
        total_latency = sum(self.timing.values())

        response = {
            "error": error_result.get("error", "unknown_error"),
            "hint": error_result.get("hint", "An error occurred"),
            "request_id": self.request_id,
            "latency_ms": int(total_latency),
        }

        # Add timing breakdown for debugging
        if self.timing and logger.isEnabledFor(logging.DEBUG):
            response["timing_breakdown"] = self.timing

        return response


def process_weather_query(query: str) -> Dict[str, Any]:
    """
    Main entry point for weather query processing.
    """
    flow = WeatherAnalysisFlow()
    return flow.process_query(query)
