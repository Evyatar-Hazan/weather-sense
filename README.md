# WeatherSense

A comprehensive weather analysis service that combines natural language processing, MCP (Model Context Protocol) tools, and CrewAI workflows to provide intelligent weather insights.

## 📋 Deliverables

✅ **1. Repository URL**: https://github.com/Evyatar-Hazan/weather-sense  
✅ **2. Cloud Run URL**: https://weather-sense-service-ektuy7j2kq-uc.a.run.app  
✅ **3. Test API Key**: `test-api-key-weather-sense-production`  
✅ **4. Complete Documentation**: README.md + NOTES.md with deployment steps

## Features

- **Natural Language Queries**: Ask for weather in plain English
- **MCP Integration**: Stdio-based weather data tool 
- **CrewAI Workflow**: Three-stage analysis pipeline (Parse → Fetch → Analyze)
- **FastAPI REST API**: Production-ready HTTP service
- **Structured Logging**: JSON-formatted logs with request tracking
- **In-Memory Caching**: 10-minute TTL for weather data
- **Docker Support**: Container-ready with Google Cloud Run deployment
- **Comprehensive Testing**: Unit and integration tests

## Architecture

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

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (optional)
- Google Cloud SDK (for deployment)

### Local Development

1. **Clone and setup environment**:
```bash
git clone https://github.com/Evyatar-Hazan/weather-sense.git
cd weather-sense
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e .
```

2. **Set environment variables**:
```bash
export API_KEY="your-secret-api-key"
export LOG_LEVEL="INFO"  # Optional, defaults to INFO
export LOG_LEVEL="INFO"
export TZ="UTC"
```

3. **Run the application**:
```bash
# Start the FastAPI server
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

4. **Test the service**:
```bash
# Health check
curl http://localhost:8000/healthz

# Weather query
curl -X POST "http://localhost:8000/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: your-secret-api-key" \
  -d '{"query": "weather in Tel Aviv from last Monday to Friday, metric"}'
```

### Testing

Run the test suite:

```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests
pytest

# Run specific test files
pytest tests/test_parser.py
pytest tests/test_mcp_client.py  
pytest tests/test_api_e2e.py

# Run with coverage
pytest --cov=. --cov-report=html
```

### MCP Tool Testing

Test the MCP weather tool directly:

```bash
# Test MCP tool via stdin/stdout
echo '{"location": "Tel Aviv", "start_date": "2025-10-20", "end_date": "2025-10-24", "units": "metric"}' | python mcp_weather/server.py
```

## 🚀 Live Demo

**Production URL**: https://weather-sense-service-ektuy7j2kq-uc.a.run.app  
**API Key**: `test-api-key-weather-sense-production`

### Try it now:

```bash
# Test the weather service
curl -X POST "https://weather-sense-service-ektuy7j2kq-uc.a.run.app/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: test-api-key-weather-sense-production" \
  -d '{"query": "weather in Tel Aviv for today"}'

# View API documentation
open https://weather-sense-service-ektuy7j2kq-uc.a.run.app/docs
```

## API Usage

### Authentication

All API requests require the `x-api-key` header:

```bash
curl -H "x-api-key: your-secret-api-key" ...
```

### Endpoints

#### GET /healthz

Health check endpoint.

**Response:**
```json
{"ok": true}
```

#### POST /v1/weather/ask

Process natural language weather queries.

**Request:**
```json
{
  "query": "Summarize weather in Tel Aviv from last Monday to Friday, metric"
}
```

**Successful Response (200):**
```json
{
  "summary": "Weather summary for Tel Aviv, IL from October 20 to October 24, 2025: The period was generally warm with dry conditions and calm winds. Average temperatures ranged from 20.1°C to 28.3°C. Notable events: October 22 had heavy rain.",
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

**Error Response (400/429/502):**
```json
{
  "error": "range_too_large",
  "hint": "Span must be <= 31 days"
}
```

### Query Examples

The service understands various natural language patterns:

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

## Complete Deployment Guide

This section provides a complete, step-by-step guide for deploying WeatherSense to Google Cloud Run from development to production.

### Prerequisites Checklist

Before starting deployment, ensure you have:

- [ ] **Google Cloud Account** with billing enabled
- [ ] **Google Cloud SDK** installed and configured
- [ ] **Docker** installed and running
- [ ] **Project repository** cloned locally
- [ ] **API key** generated for your service
- [ ] **Basic Cloud Run knowledge** (recommended)

### Step 1: Environment Setup

#### 1.1 Install Required Tools

```bash
# Install Google Cloud SDK (if not installed)
curl https://sdk.cloud.google.com | bash
exec -l $SHELL

# Install Docker (Ubuntu/Debian)
sudo apt update
sudo apt install docker.io
sudo usermod -aG docker $USER
# Log out and back in for group changes

# Verify installations
gcloud --version
docker --version
```

#### 1.2 Configure Google Cloud Project

```bash
# Set your project variables
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"  # Choose your preferred region
export SERVICE_NAME="weather-sense"
export API_KEY="your-secure-api-key-here"

# Login to Google Cloud
gcloud auth login

# Set the project
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable cloudbuild.googleapis.com
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Configure Docker authentication
gcloud auth configure-docker
```

### Step 2: Pre-Deployment Validation

#### 2.1 Test Locally First

```bash
# Clone repository (if not done)
git clone https://github.com/Evyatar-Hazan/weather-sense.git
cd weather-sense

# Setup Python environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .

# Test locally
export API_KEY="test-key-local"
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# In another terminal, test endpoints
curl http://localhost:8000/healthz
curl -X POST "http://localhost:8000/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: test-key-local" \
  -d '{"query": "weather in Tel Aviv today"}'
```

#### 2.2 Run Deployment Validation Tests

```bash
# Install test dependencies
pip install -e ".[test]"

# Run comprehensive validation
python validate_deployment.py

# Expected output: All tests should pass
# ✅ Documentation & Configuration Validation: PASSED
# ✅ MCP Server Stdio Communication Test: PASSED
# 🎉 DEPLOYMENT VALIDATION SUCCESSFUL!
```

### Step 3: Docker Image Build and Test

#### 3.1 Build Docker Image

```bash
# Build for your platform
docker build -t weather-sense:latest .

# For Cloud Run (multi-platform)
docker build \
  --platform linux/amd64 \
  -t gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
  .

# Verify image was created
docker images | grep weather-sense
```

#### 3.2 Test Docker Image Locally

```bash
# Run container locally
docker run -d \
  --name weather-test \
  -p 8000:8000 \
  -e API_KEY="$API_KEY" \
  -e LOG_LEVEL="INFO" \
  gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

# Wait for startup (10-15 seconds)
sleep 15

# Test endpoints
curl -f http://localhost:8000/healthz

curl -X POST "http://localhost:8000/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"query": "weather in New York today"}'

# Check logs
docker logs weather-test

# Clean up test container
docker stop weather-test && docker rm weather-test
```

### Step 4: Push to Google Container Registry

```bash
# Push image to GCR
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:latest

# Verify push was successful
gcloud container images list --repository=gcr.io/$PROJECT_ID
```

### Step 5: Deploy to Cloud Run

#### 5.1 Initial Deployment

```bash
# Deploy service with all required configurations
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="API_KEY=$API_KEY,LOG_LEVEL=INFO,DEPLOYMENT_ENV=docker,TZ=UTC" \
  --memory 1Gi \
  --cpu 1000m \
  --min-instances 0 \
  --max-instances 10 \
  --port 8000 \
  --timeout 300s \
  --concurrency 100 \
  --max-retries 3

# Wait for deployment (1-3 minutes)
echo "Waiting for deployment to complete..."
```

#### 5.2 Verify Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --format 'value(status.url)')

echo "Service deployed at: $SERVICE_URL"

# Test health endpoint (no authentication required)
curl -f "$SERVICE_URL/healthz"

# Expected response: {"ok":true}
```

#### 5.3 Test Production API

```bash
# Test weather endpoint (requires API key)
curl -X POST "$SERVICE_URL/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"query": "weather in San Francisco this week"}' \
  | jq '.'

# Expected: JSON response with weather summary and data
```

### Step 6: Post-Deployment Configuration

#### 6.1 Set Up Custom Domain (Optional)

```bash
# Map custom domain (if you have one)
gcloud run domain-mappings create \
  --service $SERVICE_NAME \
  --domain your-domain.com \
  --region $REGION
```

#### 6.2 Configure Monitoring

```bash
# Enable Cloud Monitoring (automatic for Cloud Run)
# View service metrics in Google Cloud Console

# Set up alerting (optional)
gcloud alpha monitoring policies create \
  --policy-from-file=monitoring-policy.yaml
```

### Step 7: Testing and Verification

#### 7.1 Comprehensive Production Testing

```bash
# Health check
echo "Testing health endpoint..."
curl -f "$SERVICE_URL/healthz" || echo "❌ Health check failed"

# Authentication test
echo "Testing authentication..."
curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$SERVICE_URL/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -d '{"query": "test"}' | grep -q "401" && echo "✅ Auth required" || echo "❌ Auth not working"

# Valid request test
echo "Testing valid weather request..."
RESPONSE=$(curl -s -X POST "$SERVICE_URL/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"query": "weather in London today"}')

echo $RESPONSE | jq '.summary' > /dev/null && echo "✅ API working" || echo "❌ API error"

# Performance test
echo "Testing response time..."
TIME=$(curl -s -o /dev/null -w "%{time_total}" \
  -X POST "$SERVICE_URL/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"query": "weather in Tokyo today"}')

echo "Response time: ${TIME}s"
```

#### 7.2 Load Testing (Optional)

```bash
# Simple load test with curl
echo "Running basic load test..."
for i in {1..10}; do
  curl -s -X POST "$SERVICE_URL/v1/weather/ask" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $API_KEY" \
    -d '{"query": "weather in city'$i' today"}' &
done
wait
echo "Load test completed"
```

### Step 8: Monitoring and Maintenance

#### 8.1 View Logs

```bash
# Real-time logs
gcloud run services logs read $SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --follow

# Recent logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
  --project=$PROJECT_ID \
  --limit=50 \
  --format="value(timestamp,textPayload)"
```

#### 8.2 Monitor Performance

```bash
# Service status
gcloud run services describe $SERVICE_NAME \
  --platform managed \
  --region $REGION

# Check metrics in Cloud Console:
# https://console.cloud.google.com/run/detail/$REGION/$SERVICE_NAME
```

### Step 9: Updates and Rollbacks

#### 9.1 Deploy Updates

```bash
# Build new version
docker build --platform linux/amd64 -t gcr.io/$PROJECT_ID/$SERVICE_NAME:v2 .
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:v2

# Deploy with zero downtime
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME:v2 \
  --platform managed \
  --region $REGION
```

#### 9.2 Rollback if Needed

```bash
# List revisions
gcloud run revisions list --service=$SERVICE_NAME --region=$REGION

# Rollback to previous revision
gcloud run services update-traffic $SERVICE_NAME \
  --to-revisions=REVISION_NAME=100 \
  --region=$REGION
```

### Troubleshooting Common Issues

| Issue | Solution |
|-------|----------|
| **Build fails** | Check Dockerfile syntax, ensure all files exist |
| **Push fails** | Verify `gcloud auth configure-docker` was run |
| **Deploy fails** | Check environment variables, memory/CPU limits |
| **API returns 503** | Check logs, may need more memory or CPU |
| **Authentication issues** | Verify API_KEY environment variable is set |
| **MCP timeouts** | Increase timeout or check MCP server logs |

### Security Best Practices

- ✅ Use strong, unique API keys
- ✅ Enable Cloud Run IAM for additional security layers
- ✅ Regularly rotate API keys
- ✅ Monitor access logs for suspicious activity
- ✅ Keep Docker images updated
- ✅ Use least-privilege service accounts

### Cost Optimization

- 🔧 Set appropriate min/max instances (0-10 recommended)
- 🔧 Use CPU throttling (--cpu-throttling)
- 🔧 Set request timeout appropriately (--timeout 300s)
- 🔧 Monitor usage and adjust resources as needed

---

## Docker Deployment

### Build and Run Locally

```bash
# Build the image
docker build -t weather-sense .

# Run the container
docker run -p 8000:8000 \
  -e API_KEY="your-secret-api-key" \
  -e LOG_LEVEL="INFO" \
  weather-sense
```

### Google Cloud Run Deployment

WeatherSense is designed for deployment on Google Cloud Run as a single Docker image that launches both the API server and spawns the MCP server as a child process using stdio communication.

#### Prerequisites

- Google Cloud SDK installed and configured
- Docker installed
- A Google Cloud Project with billing enabled
- Cloud Run API enabled

#### Deployment Steps

1. **Setup Google Cloud environment**:
```bash
# Set your project ID and region
export PROJECT_ID="your-gcp-project-id"
export REGION="us-central1"  # or your preferred region
export SERVICE_NAME="weather-sense"
export API_KEY="your-secure-api-key-here"

# Configure gcloud CLI
gcloud config set project $PROJECT_ID
gcloud services enable run.googleapis.com
gcloud auth configure-docker
```

2. **Build and push Docker image**:
```bash
# Build the Docker image with Cloud Run optimizations
docker build \
  --platform linux/amd64 \
  -t gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
  .

# Push to Google Container Registry
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME:latest
```

3. **Deploy to Cloud Run with exact configuration**:
```bash
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars="API_KEY=$API_KEY,LOG_LEVEL=INFO,DEPLOYMENT_ENV=docker" \
  --memory 1Gi \
  --cpu 1000m \
  --min-instances 0 \
  --max-instances 10 \
  --port 8000 \
  --timeout 300s \
  --concurrency 100
```

### 🎯 Current Live Deployment

**WeatherSense is already deployed and available:**

- **🌍 Service URL**: `https://weather-sense-service-ektuy7j2kq-uc.a.run.app`
- **🔑 Test API Key**: `test-api-key-weather-sense-production`
- **📍 Project**: `weather-sense-app-1761757473`
- **🌎 Region**: `us-central1`

**Quick Test:**
```bash
curl -X POST "https://weather-sense-service-ektuy7j2kq-uc.a.run.app/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: test-api-key-weather-sense-production" \
  -d '{"query": "weather in Tokyo tomorrow"}'
```

**🔍 Interactive API Docs**: https://weather-sense-service-ektuy7j2kq-uc.a.run.app/docs

4. **Verify deployment**:
```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --format 'value(status.url)')

echo "Service deployed at: $SERVICE_URL"

# Test health check (should work without authentication)
curl -f "$SERVICE_URL/healthz"

# Test weather query (requires x-api-key header)
curl -X POST "$SERVICE_URL/v1/weather/ask" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"query": "weather in San Francisco this week"}' \
  | jq '.'
```

#### Cloud Run Configuration Details

- **Authentication**: Allows unauthenticated invocations (as required), but API endpoints require `x-api-key` header
- **Process Management**: Single Docker image runs both API server and MCP server as child process
- **Communication**: MCP server communicates via stdio (stdin/stdout) as required
- **Scaling**: Auto-scales from 0 to 10 instances based on traffic
- **Memory**: 1GB per instance (sufficient for weather data processing)
- **CPU**: 1 vCPU allocated per instance
- **Timeout**: 5 minutes for long-running weather analysis requests

#### Environment Variables for Production

| Variable | Value | Purpose |
|----------|-------|---------|
| `API_KEY` | Your secure key | Required for API authentication |
| `LOG_LEVEL` | `INFO` | Production logging level |
| `DEPLOYMENT_ENV` | `docker` | Enables persistent MCP server mode |
| `TZ` | `UTC` | Timezone for consistent date handling |

#### Monitoring and Logs

```bash
# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=$SERVICE_NAME" \
  --project=$PROJECT_ID \
  --limit=50

# Monitor service metrics
gcloud run services describe $SERVICE_NAME \
  --platform managed \
  --region $REGION
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `API_KEY` | Yes | - | Authentication key for API access |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `PORT` | No | `8000` | Port for FastAPI server |
| `TZ` | No | `UTC` | Timezone for date calculations |
| `WEATHER_PROVIDER` | No | `open-meteo` | Weather data provider |
| `WEATHER_API_KEY` | No | - | Optional API key for weather provider |

## Architecture Details

### CrewAI Workflow

**Task A - Natural Language Parser** (`crew/parser.py`):
- Parses natural language queries for location, dates, and units
- Handles relative dates ("last Monday", "this week")
- Validates date ranges (≤ 31 days)
- Returns structured parameters or error messages

**Task B - MCP Weather Client** (`crew/mcp_client.py`):
- Calls MCP weather tool via subprocess (stdin/stdout)
- Handles timeouts and process errors
- Measures call duration for logging
- Combines parameters with weather data

**Task C - Weather Analyst** (`crew/agents.py`):
- Analyzes weather patterns (hot/cool, wet/dry, windy/calm)
- Identifies extremes and notable weather events  
- Generates 150-250 word summaries
- Calculates confidence scores

### MCP Weather Tool

**Server** (`mcp_weather/server.py`):
- Stdio-based JSON communication
- Structured logging with request IDs
- Input validation and error handling

**Provider** (`mcp_weather/provider.py`):
- Open-Meteo API integration
- Geocoding via coordinates or city names
- Weather data fetching with unit conversion

**Cache** (`mcp_weather/cache.py`):
- In-memory caching with 10-minute TTL
- Key generation from lat/lon/dates/units
- Automatic expiration handling

### Error Handling

The service provides structured error responses:

- **400 Bad Request**: Invalid parameters, missing location, range too large
- **401 Unauthorized**: Missing or invalid API key
- **429 Too Many Requests**: Rate limiting (if implemented)
- **502 Bad Gateway**: Weather service unavailable, MCP timeouts
- **500 Internal Server Error**: Unexpected errors

## Monitoring and Logging

### Structured Logging

All logs are JSON-formatted with fields:
- `timestamp`: ISO 8601 timestamp
- `level`: Log level (INFO, ERROR, etc.)
- `message`: Human-readable message
- `request_id`: Unique request identifier
- `task`: Component name (weather_query, parser, etc.)
- `duration_ms`: Operation duration
- `status`: Operation status (started, success, error)

### Log Examples

```json
{"timestamp":"2025-10-28T10:30:00","level":"INFO","message":"Weather query completed successfully","request_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","task":"weather_query","duration_ms":1320,"status":"success"}

{"timestamp":"2025-10-28T10:30:01","level":"ERROR","message":"MCP call timed out","request_id":"f47ac10b-58cc-4372-a567-0e02b2c3d479","task":"mcp_client","duration_ms":30000,"status":"error"}
```

## Development

### Project Structure

```
weather-sense/
├── api/                    # FastAPI application
│   ├── main.py            # API endpoints and app setup
│   ├── security.py        # Authentication logic  
│   └── logging_config.py  # Structured logging setup
├── crew/                   # CrewAI workflow components
│   ├── flow.py            # Task orchestration (A→B→C)
│   ├── parser.py          # Task A: Natural language parsing
│   ├── mcp_client.py      # Task B: MCP tool client
│   └── agents.py          # Task C: Weather analysis
├── mcp_weather/           # MCP weather tool
│   ├── server.py          # Stdio-based JSON server
│   ├── provider.py        # Weather API integration
│   └── cache.py           # In-memory caching
├── tests/                 # Test suite
│   ├── test_parser.py     # Parser unit tests
│   ├── test_mcp_client.py # MCP client tests
│   └── test_api_e2e.py    # End-to-end API tests
├── Dockerfile             # Container configuration
├── pyproject.toml         # Python package configuration
└── README.md              # This file
```

### Adding Features

1. **New Query Patterns**: Extend `DateRangeParser` in `crew/parser.py`
2. **Weather Providers**: Implement new providers in `mcp_weather/provider.py`
3. **Analysis Features**: Enhance `WeatherAnalyst` in `crew/agents.py`
4. **API Endpoints**: Add routes in `api/main.py`

### Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## Troubleshooting

### Common Issues

**MCP Tool Not Found**:
```bash
# Check Python path and file permissions
python -m py_compile mcp_weather/server.py
chmod +x mcp_weather/server.py
```

**API Authentication Errors**:
```bash
# Verify API_KEY environment variable
echo $API_KEY
export API_KEY="your-secret-api-key"
```

**Weather API Failures**:
- Check internet connectivity
- Verify Open-Meteo API availability
- Check rate limiting

**Docker Issues**:
```bash
# Check container logs
docker logs <container-id>

# Debug container
docker run -it weather-sense /bin/bash
```

### Performance Tuning

- Increase cache TTL for slower changing data
- Add Redis for distributed caching
- Implement request queuing for high load
- Use async weather API calls

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Support

For issues and questions:
1. Check this README and NOTES.md
2. Review test cases for usage examples
3. Open an issue on GitHub
4. Contact the development team