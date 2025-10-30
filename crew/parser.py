"""
CrewAI Task A - Natural language date range parser.
"""
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from dateutil.parser import parse as dateutil_parse
from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)


class DateRangeParser:
    def __init__(self):
        self.today = date.today()
        self.weekday_names = {
            "monday": 0,
            "tuesday": 1,
            "wednesday": 2,
            "thursday": 3,
            "friday": 4,
            "saturday": 5,
            "sunday": 6,
        }

    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parse natural language query to extract location, dates, and units.
        """
        try:
            query_lower = query.lower().strip()

            # Extract units
            units = self._extract_units(query_lower)

            # Extract location
            location = self._extract_location(query)
            if not location:
                return {
                    "error": "missing_location",
                    "hint": "Please specify a location (city name or coordinates)",
                }

            # Extract date range
            start_date, end_date = self._extract_date_range(query_lower)
            if not start_date or not end_date:
                return {
                    "error": "invalid_date_range",
                    "hint": "Could not parse date range from query",
                }

            # Validate date range
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

            if end_dt < start_dt:
                return {
                    "error": "invalid_date_order",
                    "hint": "End date must be after start date",
                }

            span_days = (end_dt - start_dt).days + 1
            if span_days > 31:
                return {
                    "error": "range_too_large",
                    "hint": "Date range must be <= 31 days",
                }

            # Calculate confidence based on parsing success
            confidence = self._calculate_confidence(
                query_lower, location, start_date, end_date, units
            )

            return {
                "location": location,
                "start_date": start_date,
                "end_date": end_date,
                "units": units,
                "confidence": confidence,
            }

        except Exception as e:
            logger.error(f"Parser error: {e}")
            return {
                "error": "parsing_failed",
                "hint": f"Failed to parse query: {str(e)}",
            }

    def _extract_units(self, query: str) -> str:
        """Extract units from query, default to metric."""
        if any(word in query for word in ["imperial", "fahrenheit", "mph"]):
            return "imperial"
        return "metric"

    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query."""
        # Look for common location patterns - more specific patterns first
        location_patterns = [
            # Pattern: "in/for <location> for/from/during/this/next/last"
            r"\b(?:in|for)\s+([A-Za-z\s,.-]+?)(?:\s+(?:for|from|during|this|next|last|tomorrow|today|yesterday|\d))",
            # Pattern: "weather in/for <location>"
            r"weather\s+(?:in|for)\s+([A-Za-z\s,.-]+?)(?:\s+(?:for|from|during|this|next|last|tomorrow|today|yesterday|\d)|\s*$)",
            # Pattern: "forecast/temperature/climate data for <location>"
            r"\b(?:forecast|temperature|climate)\s+(?:data\s+)?for\s+([A-Za-z\s,.-]+?)(?:\s+(?:from|during|this|next|last|tomorrow|today|yesterday|\d))",
            # Pattern: "forecast <location>" but not time words
            r"\bforecast\s+([A-Za-z][A-Za-z\s,.-]*?)(?:\s+(?:from|during|this|next|last|tomorrow|today|yesterday|\d)|\s*$)",
            # Pattern: "<location> weather"
            r"([A-Za-z\s,.-]+?)\s+weather",
            # Pattern: "in/for <location>" at end of query
            r"\b(?:in|for)\s+([A-Za-z\s,.-]+?)\s*$",
        ]

        # Check for coordinate pattern first
        coord_pattern = r"(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)"
        coord_match = re.search(coord_pattern, query)
        if coord_match:
            return f"{coord_match.group(1)},{coord_match.group(2)}"

        for pattern in location_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                location = match.group(1).strip()
                # Clean up the location
                location = re.sub(r"\s+", " ", location)
                location = location.strip(" ,.-")

                # Filter out time-related words that are not locations
                time_words = [
                    "last week",
                    "this week",
                    "next week",
                    "last monday",
                    "this monday",
                    "next monday",
                    "yesterday",
                    "today",
                    "tomorrow",
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                    "from",
                    "to",
                    "during",
                    "this",
                    "next",
                    "last",
                    "week",
                    "day",
                    "month",
                    "year",
                ]

                if location.lower() not in time_words and len(location) > 2:
                    return location

        return None

    def _extract_date_range(self, query: str) -> tuple[Optional[str], Optional[str]]:
        """Extract start and end dates from query."""
        try:
            # Handle simple single-day queries first
            if "today" in query and not (
                " from " in query or " to " in query or "between" in query
            ):
                today_date = self.today.strftime("%Y-%m-%d")
                return today_date, today_date

            if "tomorrow" in query and not (
                " from " in query or " to " in query or "between" in query
            ):
                tomorrow_date = (self.today + timedelta(days=1)).strftime("%Y-%m-%d")
                return tomorrow_date, tomorrow_date

            if "yesterday" in query and not (
                " from " in query or " to " in query or "between" in query
            ):
                yesterday_date = (self.today - timedelta(days=1)).strftime("%Y-%m-%d")
                return yesterday_date, yesterday_date

            # Handle relative date patterns
            if "last week" in query:
                return self._get_last_week()
            elif "this week" in query:
                return self._get_this_week()
            elif "next week" in query:
                return self._get_next_week()
            elif (
                "last monday to friday" in query
                or "from last monday to friday" in query
            ):
                return self._get_last_weekdays()
            elif (
                "this monday to friday" in query
                or "from this monday to friday" in query
            ):
                return self._get_this_weekdays()

            # Handle individual weekdays (e.g., "next Sunday", "last Monday")
            for weekday, weekday_num in self.weekday_names.items():
                pattern = rf"\b(?:last|this|next)\s+{weekday}\b"
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    date_str = self._get_weekday_date(
                        weekday_num, match.group(0).lower()
                    )
                    return date_str, date_str

            # Handle "next X days" pattern
            next_days_match = re.search(r"next\s+(\d+)\s+days?", query)
            if next_days_match:
                num_days = int(next_days_match.group(1))
                start_date = (self.today + timedelta(days=1)).strftime(
                    "%Y-%m-%d"
                )  # Tomorrow
                end_date = (self.today + timedelta(days=num_days)).strftime("%Y-%m-%d")
                return start_date, end_date

            # Handle specific date ranges
            date_range_patterns = [
                r"from\s+(.+?)\s+to\s+(.+?)(?:\s|$)",
                r"between\s+(.+?)\s+and\s+(.+?)(?:\s|$)",
                r"(.+?)\s+to\s+(.+?)(?:\s|$)",
                r"(.+?)\s+through\s+(.+?)(?:\s|$)",
            ]

            for pattern in date_range_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    start_str = match.group(1).strip()
                    end_str = match.group(2).strip()

                    start_date = self._parse_single_date(start_str)
                    end_date = self._parse_single_date(end_str)

                    if start_date and end_date:
                        return start_date, end_date

            # Try to find individual dates
            dates = self._extract_individual_dates(query)
            if len(dates) >= 2:
                return min(dates), max(dates)
            elif len(dates) == 1:
                # Single date - make it a one-day range
                return dates[0], dates[0]

        except Exception as e:
            logger.error(f"Date extraction error: {e}")

        return None, None

    def _parse_single_date(self, date_str: str) -> Optional[str]:
        """Parse a single date string."""
        try:
            # Clean up the date string
            date_str = re.sub(r"[,.]", "", date_str.strip())

            # Handle relative dates
            if "today" in date_str.lower():
                return self.today.strftime("%Y-%m-%d")
            elif "yesterday" in date_str.lower():
                return (self.today - timedelta(days=1)).strftime("%Y-%m-%d")
            elif "tomorrow" in date_str.lower():
                return (self.today + timedelta(days=1)).strftime("%Y-%m-%d")

            # Handle weekday names
            for weekday, weekday_num in self.weekday_names.items():
                if weekday in date_str.lower():
                    return self._get_weekday_date(weekday_num, date_str.lower())

            # Try parsing with dateutil
            parsed_date = dateutil_parse(date_str, default=datetime.now())
            return parsed_date.date().strftime("%Y-%m-%d")

        except Exception:
            return None

    def _get_weekday_date(self, target_weekday: int, date_str: str) -> str:
        """Get date for specific weekday (handles 'last', 'this', 'next')."""
        current_weekday = self.today.weekday()

        if "last" in date_str:
            # Last occurrence of the weekday
            days_back = (current_weekday - target_weekday) % 7
            if days_back == 0:
                days_back = 7  # Go to previous week
            target_date = self.today - timedelta(days=days_back)
        elif "next" in date_str:
            # Next occurrence of the weekday
            days_forward = (target_weekday - current_weekday) % 7
            if days_forward == 0:
                days_forward = 7  # Go to next week
            target_date = self.today + timedelta(days=days_forward)
        else:
            # This week's occurrence
            days_diff = target_weekday - current_weekday
            target_date = self.today + timedelta(days=days_diff)

        return target_date.strftime("%Y-%m-%d")

    def _get_last_week(self) -> tuple[str, str]:
        """Get last week's date range (Monday to Sunday)."""
        days_since_monday = (self.today.weekday()) % 7
        last_monday = self.today - timedelta(days=days_since_monday + 7)
        last_sunday = last_monday + timedelta(days=6)
        return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")

    def _get_this_week(self) -> tuple[str, str]:
        """Get this week's date range (Monday to Sunday)."""
        days_since_monday = self.today.weekday()
        this_monday = self.today - timedelta(days=days_since_monday)
        this_sunday = this_monday + timedelta(days=6)
        return this_monday.strftime("%Y-%m-%d"), this_sunday.strftime("%Y-%m-%d")

    def _get_next_week(self) -> tuple[str, str]:
        """Get next week's date range (Monday to Sunday)."""
        days_since_monday = self.today.weekday()
        next_monday = self.today + timedelta(days=7 - days_since_monday)
        next_sunday = next_monday + timedelta(days=6)
        return next_monday.strftime("%Y-%m-%d"), next_sunday.strftime("%Y-%m-%d")

    def _get_last_weekdays(self) -> tuple[str, str]:
        """Get last Monday to Friday."""
        days_since_monday = self.today.weekday()
        last_monday = self.today - timedelta(days=days_since_monday + 7)
        last_friday = last_monday + timedelta(days=4)
        return last_monday.strftime("%Y-%m-%d"), last_friday.strftime("%Y-%m-%d")

    def _get_this_weekdays(self) -> tuple[str, str]:
        """Get this Monday to Friday."""
        days_since_monday = self.today.weekday()
        this_monday = self.today - timedelta(days=days_since_monday)
        this_friday = this_monday + timedelta(days=4)
        return this_monday.strftime("%Y-%m-%d"), this_friday.strftime("%Y-%m-%d")

    def _extract_individual_dates(self, query: str) -> list[str]:
        """Extract individual dates from query."""
        dates = []

        # Date patterns
        date_patterns = [
            r"\b(\d{4}-\d{2}-\d{2})\b",  # YYYY-MM-DD
            r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b",  # MM/DD/YYYY or MM-DD-YYYY
            r"\b(\w+\s+\d{1,2},?\s+\d{4})\b",  # Month DD, YYYY
        ]

        for pattern in date_patterns:
            matches = re.finditer(pattern, query)
            for match in matches:
                try:
                    parsed_date = dateutil_parse(match.group(1))
                    dates.append(parsed_date.date().strftime("%Y-%m-%d"))
                except Exception:
                    continue

        return dates

    def _calculate_confidence(
        self, query: str, location: str, start_date: str, end_date: str, units: str
    ) -> float:
        """Calculate confidence score based on parsing success and query clarity."""
        confidence = 0.0

        # Location confidence (40% of total)
        if location:
            location_confidence = 0.0
            if len(location) > 2:
                location_confidence += 0.2
            # Bonus for recognized city names (basic check)
            if any(char.isupper() for char in location):  # Likely proper noun
                location_confidence += 0.1
            # Penalty for vague locations
            if any(
                word in location.lower()
                for word in ["somewhere", "anywhere", "unknown"]
            ):
                location_confidence -= 0.2
            confidence += min(location_confidence, 0.4)

        # Date range confidence (40% of total)
        if start_date and end_date:
            date_confidence = 0.2  # Base for successful parsing

            # Bonus for specific date formats
            if re.match(r"\d{4}-\d{2}-\d{2}", start_date):
                date_confidence += 0.1

            # Penalty for very vague date references
            vague_date_words = ["sometime", "maybe", "perhaps", "possibly"]
            if any(word in query for word in vague_date_words):
                date_confidence -= 0.15

            # Bonus for clear temporal indicators
            clear_indicators = [
                "today",
                "tomorrow",
                "yesterday",
                "last week",
                "next week",
                "this week",
            ]
            if any(indicator in query for indicator in clear_indicators):
                date_confidence += 0.1

            confidence += min(date_confidence, 0.4)

        # Units confidence (10% of total)
        units_confidence = 0.05  # Base for default units
        if (
            "metric" in query
            or "imperial" in query
            or "fahrenheit" in query
            or "celsius" in query
        ):
            units_confidence = 0.1  # Explicitly mentioned
        confidence += units_confidence

        # Query clarity bonus/penalty (10% of total)
        clarity_score = 0.0

        # Penalty for ambiguous words
        ambiguous_words = ["maybe", "perhaps", "might", "possibly", "unclear", "vague"]
        ambiguous_count = sum(1 for word in ambiguous_words if word in query)
        clarity_score -= ambiguous_count * 0.03

        # Bonus for clear structure
        if any(pattern in query for pattern in ["from", "to", "between", "in"]):
            clarity_score += 0.05

        # Penalty for overly complex queries
        if len(query.split()) > 15:
            clarity_score -= 0.02

        confidence += clarity_score

        # Ensure confidence is in valid range [0.0, 1.0]
        return max(0.0, min(confidence, 1.0))


def parse_natural_language(query_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    CrewAI Task A - Parse natural language query.
    """
    query = query_data.get("query", "")
    if not query:
        return {"error": "missing_query", "hint": "Query parameter is required"}

    parser = DateRangeParser()
    return parser.parse_query(query)
