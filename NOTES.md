# WeatherSense Development Notes

This document contains detailed technical notes, implementation decisions, and development guidelines for the WeatherSense project.

## Implementation Decisions

### Architecture Choices

**MCP Tool Design**:
- Chose stdio-based communication for simplicity and language independence
- JSON protocol for structured data exchange
- Subprocess isolation for fault tolerance
- 30-second timeout to prevent hanging processes

**CrewAI Task Flow**:
- Sequential A→B→C execution for deterministic behavior
- Error propagation between tasks
- Individual task timing for performance analysis
- Confidence scoring based on parsing success

**Caching Strategy**:
- In-memory cache for simplicity (no external dependencies)
- 10-minute TTL balances freshness vs. performance
- Cache key includes all parameters (lat, lon, dates, units)
- Thread-safe implementation for concurrent requests

**API Design**:
- RESTful endpoints following OpenAPI standards
- Structured error responses with consistent format
- Request ID tracking for debugging
- Comprehensive logging for production monitoring

### Natural Language Processing

**Date Parsing Strategy**:
The parser handles multiple date formats and relative expressions:

```python
# Relative dates
"last Monday" → Calculate based on current weekday
"this week" → Monday to Sunday of current week
"from yesterday to today" → Specific date range

# Absolute dates  
"October 15, 2025" → Parse with dateutil
"2025-10-15" → Direct ISO format
"10/15/2025" → US date format
```

**Location Extraction**:
```python
# Patterns used for location detection
location_patterns = [
    r'\bin\s+([A-Za-z\s,.-]+?)(?:\s+from|\s+between|\s*$)',
    r'weather\s+(?:in\s+)?([A-Za-z\s,.-]+?)(?:\s+from|\s+between)',
    r'([A-Za-z\s,.-]+?)(?:\s+weather|\s+from|\s+between)',
]
```

**Confidence Scoring**:
- Base confidence: 0.3 for successful parsing
- Location confidence: +0.3 for valid location
- Date range confidence: +0.3 for valid dates
- Units confidence: +0.1 if units specified
- Maximum confidence: 1.0

### Weather Data Integration

**Open-Meteo API Usage**:
```python
# Daily weather parameters requested
daily_params = [
    "temperature_2m_min",      # Minimum temperature
    "temperature_2m_max",      # Maximum temperature  
    "precipitation_sum",       # Total precipitation
    "wind_speed_10m_max",      # Maximum wind speed
    "weather_code"             # Weather condition code
]
```

**Weather Codes**:
The system uses WMO weather codes:
- 0: Clear sky
- 1-3: Partly cloudy to overcast
- 45-48: Fog
- 51-67: Rain (drizzle to heavy)
- 71-86: Snow
- 95-99: Thunderstorms

**Unit Conversions**:
- Temperature: Celsius ↔ Fahrenheit
- Wind speed: km/h ↔ mph (converted to km/h for consistency)
- Precipitation: Always in mm

### Error Handling Strategy

**Error Categories**:
1. **Client Errors (4xx)**:
   - `missing_location`: No location found in query
   - `invalid_date_range`: Unparseable dates
   - `range_too_large`: Span > 31 days
   - `invalid_date_order`: End before start

2. **Server Errors (5xx)**:
   - `mcp_timeout`: MCP tool exceeded timeout
   - `provider_unavailable`: Weather API down
   - `internal_error`: Unexpected exceptions

3. **Rate Limiting (429)**:
   - `rate_limited`: Too many requests

**Error Response Format**:
```json
{
  "error": "range_too_large",
  "hint": "Span must be <= 31 days"
}
```

### Performance Considerations

**Caching Effectiveness**:
- Cache hit rate depends on query patterns
- Geographic clustering improves hit rates
- Date range overlap reduces effectiveness
- Memory usage scales with unique location/date combinations

**Bottlenecks**:
1. **Network latency**: Weather API calls (100-500ms)
2. **Geocoding**: Location resolution (50-200ms)
3. **Subprocess overhead**: MCP tool startup (10-50ms)
4. **JSON parsing**: Minimal impact (<1ms)

**Optimization Opportunities**:
- Batch geocoding for multiple locations
- Persistent weather API connections
- Redis cache for horizontal scaling
- Async/await for concurrent operations

### Testing Strategy

**Unit Tests**:
- `test_parser.py`: NLP parsing logic
- `test_mcp_client.py`: Subprocess communication
- Mock external dependencies (weather APIs)

**Integration Tests**:
- `test_api_e2e.py`: Full API workflow
- Real subprocess calls with mocked data
- Error scenario testing

**Test Data**:
```python
# Fixed test date for consistency
self.parser.today = date(2025, 10, 28)  # Tuesday

# Mock weather responses
mock_weather_data = {
    "daily": [
        {
            "date": "2025-10-20",
            "tmin": 20.0, "tmax": 28.0,
            "precip_mm": 0.0, "wind_max_kph": 15.0,
            "code": 1
        }
    ],
    "source": "open-meteo"
}
```

### Security Considerations

**API Authentication**:
- API key via `x-api-key` header
- Environment variable configuration
- No key logging or exposure in responses

**Input Validation**:
- Query length limits (implicit via HTTP)
- Date range validation (≤ 31 days)
- SQL injection prevention (no database)
- Command injection prevention (subprocess args)

**Container Security**:
- Non-root user in Docker container
- Minimal base image (python:3.11-slim)
- No unnecessary packages or services
- Health check endpoint for monitoring

### Deployment Considerations

**Environment Variables**:
```bash
# Required
API_KEY="your-secret-key"

# Optional with defaults
LOG_LEVEL="INFO"
PORT="8000"
TZ="UTC"
WEATHER_PROVIDER="open-meteo"
```

**Resource Requirements**:
- Memory: 512MB minimum, 1GB recommended
- CPU: 1 vCPU sufficient for moderate load
- Storage: Minimal (stateless application)
- Network: Outbound HTTPS for weather APIs

**Scaling Considerations**:
- Stateless design enables horizontal scaling
- In-memory cache doesn't share between instances
- External cache (Redis) needed for multi-instance caching
- Load balancer can distribute requests evenly

### Monitoring and Observability

**Structured Logging Fields**:
```json
{
  "timestamp": "2025-10-28T10:30:00Z",
  "level": "INFO",
  "message": "Request completed",
  "request_id": "uuid-string",
  "task": "weather_query",
  "duration_ms": 1234,
  "status": "success"
}
```

**Metrics to Track**:
- Request rate and latency percentiles
- Error rates by error type
- Cache hit/miss ratios
- MCP tool success/failure rates
- Weather API response times

**Alerting Thresholds**:
- Error rate > 5%
- 95th percentile latency > 5 seconds
- Cache hit rate < 50%
- Weather API failures > 10%

### Future Enhancements

**Performance Improvements**:
- Async/await for concurrent operations
- Connection pooling for weather APIs
- Intelligent caching with geographic clustering
- Request queuing and rate limiting

**Feature Additions**:
- Multiple weather providers (OpenWeather, AccuWeather)
- Historical weather data analysis
- Weather forecasting beyond current data
- Batch query processing
- WebSocket streaming for real-time updates

**Analysis Enhancements**:
- Machine learning for better confidence scoring
- Seasonal pattern recognition
- Anomaly detection in weather patterns
- Comparative analysis between locations

### Known Limitations

**Date Parsing**:
- Ambiguous dates may be misinterpreted
- Limited support for non-English languages
- Complex relative dates ("third Tuesday of next month")

**Weather Data**:
- Dependent on Open-Meteo API availability
- Limited to daily granularity (no hourly data)
- No real-time weather alerts or warnings

**Scalability**:
- In-memory cache doesn't scale horizontally
- Subprocess overhead for each MCP call
- No connection pooling for external APIs

**Geographic Coverage**:
- Geocoding quality varies by region
- Some remote locations may not be found
- Coordinate precision limited to 2 decimal places

### Development Workflow

**Local Development**:
```bash
# Install dependencies
pip install -e ".[test]"

# Run in development mode
export API_KEY="dev-key"
python -m uvicorn api.main:app --reload

# Run tests
pytest -v --cov=.
```

**Code Quality**:
- Black for code formatting
- isort for import sorting
- pytest for testing
- Type hints encouraged but not enforced

**Git Workflow**:
- Feature branches for new development
- Pull requests for code review
- Automated testing on push
- Semantic versioning for releases

### Debugging Guide

**Common Issues**:

1. **MCP Tool Not Found**:
   ```bash
   # Check file permissions and Python path
   python -c "import sys; print(sys.executable)"
   ls -la mcp_weather/server.py
   ```

2. **API Authentication Failures**:
   ```bash
   # Verify environment variable
   echo $API_KEY
   # Check request headers
   curl -v -H "x-api-key: $API_KEY" ...
   ```

3. **Weather API Timeouts**:
   ```bash
   # Test direct API access
   curl "https://api.open-meteo.com/v1/forecast?latitude=32.08&longitude=34.78&daily=temperature_2m_max"
   ```

4. **Date Parsing Issues**:
   ```python
   # Test parser directly
   from crew.parser import DateRangeParser
   parser = DateRangeParser()
   result = parser.parse_query("your query here")
   print(result)
   ```

**Log Analysis**:
```bash
# Filter by request ID
grep "request_id:12345" app.log

# Find slow requests
jq 'select(.duration_ms > 5000)' app.log

# Error summary
jq 'select(.level == "ERROR") | .message' app.log | sort | uniq -c
```

This completes the comprehensive WeatherSense implementation with all required components, following the exact specifications provided.