#!/usr/bin/env python3
"""
MCP Weather Server - stdio-based JSON communication tool.
"""
import json
import logging
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict

from cache import weather_cache
from provider import WeatherProvider


class MCPStructuredJSONFormatter(logging.Formatter):
    """Structured JSON formatter for MCP server with tool identification."""

    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "tool": "weather.get_range",  # MCP tool identifier
        }

        # Add structured fields if present
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id

        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        if hasattr(record, "task"):
            log_entry["task"] = record.task

        if hasattr(record, "status"):
            log_entry["status"] = record.status

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


def setup_mcp_logging(log_level: str = "INFO") -> None:
    """Setup structured logging configuration for MCP server."""
    # Create formatter with ISO timestamp format
    formatter = MCPStructuredJSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add stderr handler with structured formatter
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)


# Initialize logging
setup_mcp_logging()


def validate_date_range(start_date: str, end_date: str) -> None:
    """Validate date range constraints."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        if end < start:
            raise ValueError("end_date must be >= start_date")

        span_days = (end - start).days + 1
        if span_days > 31:
            raise ValueError("range_too_large")

    except ValueError as e:
        if str(e) == "range_too_large":
            raise
        raise ValueError("Invalid date format. Use YYYY-MM-DD")


def process_weather_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process weather request and return response."""
    request_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        # Extract and validate parameters
        location = request_data.get("location")
        start_date = request_data.get("start_date")
        end_date = request_data.get("end_date")
        units = request_data.get("units", "metric")

        if not all([location, start_date, end_date]):
            return {
                "error": "missing_parameters",
                "hint": "location, start_date, and end_date are required",
            }

        if units not in ["metric", "imperial"]:
            return {
                "error": "invalid_units",
                "hint": "units must be 'metric' or 'imperial'",
            }

        # Validate date range
        validate_date_range(start_date, end_date)

        # Initialize provider
        provider = WeatherProvider()

        # Geocode location
        lat, lon, formatted_location = provider.geocode_location(location)

        # Check cache first
        cached_data = weather_cache.get(lat, lon, start_date, end_date, units)
        if cached_data:
            duration_ms = int((time.time() - start_time) * 1000)

            # Log request
            logger = logging.getLogger(__name__)
            logger.info(
                "", extra={"request_id": request_id, "duration_ms": duration_ms}
            )

            return cached_data

        # Fetch weather data
        weather_data = provider.fetch_weather_data(
            lat, lon, start_date, end_date, units
        )

        # Prepare response
        response = {
            "location": formatted_location,
            "latitude": lat,
            "longitude": lon,
            "units": units,
            "start_date": start_date,
            "end_date": end_date,
            **weather_data,
        }

        # Cache the response
        weather_cache.set(lat, lon, start_date, end_date, units, response)

        # Log request
        duration_ms = int((time.time() - start_time) * 1000)
        logger = logging.getLogger(__name__)
        logger.info("", extra={"request_id": request_id, "duration_ms": duration_ms})

        return response

    except ValueError as e:
        duration_ms = int((time.time() - start_time) * 1000)

        if "range_too_large" in str(e):
            return {"error": "range_too_large", "hint": "span must be <= 31 days"}

        logger = logging.getLogger(__name__)
        logger.error(
            f"Request error: {e}",
            extra={"request_id": request_id, "duration_ms": duration_ms},
        )

        return {"error": "invalid_request", "hint": str(e)}

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        logger = logging.getLogger(__name__)
        logger.error(
            f"Unexpected error: {e}",
            extra={"request_id": request_id, "duration_ms": duration_ms},
        )

        return {"error": "internal_error", "hint": "Server error occurred"}


def main():
    """Main entry point for MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Weather Server")
    parser.add_argument(
        "--persistent", action="store_true", help="Run in persistent mode (for Docker)"
    )
    args = parser.parse_args()

    if args.persistent:
        run_persistent_mode()
    else:
        run_single_request_mode()


def run_single_request_mode():
    """Single request mode - read from stdin, process, write to stdout, exit."""
    try:
        # Read from stdin
        input_data = sys.stdin.read().strip()

        if not input_data:
            response = {"error": "no_input", "hint": "No input data provided"}
        else:
            try:
                request_data = json.loads(input_data)
                response = process_weather_request(request_data)
            except json.JSONDecodeError:
                response = {"error": "invalid_json", "hint": "Input must be valid JSON"}

        # Write response to stdout
        print(json.dumps(response, ensure_ascii=False))
        sys.stdout.flush()

    except Exception as e:
        error_response = {"error": "server_error", "hint": f"Server error: {str(e)}"}
        print(json.dumps(error_response))
        sys.stdout.flush()
        sys.exit(1)


def run_persistent_mode():
    """Persistent mode - keep reading from stdin and responding to stdout."""
    logger = logging.getLogger(__name__)
    logger.info("Starting MCP server in persistent mode")

    try:
        while True:
            try:
                # Read line from stdin
                line = sys.stdin.readline()
                if not line:  # EOF
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    request_data = json.loads(line)
                    response = process_weather_request(request_data)
                except json.JSONDecodeError:
                    response = {
                        "error": "invalid_json",
                        "hint": "Input must be valid JSON",
                    }

                # Write response to stdout
                print(json.dumps(response, ensure_ascii=False))
                sys.stdout.flush()

            except KeyboardInterrupt:
                break
            except Exception as e:
                error_response = {
                    "error": "server_error",
                    "hint": f"Server error: {str(e)}",
                }
                print(json.dumps(error_response))
                sys.stdout.flush()

    except Exception as e:
        logger.error(f"Fatal error in persistent mode: {e}")
        sys.exit(1)

    logger.info("MCP server persistent mode ended")


if __name__ == "__main__":
    main()
