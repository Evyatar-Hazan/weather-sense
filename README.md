# WeatherSense

A comprehensive weather analysis service that combines natural language processing, MCP (Model Context Protocol) tools, and CrewAI workflows to provide intelligent weather insights.

## 📋 Table of Contents

- [Quick Start & Installation](#-quick-start--installation)
  - [Prerequisites](#prerequisites)
  - [Local Development Setup](#local-development-setup)
  - [Quick Test](#quick-test)
- [Architecture & Components](#-architecture--components)
  - [System Overview](#system-overview)
  - [Component Mapping](#component-mapping)
  - [Core Workflows](#core-workflows)
- [Configuration](#-configuration)
  - [Environment Variables](#environment-variables)
  - [Example Configuration](#example-configuration)
- [Testing](#-testing)
  - [Test Suite Overview](#test-suite-overview)
  - [Running Tests](#running-tests)
- [Deployment & Production](#-deployment--production)
  - [Docker Deployment](#docker-deployment)
  - [Google Cloud Run](#google-cloud-run)
  - [Live Demo](#live-demo)
- [API Reference](#-api-reference)
- [Troubleshooting & FAQ](#-troubleshooting--faq)
- [Contributing](#-contributing)

## 🚀 Quick Start & Installation

### Prerequisites

| Requirement | Version | Platform Support |
|-------------|---------|------------------|
| Python | 3.11+ | Linux, macOS, Windows (WSL) |
| Memory | 2GB RAM minimum | All platforms |
| Network | Internet connection | For weather API calls |
| Disk Space | ~500MB | For dependencies |

### Local Development Setup

#### Step 1: Clone Repository
```bash
git clone https://github.com/Evyatar-Hazan/weather-sense.git
cd weather-sense
```

#### Step 2: Create Virtual Environment
```bash
# Linux/macOS
python3 -m venv .venv
source .venv/bin/activate

# Windows (WSL recommended)
python -m venv .venv
.venv\Scripts\activate
```

#### Step 3: Install Dependencies
```bash
pip install -e .

# For development (includes testing dependencies)
pip install -e ".[test]"
```

#### Step 4: Configure Environment
```bash
# For local development, you can use any API key value
export API_KEY="your-local-dev-key-here"
export LOG_LEVEL="INFO"
export TZ="UTC"

# Note: Local development accepts any API key value for testing
# Production requires a valid API key from the administrator
```

#### Step 5: Start Services
```bash
# Start FastAPI server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Alternative port if 8000 is busy
python -m uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

### Quick Test

#### Health Check
```bash
# Health check endpoint (works both locally and in production):
curl http://localhost:8000/health
# or for production direct server:
curl https://weather-sense-service-1061398738.us-central1.run.app/health
# or for production proxy (assignment-compliant):
curl https://weather-sense-proxy.weather-sense.workers.dev/healthz
# Expected: {"ok": true}
```

#### Weather Query
```bash
# Local development
curl -X POST "http://localhost:8000/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-local-dev-key" \
  -d '{"query": "weather in Tel Aviv from last Monday to Friday, metric"}'

# Production via proxy (recommended)
curl -X POST "https://weather-sense-proxy.weather-sense.workers.dev/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather in Tel Aviv from last Monday to Friday, metric"}'

# Production direct server
curl -X POST "https://weather-sense-service-1061398738.us-central1.run.app/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather in Tel Aviv from last Monday to Friday, metric"}'
```

#### Test MCP Tool Directly
```bash
echo '{"location": "Tel Aviv", "start_date": "2025-10-20", "end_date": "2025-10-24", "units": "metric"}' | \
python mcp_weather/server.py
```

## 🏗️ Architecture & Components

### System Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   FastAPI API   │    │   CrewAI Flow    │    │  MCP Weather    │
│                 │    │                  │    │     Tool        │
│ • Authentication│────│ Task A: Parser   │────│                 │
│ • Request/Response    │ Task B: MCP Client    │ • Geocoding     │
│ • Error Handling│    │ Task C: Analyst  │    │ • Weather API   │
│ • Logging       │    │                  │    │ • Caching       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### Component Mapping

| Component | File/Module | Responsibility |
|-----------|-------------|----------------|
| **API Layer** | `api/main.py` | FastAPI endpoints, request/response handling |
| **Authentication** | `api/security.py` | API key validation and security |
| **Logging** | `api/logging_config.py` | Structured JSON logging setup (API server) |
| **MCP Logging** | `mcp_weather/server.py` | Structured JSON logging setup (MCP server) |
| **CrewAI Orchestration** | `crew/flow.py` | Task coordination (A→B→C pipeline) |
| **Natural Language Parser** | `crew/parser.py` | Query parsing, date handling (legacy interface) |
| **Modular Parser Components** | `crew/date_range_parser.py` | New modular parser with improved validation |
| **Location Extraction** | `crew/location_extractor.py` | Dedicated location parsing with security validation |
| **Date Range Extraction** | `crew/date_extractor.py` | Advanced date/time parsing with natural language support |
| **Input Validation** | `crew/input_validator.py` | Comprehensive input sanitization and security checks |
| **MCP Client** | `crew/mcp_client.py` | MCP tool communication via stdio |
| **Weather Analyst** | `crew/agents.py` | Weather data analysis and summarization |
| **MCP Server** | `mcp_weather/server.py` | Stdio-based JSON communication with logging |
| **Weather Provider** | `mcp_weather/provider.py` | Open-Meteo API integration |
| **Caching Layer** | `mcp_weather/cache.py` | In-memory caching (10-min TTL) |

### Parser Architecture Refactoring

The natural language parser has been refactored from a monolithic 455-line class into modular components for better maintainability, testing, and security:

**New Modular Components:**
- **`LocationExtractor`** - Handles location parsing with coordinate validation and security checks
- **`DateRangeExtractor`** - Advanced date/time parsing supporting relative dates, weekdays, months
- **`InputValidator`** - Comprehensive input sanitization preventing injection attacks
- **`DateRangeParser`** - Central orchestrator combining all components with enhanced error handling

**Security Improvements:**
- Input length validation (max 1000 characters for queries, 200 for locations)
- XSS/injection pattern detection using regex-based security scanning
- Coordinate boundary validation (latitude: -90 to 90, longitude: -180 to 180)
- Special character sanitization while preserving valid location names
- Null byte and control character removal

**Enhanced Parsing Capabilities:**
- Better handling of complex date ranges ("from Monday to Friday")
- Improved location extraction with multiple fallback strategies
- Support for both absolute dates (2024-01-15) and relative dates (next Tuesday)
- Robust error handling with detailed validation feedback

**Backward Compatibility:**
- Legacy `parser.py` interface preserved for existing integrations
- All existing tests continue to pass without modification
- Gradual migration path for future enhancements

### Core Workflows

#### API Request Flow
1. **Authentication** → Validate API key
2. **CrewAI Pipeline** → Execute three-stage analysis
3. **Response** → Return structured JSON with summary

#### CrewAI Task Pipeline
- **Task A (Parser)** → Parse natural language → Extract location, dates, units
- **Task B (MCP Client)** → Call weather tool → Fetch weather data
- **Task C (Analyst)** → Analyze patterns → Generate summary

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | ✅ Yes | - | Authentication key for API access |
| `LOG_LEVEL` | ❌ No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PORT` | ❌ No | `8000` | Port for FastAPI server |
| `TZ` | ❌ No | `UTC` | Timezone for date calculations |
| `WEATHER_PROVIDER` | ❌ No | `open-meteo` | Weather data provider |
| `WEATHER_API_KEY` | ❌ No | - | Optional API key for weather provider |
| `DEPLOYMENT_ENV` | ❌ No | - | Set to `docker` for container mode |
| `HTTPS_ONLY` | ❌ No | `true` | Enforce HTTPS redirects (set to `false` for local dev) |

### Rate Limiting and Resilience

The API implements comprehensive protection and retry mechanisms:

**Rate Limiting:**
| Endpoint | Rate Limit | Scope |
|----------|------------|-------|
| `POST /v1/weather/ask` | 30 requests/minute | Per IP address |
| `GET /health` | No limit | All requests |

**Retry Logic:**
- **API Calls**: Exponential backoff for weather API failures (max 5 attempts)
- **MCP Communication**: Retry logic for subprocess/process communication (max 3 attempts)
- **Network Errors**: Automatic recovery from connection timeouts and temporary failures
- **Jitter**: Random delays to prevent thundering herd effects

**Rate Limit Response** (HTTP 429):
```json
{
  "detail": "Rate limit exceeded. Try again later.",
  "error_type": "rate_limited",
  "retry_after": 60
}
```

### Example Configuration

Create a `.env` file in the project root:

```bash
# Required - For local development, any value works
API_KEY=your-local-dev-key-here

# Optional
LOG_LEVEL=INFO
PORT=8000
TZ=UTC
WEATHER_PROVIDER=open-meteo

# For Docker deployment
DEPLOYMENT_ENV=docker
```

#### 🔑 API Key Configuration Notes

**Local Development**:
- You can use **any API key value** (e.g., `test-key`, `dev-123`, `local-development`)
- The application validates that an API key exists but doesn't verify it against a database
- This allows free local testing and development

**Production Environment**:
- Requires a **valid API key** issued by the service administrator
- API keys are validated against the configured production key
- Contact admin for production access credentials

**Example Local Setup**:
```bash
# Simple local development
export API_KEY="my-local-test-key"

# Or create a .env file
echo 'API_KEY="local-dev-key-123"' > .env
echo 'LOG_LEVEL="DEBUG"' >> .env
```

### Security Features

WeatherSense includes comprehensive security measures for production deployment:

**HTTPS Enforcement**:
- Automatic HTTP to HTTPS redirects in production (`HTTPS_ONLY=true`)
- Can be disabled for local development (`HTTPS_ONLY=false`)
- Health checks and localhost requests exempted from redirects

**Security Headers**:
All responses include essential security headers:
- `Strict-Transport-Security`: Enforces HTTPS for browsers
- `X-Content-Type-Options`: Prevents MIME sniffing attacks
- `X-Frame-Options`: Protects against clickjacking
- `X-XSS-Protection`: Enables browser XSS filtering
- `Referrer-Policy`: Controls referrer information leakage

**Input Sanitization & Validation**:
- Query length limits (1-1000 characters with Pydantic validation)
- XSS prevention with HTML entity escaping
- JavaScript pattern removal (`javascript:`, `onload=`, etc.)
- Control character filtering (null bytes, non-printable chars)
- Coordinate validation (latitude: -90 to 90, longitude: -180 to 180)
- Location name sanitization (dangerous characters removed)
- Unicode support for international location names

**Example Production Security Configuration**:
```bash
# Enable HTTPS enforcement (default in production)
HTTPS_ONLY=true

# For local development (disable HTTPS enforcement)
HTTPS_ONLY=false
```

## 📊 Monitoring & Metrics

### Prometheus Metrics

WeatherSense provides comprehensive Prometheus metrics for monitoring and observability:

**Metrics Endpoint**: `/metrics`
- No authentication required
- Standard Prometheus format
- Real-time metrics collection

**Available Metrics**:

| Metric | Type | Description | Labels |
|--------|------|-------------|---------|
| `weathersense_app_info_info` | Info | Application information | `version`, `environment`, `application` |
| `weathersense_requests_total` | Counter | Total HTTP requests | `method`, `endpoint`, `status_code` |
| `weathersense_request_duration_seconds` | Histogram | HTTP request duration | `method`, `endpoint` |
| `weathersense_weather_queries_total` | Counter | Weather queries processed | `status`, `location_type` |
| `weathersense_weather_query_duration_seconds` | Histogram | Weather query duration | `status` |
| `weathersense_health_checks_total` | Counter | Health check requests | `status` |
| `weathersense_mcp_tool_calls_total` | Counter | MCP tool calls | `tool_name`, `status` |
| `weathersense_mcp_tool_duration_seconds` | Histogram | MCP tool duration | `tool_name` |
| `weathersense_errors_total` | Counter | Application errors | `error_type`, `component` |

**Example Metrics Usage**:
```bash
# Check application metrics
curl http://localhost:8000/metrics

# Example queries for monitoring:
# - Request rate: rate(weathersense_requests_total[5m])
# - Error rate: rate(weathersense_weather_queries_total{status="error"}[5m])
# - Response time P95: histogram_quantile(0.95, weathersense_request_duration_seconds_bucket)
# - Query success rate: weathersense_weather_queries_total{status="success"} / on() weathersense_weather_queries_total
```

**Cloud Run Integration**:
- Metrics automatically collected in Google Cloud environments
- Compatible with Google Cloud Monitoring
- Can be scraped by external Prometheus instances
- No additional configuration required

## 🧪 Testing

### Test Suite Overview

| Test File | Purpose | Type | Coverage |
|-----------|---------|------|----------|
| `test_api_e2e.py` | Complete API workflow | E2E | Full request-response cycle |
| `test_deployment_integration.py` | Deployment validation | Integration | Container setup, environment |
| `test_documentation_only.py` | Documentation validation | Unit | README, config validation |
| `test_mcp_cache.py` | Caching functionality | Unit | TTL, key generation |
| `test_mcp_client.py` | MCP tool communication | Integration | Stdio interface, timeout handling |
| `test_mcp_server.py` | MCP server functionality | Unit | JSON processing, error handling |
| `test_mcp_stdio.py` | MCP stdio communication | Integration | Input/output handling |
| `test_parser.py` | Natural language parsing logic | Unit | Date parsing, location extraction |
| `test_pytest_integration.py` | Test framework integration | Integration | Pytest configuration |
| `test_range_parser.py` | Date range parsing | Unit | Relative dates, validation |
| `test_weather_analyst.py` | Weather analysis logic | Unit | Pattern detection, summarization |
| `test_weather_api_integration.py` | Weather API integration | Integration | API calls, data validation |
| `test_weather_fetcher.py` | Weather data fetching | Unit | Data retrieval logic |
| `test_weather_provider.py` | Weather provider interface | Integration | Open-Meteo API, geocoding |

### Running Tests

#### All Tests
```bash
# Install test dependencies
pip install -e ".[test]"

# Run complete test suite
pytest

# With coverage report
pytest --cov=. --cov-report=html --cov-report=term
```

#### Specific Test Categories
```bash
# Unit tests only
pytest tests/test_parser.py tests/test_mcp_cache.py tests/test_weather_analyst.py tests/test_range_parser.py

# Integration tests
pytest tests/test_mcp_client.py tests/test_weather_provider.py tests/test_mcp_stdio.py tests/test_weather_api_integration.py

# End-to-end tests
pytest tests/test_api_e2e.py tests/test_deployment_integration.py

# Documentation and configuration
pytest tests/test_documentation_only.py tests/test_pytest_integration.py

# MCP-specific tests
pytest tests/test_mcp_server.py tests/test_mcp_client.py tests/test_mcp_stdio.py tests/test_mcp_cache.py

# Weather-specific tests
pytest tests/test_weather_provider.py tests/test_weather_fetcher.py tests/test_weather_analyst.py tests/test_weather_api_integration.py

# Quick validation
python validate_deployment.py
```

#### Test Output Examples
```bash
# Expected successful output
✅ Documentation & Configuration Validation: PASSED
✅ MCP Server Stdio Communication Test: PASSED
🎉 DEPLOYMENT VALIDATION SUCCESSFUL!
```

## � Security

### Security Validation Framework

WeatherSense includes a comprehensive security validation system to protect against malicious inputs and ensure safe operation:

#### Security Features
- **XSS Prevention**: Automatic detection and sanitization of script injection attempts
- **SQL Injection Protection**: Pattern-based detection of SQL injection attempts
- **Input Sanitization**: Removal of dangerous characters while preserving valid input
- **Coordinate Validation**: Geographic boundary validation for latitude/longitude values
- **Rate Limiting**: 30 requests per minute per IP address with proxy header support
- **Input Length Limits**: Maximum query length (1000 chars) and location length (200 chars)

#### Security Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **SecurityValidator** | `utils/security.py` | Core security validation framework |
| **Rate Limiter** | `api/main.py` | Request rate limiting with proxy support |
| **Input Validator** | `crew/input_validator.py` | Modular input validation |
| **Security Tests** | `tests/test_security_validation.py` | Comprehensive security testing |

#### Protected Input Types

```python
# XSS Prevention Examples
malicious_input = "<script>alert('xss')</script> weather in London"
result = parser.parse_query(malicious_input)  # ❌ Blocked/Sanitized

# SQL Injection Prevention
malicious_query = "weather in London'; DROP TABLE users; --"
result = parser.parse_query(malicious_query)  # ❌ Blocked/Sanitized

# Coordinate Validation
invalid_coords = "weather at 91.0, 34.78"  # ❌ Invalid latitude > 90
valid_coords = "weather at 32.08, 34.78"   # ✅ Valid coordinates

# Rate Limiting
# More than 30 requests/minute from same IP = HTTP 429
```

#### Rate Limiting Configuration

```python
# Rate limiting settings in api/main.py
RATE_LIMIT_REQUESTS = 30     # requests per minute
RATE_LIMIT_WINDOW = 60       # time window in seconds

# Proxy support for Cloud Run deployment
def get_client_ip(request):
    # Checks X-Forwarded-For, X-Real-IP headers
    # Falls back to client IP for local development
```

#### Security Testing

```bash
# Run security validation tests
pytest tests/test_security_validation.py -v

# Test categories include:
# - XSS prevention
# - SQL injection protection
# - Coordinate validation
# - Long input handling
# - Special character handling
# - Empty input validation
# - Normal query functionality
```

## 🚀 Deployment & Production

### Docker Deployment

#### Local Docker Setup
```bash
# Build the image
docker build -t weather-sense .

# Run locally
docker run -p 8000:8000 \
  -e API_KEY="your-secret-api-key" \
  -e LOG_LEVEL="INFO" \
  weather-sense

# Test container
curl http://localhost:8000/health
```

### Google Cloud Run

#### Prerequisites Checklist
- [ ] Google Cloud Account with billing enabled
- [ ] Google Cloud SDK installed (`gcloud`)
- [ ] Docker installed and running
- [ ] Project repository cloned locally

#### Quick Deployment
```bash
# Set environment variables
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"
export SERVICE_NAME="weather-sense"
export API_KEY="your-secure-api-key-here"

# Configure gcloud
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com
gcloud auth configure-docker

# Build and push
docker build --platform linux/amd64 -t gcr.io/$PROJECT_ID/$SERVICE_NAME:latest .
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

# Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="API_KEY=$API_KEY,LOG_LEVEL=INFO,DEPLOYMENT_ENV=docker" \
  --memory 1Gi \
  --cpu 1000m \
  --port 8000 \
  --timeout 300s
```

### Live Demo

🌍 **Production Instance**: https://weather-sense-service-ektuy7j2kq-uc.a.run.app
🔑 **Demo API Key (Valid until Nov 15, 2025)**: `interview-demo-20251029-974213a2e493d09f`

#### Try it Now
```bash
# Quick test
curl -X POST "https://weather-sense-service-ektuy7j2kq-uc.a.run.app/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: interview-demo-20251029-974213a2e493d09f" \
  -d '{"query": "weather in Tel Aviv for today"}'

# Interactive docs
open https://weather-sense-service-ektuy7j2kq-uc.a.run.app/docs
```

## 📚 API Reference

### Access Methods

WeatherSense offers two access patterns:

1. **Direct Server Access** (Google Cloud Run)
   - URL: `https://weather-sense-service-1061398738.us-central1.run.app`
   - Best for: Production integrations, high-volume usage
   - Features: Full endpoint availability

2. **Proxy Access** (Cloudflare Worker - Recommended for Assignment)
   - URL: `https://weather-sense-proxy.weather-sense.workers.dev`
   - Best for: Assignment compliance, edge performance, global access
   - Features: Transparent request forwarding with edge caching

### Authentication

All API requests require the `x-api-key` header:
```bash
curl -H "x-api-key: your-secret-api-key" ...
```

### Endpoints

#### Health Check Endpoints

**Direct Server (Cloud Run)**
```bash
# Health check (Cloud Run direct)
curl https://weather-sense-service-1061398738.us-central1.run.app/health
# Response: {"ok": true}
```

**Proxy (Cloudflare Worker)**
```bash
# Health check (Assignment-compliant endpoint)
curl https://weather-sense-proxy.weather-sense.workers.dev/healthz
# Response: {"ok": true}
```

**Purpose**: Health check endpoints
**Authentication**: ❌ Not required

**Note**: Cloud Run reserves paths ending with 'z' (like `/healthz`), so we use `/health` for direct access and the proxy provides `/healthz` for assignment compliance. See [Cloud Run Known Issues](https://cloud.google.com/run/docs/known-issues#ah) for details.

#### Weather Query Endpoints

**Direct Server POST /v1/weather/ask**
```bash
curl -X POST "https://weather-sense-service-1061398738.us-central1.run.app/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather in Tel Aviv from last Monday to Friday, metric"}'
```

**Proxy POST /v1/weather/ask (Recommended)**
```bash
curl -X POST "https://weather-sense-proxy.weather-sense.workers.dev/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather in Tel Aviv from last Monday to Friday, metric"}'
```

**Purpose**: Process natural language weather queries
**Authentication**: ✅ Required

#### GET /health, /ping
**Purpose**: Health check endpoints
**Authentication**: ❌ Not required

**Response**:
```json
{"ok": true}
```

**Note**: Cloud Run reserves paths ending with 'z' (like `/healthz`), so we use `/health` instead. See [Cloud Run Known Issues](https://cloud.google.com/run/docs/known-issues#ah) for details.

#### POST /v1/weather/ask
**Purpose**: Process natural language weather queries
**Authentication**: ✅ Required

**Request Body**:
```json
{
  "query": "Summarize weather in Tel Aviv from last Monday to Friday, metric"
}
```

**Successful Response (200)**:
```json
{
  "summary": "Weather summary for Tel Aviv, IL from October 20 to October 24, 2025...",
  "params": {
    "location": "Tel Aviv, IL",
    "start_date": "2025-10-20",
    "end_date": "2025-10-24",
    "units": "metric"
  },
  "data": {
    "daily": [
      {
        "date": "2025-10-20",
        "tmin": 20.1,
        "tmax": 28.3,
        "precip_mm": 0.0,
        "wind_max_kph": 20.0,
        "code": 1
      }
    ],
    "source": "open-meteo"
  },
  "confidence": 0.87,
  "tool_used": "weather.get_range",
  "latency_ms": 1320,
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

**Error Responses**:
| Status | Error Type | Description |
|--------|------------|-------------|
| 400 | `range_too_large` | Date span > 31 days |
| 400 | `invalid_location` | Location not found |
| 400 | `invalid_date_range` | Invalid date format |
| 401 | `unauthorized` | Missing/invalid API key |
| 429 | `rate_limited` | Too many requests |
| 502 | `service_unavailable` | Weather service error |

### Query Examples

The service understands various natural language patterns:

#### Using Proxy (Recommended for Assignment)
```bash
# Relative dates
curl -X POST "https://weather-sense-proxy.weather-sense.workers.dev/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather in New York from last Monday to Friday"}'

curl -X POST "https://weather-sense-proxy.weather-sense.workers.dev/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "Tel Aviv weather this week"}'

# Specific dates with units
curl -X POST "https://weather-sense-proxy.weather-sense.workers.dev/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather in Paris from October 15 to October 20, imperial"}'

# Coordinates
curl -X POST "https://weather-sense-proxy.weather-sense.workers.dev/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather at 40.7128,-74.0060 from Monday to Wednesday"}'
```

#### Using Direct Server
```bash
# Same queries work with direct server URL:
curl -X POST "https://weather-sense-service-1061398738.us-central1.run.app/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "London weather from yesterday to today"}'
```

#### Common Query Patterns
```bash
# Relative dates
"weather in New York from last Monday to Friday"
"Tel Aviv weather this week"
"London weather from yesterday to today"

# Specific dates
"weather in Paris from October 15 to October 20, imperial"
"Tokyo temperature between 2025-10-01 and 2025-10-07"

# Coordinates
"weather at 40.7128,-74.0060 from Monday to Wednesday"
```

## ❓ Troubleshooting & FAQ

### Common Installation Issues

#### 1. Command Not Found
**Problem**: `python: command not found`
**Solution**: Use `python3` on Ubuntu/Debian systems:
```bash
python3 -m venv .venv
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 2. Port Already in Use
**Problem**: `Address already in use` or port 8000 busy
**Solution**: Use different port:
```bash
python -m uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
curl http://localhost:8080/health  # Test with new port
```

#### 3. Module Not Found
**Problem**: Import errors after installation
**Solution**: Verify virtual environment:
```bash
source .venv/bin/activate  # Should show (.venv) in prompt
which python              # Should point to .venv/bin/python
pip list | grep weather-sense  # Should show package
```

#### 4. Environment Setup
**Problem**: `uvicorn: command not found`
**Solution**: Reinstall in virtual environment:
```bash
cd weather-sense  # Ensure correct directory
source .venv/bin/activate
pip install -e .
```

### Runtime Issues

#### 5. API Authentication Errors
**Problem**: 401 Unauthorized responses
**Solution**: Verify API key configuration:
```bash
echo $API_KEY  # Should show your key
export API_KEY="your-local-dev-key"  # For local development, any value works

# For local testing, try:
export API_KEY="test-local-123"
export API_KEY="dev-key"
export API_KEY="my-development-key"
```

**Note**: Local development accepts any API key value. Production requires a valid key from admin.

#### 6. MCP Tool Failures
**Problem**: MCP timeout or communication errors
**Solution**: Test MCP tool directly:
```bash
echo '{"location": "Tokyo", "start_date": "2025-10-25", "end_date": "2025-10-26", "units": "metric"}' | \
python mcp_weather/server.py
```

#### 7. Docker Issues
**Problem**: Container startup failures
**Solution**: Check logs and environment:
```bash
docker logs <container-id>
docker run -it weather-sense /bin/bash  # Debug container
```

### Performance Tips

- ✅ **Caching**: Weather data cached for 10 minutes
- ✅ **Timeouts**: MCP calls timeout after 30 seconds
- ✅ **Rate Limiting**: Implement client-side rate limiting
- ✅ **Memory**: Cloud Run instances use 1GB RAM

### Warning Signs

- ⚠️ **High Latency**: Check MCP tool responsiveness
- ⚠️ **Memory Usage**: Monitor container memory consumption
- ⚠️ **API Errors**: Watch for weather service timeouts

## 🤝 Contributing

### Development Workflow
1. **Fork** the repository
2. **Create** feature branch: `git checkout -b feature-name`
3. **Add tests** for new functionality
4. **Run tests**: `pytest --cov=.`
5. **Commit** changes: `git commit -m "Add feature"`
6. **Submit** pull request

### Code Standards
- Follow PEP 8 Python style guidelines
- Add type hints for new functions
- Include docstrings for public methods
- Maintain test coverage above 80%

### Adding Features
| Component | File | Purpose |
|-----------|------|---------|
| **Query Patterns** | `crew/parser.py` | Extend DateRangeParser |
| **Weather Providers** | `mcp_weather/provider.py` | New API integrations |
| **Analysis Logic** | `crew/agents.py` | Enhanced WeatherAnalyst |
| **API Endpoints** | `api/main.py` | New routes and responses |

## 📋 Project Summary

WeatherSense is a production-ready weather analysis service that demonstrates:

- **🤖 AI Integration**: Natural language processing with CrewAI workflows
- **🔌 MCP Protocol**: Standards-compliant tool communication via stdio
- **🌐 Cloud Native**: Docker containerization with Google Cloud Run deployment

**Key Capabilities**:
- Parse natural language weather queries ("weather in NYC this week")
- Fetch real-time weather data with intelligent caching
- Generate comprehensive weather summaries with confidence scores

**Production Features**:
- Structured logging with request tracking
- API authentication and error handling
- Auto-scaling deployment with health monitoring

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Model Context Protocol (MCP) Spec](https://spec.modelcontextprotocol.io/)
- [CrewAI Framework](https://github.com/joaomdmoura/crewAI)
- [Open-Meteo Weather API](https://open-meteo.com/en/docs)
- [Google Cloud Run Guide](https://cloud.google.com/run/docs)

## 📄 License

This project is licensed under the MIT License. See LICENSE file for details.
