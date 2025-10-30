"""
Security validation utilities for WeatherSense.
"""
import html
import logging
import re
import urllib.parse
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Security-focused input validation for weather queries."""

    def __init__(self):
        # Suspicious patterns that could indicate XSS or injection attempts
        self.suspicious_patterns = [
            r"<script[^>]*>",
            r"javascript:",
            r"vbscript:",
            r"on\w+\s*=",  # event handlers like onclick=
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<applet[^>]*>",
            r"eval\s*\(",
            r"alert\s*\(",
            r"confirm\s*\(",
            r"prompt\s*\(",
            r"document\.",
            r"window\.",
            r"location\.",
            r"navigator\.",
            r"console\.",
        ]

        # SQL injection patterns
        self.sql_patterns = [
            r"\b(?:union|select|insert|update|delete|drop|create|alter)\b",
            r'[\'";]',  # quotes that could close SQL strings
            r"--",  # SQL comments
            r"/\*.*?\*/",  # SQL block comments
        ]

        # Reasonable limits for input validation
        self.max_query_length = 500
        self.max_location_length = 100

        # Valid coordinate ranges
        self.lat_range = (-90.0, 90.0)
        self.lon_range = (-180.0, 180.0)

    def validate_query(self, query: str) -> Dict[str, any]:
        """
        Comprehensive security validation for weather queries.

        Returns:
            dict: {
                'valid': bool,
                'sanitized_query': str,
                'errors': List[str],
                'warnings': List[str]
            }
        """
        if not query or not isinstance(query, str):
            return {
                "valid": False,
                "sanitized_query": "",
                "errors": ["Query is required and must be a string"],
                "warnings": [],
            }

        errors = []
        warnings = []

        # Length validation
        if len(query) > self.max_query_length:
            errors.append(f"Query too long (max {self.max_query_length} characters)")

        # Check for suspicious patterns
        query_lower = query.lower()
        for pattern in self.suspicious_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                errors.append(f"Suspicious content detected: {pattern}")

        # Check for SQL injection patterns
        for pattern in self.sql_patterns:
            if re.search(pattern, query_lower, re.IGNORECASE):
                warnings.append(f"Potentially unsafe SQL pattern: {pattern}")

        # Basic XSS prevention
        if "<" in query or ">" in query:
            if not self._is_safe_html_content(query):
                errors.append("HTML/XML content not allowed")

        # URL encoding check
        if "%" in query and not self._is_safe_url_encoded(query):
            warnings.append("URL encoded content detected")

        # Sanitize the query
        sanitized = self._sanitize_query(query)

        return {
            "valid": len(errors) == 0,
            "sanitized_query": sanitized,
            "errors": errors,
            "warnings": warnings,
        }

    def validate_location(self, location: str) -> Dict[str, any]:
        """
        Validate and sanitize location input.

        Returns:
            dict: {
                'valid': bool,
                'sanitized_location': str,
                'location_type': str,  # 'coordinates', 'city_name', 'unknown'
                'errors': List[str]
            }
        """
        if not location or not isinstance(location, str):
            return {
                "valid": False,
                "sanitized_location": "",
                "location_type": "unknown",
                "errors": ["Location is required and must be a string"],
            }

        errors = []
        location = location.strip()

        # Length validation
        if len(location) > self.max_location_length:
            errors.append(
                f"Location name too long (max {self.max_location_length} characters)"
            )

        # Check if it's coordinates
        if self._is_coordinates(location):
            lat, lon, coord_errors = self._validate_coordinates(location)
            if coord_errors:
                errors.extend(coord_errors)
                return {
                    "valid": False,
                    "sanitized_location": location,
                    "location_type": "coordinates",
                    "errors": errors,
                }
            else:
                return {
                    "valid": True,
                    "sanitized_location": f"{lat},{lon}",
                    "location_type": "coordinates",
                    "errors": [],
                }

        # Validate city name
        city_errors = self._validate_city_name(location)
        if city_errors:
            errors.extend(city_errors)

        # Sanitize location
        sanitized = self._sanitize_location(location)

        return {
            "valid": len(errors) == 0,
            "sanitized_location": sanitized,
            "location_type": "city_name",
            "errors": errors,
        }

    def _is_coordinates(self, location: str) -> bool:
        """Check if location string looks like coordinates."""
        coord_pattern = r"^-?\d+\.?\d*\s*,\s*-?\d+\.?\d*$"
        return bool(re.match(coord_pattern, location.strip()))

    def _validate_coordinates(
        self, location: str
    ) -> Tuple[Optional[float], Optional[float], List[str]]:
        """Validate coordinate values."""
        errors = []

        try:
            parts = location.split(",")
            if len(parts) != 2:
                errors.append("Coordinates must be in format: latitude,longitude")
                return None, None, errors

            lat = float(parts[0].strip())
            lon = float(parts[1].strip())

            # Validate latitude range
            if not (self.lat_range[0] <= lat <= self.lat_range[1]):
                errors.append(
                    f"Latitude must be between "
                    f"{self.lat_range[0]} and {self.lat_range[1]}"
                )

            # Validate longitude range
            if not (self.lon_range[0] <= lon <= self.lon_range[1]):
                errors.append(
                    f"Longitude must be between "
                    f"{self.lon_range[0]} and {self.lon_range[1]}"
                )

            return lat, lon, errors

        except ValueError:
            errors.append("Invalid coordinate format - must be numeric values")
            return None, None, errors

    def _validate_city_name(self, location: str) -> List[str]:
        """Validate city name format."""
        errors = []

        # Check for valid characters (letters, spaces, common punctuation)
        valid_chars_pattern = r"^[a-zA-Z\s\-\',\.]+$"
        if not re.match(valid_chars_pattern, location):
            errors.append("Location name contains invalid characters")

        # Check for minimum length
        if len(location.strip()) < 2:
            errors.append("Location name too short (minimum 2 characters)")

        # Check for suspicious patterns
        if any(char in location for char in "<>[]{}()"):
            errors.append("Location name contains suspicious characters")

        # Check for numbers (unusual in city names)
        if re.search(r"\d{3,}", location):  # 3+ consecutive digits
            errors.append("Location name contains suspicious numeric patterns")

        return errors

    def _sanitize_query(self, query: str) -> str:
        """Sanitize query string."""
        # HTML escape
        sanitized = html.escape(query)

        # Normalize whitespace
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        # Remove any remaining suspicious characters
        sanitized = re.sub(r"[<>{}[\]()]", "", sanitized)

        return sanitized

    def _sanitize_location(self, location: str) -> str:
        """Sanitize location string."""
        # Remove leading/trailing whitespace
        sanitized = location.strip()

        # Normalize internal whitespace
        sanitized = re.sub(r"\s+", " ", sanitized)

        # Remove suspicious characters
        sanitized = re.sub(r"[<>{}[\]()]", "", sanitized)

        # Capitalize first letter of each word (common for city names)
        sanitized = " ".join(word.capitalize() for word in sanitized.split())

        return sanitized

    def _is_safe_html_content(self, content: str) -> bool:
        """Check if HTML-like content is safe."""
        # Very basic check - in production, use a proper HTML sanitizer
        dangerous_tags = [
            "script",
            "iframe",
            "object",
            "embed",
            "applet",
            "link",
            "meta",
        ]
        content_lower = content.lower()

        for tag in dangerous_tags:
            if f"<{tag}" in content_lower:
                return False

        return True

    def _is_safe_url_encoded(self, content: str) -> bool:
        """Check if URL encoded content is safe."""
        try:
            decoded = urllib.parse.unquote(content)
            # Check if the decoded content would be safe
            validation = self.validate_query(decoded)
            return validation["valid"]
        except Exception:
            return False


# Global validator instance
security_validator = SecurityValidator()


def validate_weather_query(query: str) -> Dict[str, any]:
    """Convenience function for validating weather queries."""
    return security_validator.validate_query(query)


def validate_location_input(location: str) -> Dict[str, any]:
    """Convenience function for validating location inputs."""
    return security_validator.validate_location(location)
