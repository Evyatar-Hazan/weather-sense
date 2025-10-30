# WeatherSense Changelog

All notable changes to the WeatherSense project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.0] - 2025-10-31

### Added
- **Comprehensive Security Framework**
  - New `utils/security.py` module with `SecurityValidator` class
  - XSS attack prevention with pattern detection and sanitization
  - SQL injection protection with parameterized query enforcement
  - Coordinate validation with geographic boundary checking (-90≤lat≤90, -180≤lon≤180)
  - Input length validation (1000 chars max for queries, 200 for locations)
  - Special character sanitization while preserving valid international names

- **Custom Rate Limiting System**
  - 30 requests per minute per IP address
  - Proxy header support for Google Cloud Run deployment (X-Forwarded-For, X-Real-IP)
  - Automatic cleanup of expired request records
  - HTTP 429 responses for rate limit violations
  - Fallback to direct client IP for local development

- **Enhanced Parser Architecture**
  - Modular component design replacing monolithic 455-line parser
  - `LocationExtractor` - Advanced location parsing with security validation
  - `DateRangeExtractor` - Natural language date/time processing
  - `InputValidator` - Comprehensive input sanitization and validation
  - `DateRangeParser` - Central orchestrator with improved error handling

- **Security Testing Suite**
  - New `tests/test_security_validation.py` with 7 comprehensive tests
  - XSS prevention validation
  - SQL injection protection testing
  - Coordinate boundary validation
  - Long input handling (10,000+ characters)
  - Special character processing
  - Empty/whitespace input validation
  - Normal query functionality preservation

### Changed
- **Improved Pattern Recognition**
  - Enhanced location extraction patterns to support "at" keyword for coordinates
  - Better handling of coordinate patterns in natural language queries
  - Improved fallback mechanisms for invalid input detection

- **Enhanced Error Handling**
  - More descriptive error messages for invalid inputs
  - Graceful degradation when security modules are unavailable
  - Better validation feedback for malformed coordinates

- **Documentation Updates**
  - Comprehensive security section added to README.md
  - Detailed implementation notes in NOTES.md
  - Security best practices documentation
  - Rate limiting configuration examples

### Security
- **Input Validation Hardening**
  - All user inputs now validated before processing
  - Automatic sanitization of potentially dangerous content
  - Protection against script injection and SQL injection attacks
  - Safe handling of international characters and special symbols

### Fixed
- **Import Compatibility**
  - Added fallback mechanisms for environments without security modules
  - Graceful handling of missing dependencies
  - Backward compatibility preserved for existing integrations

### Performance
- **Optimized Rate Limiting**
  - Native Python collections used instead of external dependencies
  - Efficient timestamp-based request tracking
  - Automatic cleanup reduces memory usage over time

## [2.0.0] - Previous Release

### Added
- Initial security framework implementation
- Basic rate limiting functionality
- Comprehensive testing suite

### Changed
- Parser architecture refactoring
- Improved error handling
- Enhanced documentation

## [1.0.0] - Initial Release

### Added
- FastAPI-based weather query API
- CrewAI workflow orchestration
- MCP (Model Context Protocol) tool integration
- Open-Meteo weather data provider
- Natural language query parsing
- Comprehensive test suite
- Docker containerization
- Google Cloud Run deployment
- Cloudflare Worker proxy for health checks

---

## Security Notices

### [2.1.0] Security Enhancements
- **IMPORTANT**: This release includes significant security improvements. All production deployments should be updated to this version.
- **Rate Limiting**: New rate limiting protects against abuse (30 req/min per IP)
- **Input Validation**: Comprehensive input validation prevents injection attacks
- **Coordinate Safety**: Geographic coordinate validation prevents invalid location requests

### Compatibility Notes
- All API endpoints maintain backward compatibility
- Existing client integrations will continue to work without changes
- No breaking changes to request/response formats
- Security validation is transparent to normal usage

### Testing Status
- **Total Tests**: 299
- **Passing**: 290 (97% success rate)
- **Skipped**: 9 (deployment-specific)
- **Security Tests**: 7 (100% passing)

### Known Issues
- None reported for current release

---

*For detailed technical documentation, see [NOTES.md](./NOTES.md)*
*For installation and usage instructions, see [README.md](./README.md)*
