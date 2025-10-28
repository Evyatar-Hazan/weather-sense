"""
FastAPI main application with weather analysis endpoints.
"""
import os
import time
import uuid
import logging
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .logging_config import setup_logging, log_request
from .security import verify_api_key_header
from crew.flow import process_weather_query


# Setup logging
setup_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="WeatherSense API",
    description="Weather analysis with MCP tools and CrewAI",
    version="1.0.0"
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


@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(ok=True)


@app.post("/v1/weather/ask")
async def weather_ask(
    request: WeatherQueryRequest,
    x_api_key: str = Header(None, alias="x-api-key"),
    api_key: str = Depends(verify_api_key_header)
):
    """
    Process natural language weather query.
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Log request start
    logger.info(f"Weather query request started: {request.query}", extra={
        "request_id": request_id,
        "task": "weather_query",
        "status": "started"
    })
    
    try:
        # Validate input
        if not request.query or not request.query.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query parameter is required and cannot be empty"
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
            if error_code in ["missing_location", "invalid_date_range", "invalid_date_order", "range_too_large"]:
                status_code = status.HTTP_400_BAD_REQUEST
            elif error_code in ["mcp_timeout", "fetch_failed", "provider_unavailable"]:
                status_code = status.HTTP_502_BAD_GATEWAY
            elif error_code in ["rate_limited"]:
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
            # Log error
            log_request(
                logger, request_id, "weather_query", duration_ms, "error",
                f"Query failed: {error_code}"
            )
            
            raise HTTPException(
                status_code=status_code,
                detail={"error": error_code, "hint": hint}
            )
        
        # Update the response with actual duration and request_id
        result["latency_ms"] = duration_ms
        result["request_id"] = request_id
        
        # Log successful request
        log_request(
            logger, request_id, "weather_query", duration_ms, "success",
            "Query completed successfully"
        )
        
        return result
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log unexpected error
        log_request(
            logger, request_id, "weather_query", duration_ms, "error",
            f"Unexpected error: {str(e)}"
        )
        
        logger.exception(f"Unexpected error in weather query: {e}", extra={
            "request_id": request_id
        })
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "internal_server_error", 
                "hint": "An unexpected error occurred"
            }
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Custom HTTP exception handler for consistent error responses."""
    return exc.detail


# Additional error handlers for specific status codes
@app.exception_handler(401)
async def unauthorized_handler(request, exc):
    return {"error": "unauthorized", "hint": "Invalid or missing API key"}


@app.exception_handler(400)
async def bad_request_handler(request, exc):
    return {"error": "bad_request", "hint": "Invalid request parameters"}


@app.exception_handler(429)
async def rate_limit_handler(request, exc):
    return {"error": "rate_limited", "hint": "Too many requests, please try again later"}


@app.exception_handler(502)
async def bad_gateway_handler(request, exc):
    return {"error": "service_unavailable", "hint": "Weather service temporarily unavailable"}


# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info("WeatherSense API starting up")
    
    # Validate required environment variables
    required_env_vars = ["API_KEY"]
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        raise RuntimeError(f"Missing required environment variables: {missing_vars}")
    
    logger.info("WeatherSense API startup complete")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("WeatherSense API shutting down")


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=False
    )