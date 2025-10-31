"""
Prometheus metrics for WeatherSense API monitoring.
"""
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Histogram,
    Info,
    generate_latest,
)

# Application info metric
app_info = Info(
    "weathersense_app_info",
    "Application information for WeatherSense",
)

# Request metrics
request_counter = Counter(
    "weathersense_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status_code"],
)

# Latency metrics
request_duration = Histogram(
    "weathersense_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

# Weather-specific metrics
weather_query_counter = Counter(
    "weathersense_weather_queries_total",
    "Total number of weather queries processed",
    ["status", "location_type"],
)

weather_query_duration = Histogram(
    "weathersense_weather_query_duration_seconds",
    "Weather query processing duration in seconds",
    ["status"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

# MCP tool metrics
mcp_tool_calls = Counter(
    "weathersense_mcp_tool_calls_total",
    "Total number of MCP tool calls",
    ["tool_name", "status"],
)

mcp_tool_duration = Histogram(
    "weathersense_mcp_tool_duration_seconds",
    "MCP tool call duration in seconds",
    ["tool_name"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)

# Error metrics
error_counter = Counter(
    "weathersense_errors_total",
    "Total number of errors",
    ["error_type", "component"],
)

# Health metrics
health_check_counter = Counter(
    "weathersense_health_checks_total",
    "Total number of health check requests",
    ["status"],
)


def set_app_info(version: str, environment: str = "production"):
    """Set application information."""
    app_info.info(
        {"version": version, "environment": environment, "application": "weathersense"}
    )


def get_metrics() -> bytes:
    """Get all metrics in Prometheus format."""
    return generate_latest(REGISTRY)


def get_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    return CONTENT_TYPE_LATEST
