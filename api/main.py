"""
FastAPI main application with weather analysis endpoints.
"""
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from crew.flow import process_weather_query
from crew.mcp_client import start_persistent_mcp_server, stop_persistent_mcp_server

from .logging_config import log_request, setup_logging
from .security import verify_api_key_header

# Setup logging
setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


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
        f"Configuration: TZ={os.getenv('TZ')}, WEATHER_PROVIDER={os.getenv('WEATHER_PROVIDER')}"
    )
    if os.getenv("WEATHER_API_KEY"):
        logger.info("WEATHER_API_KEY is configured")
    else:
        logger.info("WEATHER_API_KEY is not set (optional)")

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class WeatherQueryRequest(BaseModel):
    query: str


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
    return HealthResponse(ok=True)


@app.post("/v1/weather/ask", response_model=WeatherQueryResponse)
async def weather_ask(
    request: WeatherQueryRequest,
    x_api_key: str = Header(None, alias="x-api-key"),
    api_key: str = Depends(verify_api_key_header),
):
    """
    Process natural language weather query.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    # Log request start
    logger.info(
        f"Weather query request started: {request.query}",
        extra={"request_id": request_id, "task": "weather_query", "status": "started"},
    )

    try:
        # Validate input
        if not request.query or not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query parameter is required and cannot be empty",
            )

        # Process the query through CrewAI flow
        result = process_weather_query(request.query.strip())

        # Calculate total duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Handle errors from the flow
        if "error" in result:
            error_code = result.get("error", "unknown_error")
            hint = result.get("hint", "An error occurred")

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
    from fastapi.responses import JSONResponse

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
