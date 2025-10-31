"""
FastAPI main application with weather analysis endpoints.
"""
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from html import escape
from typing import Any, Dict

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

from crew.flow import process_weather_query
from crew.mcp_client import start_persistent_mcp_server, stop_persistent_mcp_server
from utils.metrics import (
    get_content_type,
    get_metrics,
    health_check_counter,
    request_counter,
    request_duration,
    set_app_info,
    weather_query_counter,
    weather_query_duration,
)

from .logging_config import log_request, setup_logging
from .security import verify_api_key_header

# Setup logging
setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Simple rate limiting
rate_limit_storage = defaultdict(list)  # {ip: [timestamp1, timestamp2, ...]}
RATE_LIMIT_REQUESTS = 30
RATE_LIMIT_WINDOW = 60  # seconds


def check_rate_limit(client_ip: str) -> bool:
    """Check if client IP is within rate limit."""
    now = time.time()
    # Clean old requests outside the window
    rate_limit_storage[client_ip] = [
        ts for ts in rate_limit_storage[client_ip] if now - ts < RATE_LIMIT_WINDOW
    ]

    # Check if under limit
    if len(rate_limit_storage[client_ip]) >= RATE_LIMIT_REQUESTS:
        return False

    # Add current request
    rate_limit_storage[client_ip].append(now)
    return True


def get_client_ip(request: Request) -> str:
    """Extract client IP from request."""
    # Check for X-Forwarded-For header (common in reverse proxies)
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()

    # Check for X-Real-IP header
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fall back to direct client IP
    return request.client.host if request.client else "unknown"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan event handler."""
    # Startup
    logger.info("WeatherSense API starting up")

    # Validate required environment variables
    required_env_vars = ["API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]

    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise RuntimeError(f"Missing required environment variables: {missing_vars}")

    # Set default values for optional environment variables
    os.environ.setdefault("TZ", "UTC")
    os.environ.setdefault("WEATHER_PROVIDER", "open-meteo")
    os.environ.setdefault("LOG_LEVEL", "INFO")

    # Start persistent MCP server if in Docker environment
    if os.getenv("DEPLOYMENT_ENV") == "docker":
        logger.info("Starting persistent MCP server for Docker environment")
        if not start_persistent_mcp_server():
            logger.error("Failed to start persistent MCP server")
            raise RuntimeError("Failed to start persistent MCP server")
        logger.info("Persistent MCP server started successfully")
    else:
        logger.info("Local environment detected, will use subprocess mode for MCP")

    # Log configuration
    logger.info(
        f"Configuration: TZ={os.getenv('TZ')}, "
        f"WEATHER_PROVIDER={os.getenv('WEATHER_PROVIDER')}"
    )
    if os.getenv("WEATHER_API_KEY"):
        logger.info("WEATHER_API_KEY is configured")
    else:
        logger.info("WEATHER_API_KEY is not set (optional)")

    # Set up Prometheus metrics
    environment = os.getenv("DEPLOYMENT_ENV", "local")
    set_app_info(version="1.0.0", environment=environment)
    logger.info("Prometheus metrics initialized")

    logger.info("WeatherSense API startup complete")

    yield

    # Shutdown
    logger.info("WeatherSense API shutting down")

    # Stop persistent MCP server if running
    if os.getenv("DEPLOYMENT_ENV") == "docker":
        logger.info("Stopping persistent MCP server")
        stop_persistent_mcp_server()
        logger.info("Persistent MCP server stopped")

    logger.info("WeatherSense API shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="WeatherSense API",
    description="Weather analysis with MCP tools and CrewAI",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiting state
logger.info("Rate limiting initialized: 30 requests per minute per IP")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# HTTPS enforcement middleware
@app.middleware("http")
async def https_enforcement_middleware(request: Request, call_next):
    """
    Enforce HTTPS for production environments and add security headers.
    Can be disabled by setting HTTPS_ONLY=false for local development.
    """
    https_only = os.getenv("HTTPS_ONLY", "true").lower() == "true"

    # Skip HTTPS enforcement for health checks, local development, and test environments
    if (
        not https_only
        or request.url.path in ["/health", "/healthz"]
        or request.headers.get("host", "").startswith("localhost")
        or request.headers.get("host", "").startswith("127.0.0.1")
        or request.headers.get("host", "").startswith("testserver")  # For testing
    ):
        response = await call_next(request)
    else:
        # Enforce HTTPS in production
        if request.url.scheme != "https":
            # Redirect HTTP to HTTPS
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)

        response = await call_next(request)

    # Add security headers
    response.headers[
        "Strict-Transport-Security"
    ] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response


# Metrics collection middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """
    Collect Prometheus metrics for HTTP requests.
    """
    # Skip metrics collection for the metrics endpoint itself
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.time()
    method = request.method
    path = request.url.path

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Normalize endpoint for metrics (remove dynamic parts)
    endpoint = path
    if path.startswith("/v1/weather/ask"):
        endpoint = "/v1/weather/ask"
    elif path in ["/health", "/healthz"]:
        endpoint = "/health"

    # Record metrics
    request_counter.labels(
        method=method, endpoint=endpoint, status_code=response.status_code
    ).inc()

    request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    return response


# Pydantic models
class WeatherQueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, v):
        """Sanitize input query to prevent XSS and injection attacks."""
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")

        sanitized = v.strip()

        # Remove null bytes and control characters (except common whitespace)
        sanitized = "".join(
            char for char in sanitized if ord(char) >= 32 or char in "\t\n\r"
        )

        # HTML escape first to prevent XSS
        sanitized = escape(sanitized)

        # Then remove potentially dangerous patterns (they might be HTML escaped now)
        dangerous_patterns = [
            r"&lt;script[^&]*&gt;.*?&lt;/script&gt;",  # HTML escaped script tags
            r"<script[^>]*>.*?</script>",  # Direct script tags
            r"javascript:",  # JavaScript URLs
            r"on\w+\s*=",  # Event handlers
            r"&lt;iframe[^&]*&gt;.*?&lt;/iframe&gt;",  # HTML escaped iframe tags
            r"<iframe[^>]*>.*?</iframe>",  # Direct iframe tags
            r"&lt;object[^&]*&gt;.*?&lt;/object&gt;",  # HTML escaped object tags
            r"<object[^>]*>.*?</object>",  # Direct object tags
            r"&lt;embed[^&]*&gt;.*?&lt;/embed&gt;",  # HTML escaped embed tags
            r"<embed[^>]*>.*?</embed>",  # Direct embed tags
            r"expression\s*\(",  # CSS expression
            r"vbscript:",  # VBScript URLs
        ]

        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)

        # Check for potential coordinate patterns and validate them
        coord_pattern = r"(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)"
        matches = re.findall(coord_pattern, sanitized)
        for lat_str, lon_str in matches:
            try:
                lat, lon = float(lat_str), float(lon_str)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    raise ValueError(
                        "Invalid coordinates: latitude must be -90 to 90, "
                        "longitude must be -180 to 180"
                    )
            except ValueError as e:
                if "Invalid coordinates" in str(e):
                    raise e
                # If conversion fails, it's probably not coordinates, continue

        return sanitized


class HealthResponse(BaseModel):
    ok: bool


class WeatherQueryResponse(BaseModel):
    summary: str
    params: Dict[str, Any]
    data: Dict[str, Any]
    confidence: float
    tool_used: str
    latency_ms: int
    request_id: str


class ErrorResponse(BaseModel):
    error: str
    hint: str


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    health_check_counter.labels(status="ok").inc()
    return HealthResponse(ok=True)


# Register /healthz only in local/debug environment
if (
    os.getenv("ENV", "local") == "local"
    or os.getenv("DEBUG", "false").lower() == "true"
):

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz_check():
        return await health_check()


@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    from fastapi.responses import Response

    metrics_data = get_metrics()
    return Response(content=metrics_data, media_type=get_content_type())


@app.post("/v1/weather/ask", response_model=WeatherQueryResponse)
async def weather_ask(
    request: WeatherQueryRequest,
    raw_request: Request,
    x_api_key: str = Header(None, alias="x-api-key"),
    api_key: str = Depends(verify_api_key_header),
):
    """
    Process natural language weather query.
    """
    # Check rate limit
    client_ip = get_client_ip(raw_request)
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail={
                "detail": "Rate limit exceeded. Try again later.",
                "error_type": "rate_limited",
                "retry_after": 60,
            },
        )
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Log request start
    logger.info(
        f"Weather query request started: {request.query}",
        extra={"request_id": request_id, "task": "weather_query", "status": "started"},
    )

    try:
        # Process the query through CrewAI flow (input already validated by Pydantic)
        result = process_weather_query(request.query.strip())

        # Calculate total duration
        duration_ms = int((time.time() - start_time) * 1000)
        duration_seconds = duration_ms / 1000.0

        # Handle errors from the flow
        if "error" in result:
            error_code = result.get("error", "unknown_error")
            hint = result.get("hint", "An error occurred")

            # Record failed weather query metrics
            weather_query_counter.labels(status="error", location_type="unknown").inc()
            weather_query_duration.labels(status="error").observe(duration_seconds)

            # Map errors to HTTP status codes
            if error_code in [
                "missing_location",
                "invalid_date_range",
                "invalid_date_order",
                "range_too_large",
            ]:
                status_code = status.HTTP_400_BAD_REQUEST
            elif error_code in ["rate_limited", "quota_exceeded"]:
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif error_code in [
                "mcp_timeout",
                "fetch_failed",
                "provider_unavailable",
                "mcp_failed",
            ]:
                status_code = status.HTTP_502_BAD_GATEWAY
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            # Log error
            log_request(
                logger,
                request_id,
                "weather_query",
                duration_ms,
                "error",
                f"Query failed: {error_code}",
            )

            raise HTTPException(
                status_code=status_code, detail={"error": error_code, "hint": hint}
            )

        # Update the response with actual duration and request_id
        result["latency_ms"] = duration_ms
        result["request_id"] = request_id

        # Determine location type for metrics
        location_type = "unknown"
        if "params" in result and "location" in result["params"]:
            location = result["params"]["location"]
            if (
                "," in location
                and location.replace(".", "")
                .replace("-", "")
                .replace(",", "")
                .replace(" ", "")
                .isdigit()
            ):
                location_type = "coordinates"
            else:
                location_type = "city_name"

        # Record successful weather query metrics
        weather_query_counter.labels(
            status="success", location_type=location_type
        ).inc()
        weather_query_duration.labels(status="success").observe(duration_seconds)

        # Log successful request
        log_request(
            logger,
            request_id,
            "weather_query",
            duration_ms,
            "success",
            "Query completed successfully",
        )

        return result

    except HTTPException:
        # Re-raise HTTP exceptions
        raise

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        duration_seconds = duration_ms / 1000.0

        # Record exception metrics
        weather_query_counter.labels(status="exception", location_type="unknown").inc()
        weather_query_duration.labels(status="exception").observe(duration_seconds)

        # Log unexpected error
        log_request(
            logger,
            request_id,
            "weather_query",
            duration_ms,
            "error",
            f"Unexpected error: {str(e)}",
        )

        logger.exception(
            f"Unexpected error in weather query: {e}", extra={"request_id": request_id}
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error",
                "hint": "An unexpected error occurred",
            },
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler for consistent error responses."""
    # Handle both dict and string details
    if isinstance(exc.detail, dict):
        content = exc.detail
    else:
        content = {"error": exc.detail}

    return JSONResponse(status_code=exc.status_code, content=content)


# Additional error handlers for specific status codes - removed to avoid conflicts
# The HTTPException handler above handles all HTTP errors properly


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, log_level="info", reload=False)
