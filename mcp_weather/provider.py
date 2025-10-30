"""
Weather data provider using Open-Meteo API.
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)


class WeatherProvider:
    def __init__(self):
        self.geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
        self.weather_url = "https://api.open-meteo.com/v1/forecast"

    def geocode_location(self, location: str) -> Tuple[float, float, str]:
        """
        Geocode location name to lat/lon coordinates.
        Returns (lat, lon, formatted_name).
        """
        if self._is_coordinates(location):
            lat, lon = map(float, location.split(","))
            return lat, lon, f"{lat:.2f},{lon:.2f}"

        try:
            params = {"name": location, "count": 1, "language": "en", "format": "json"}

            response = requests.get(self.geocoding_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()
            if not data.get("results"):
                raise ValueError(f"Location '{location}' not found")

            result = data["results"][0]
            lat = result["latitude"]
            lon = result["longitude"]

            # Format location name
            name_parts = [result["name"]]
            if result.get("country"):
                name_parts.append(result["country"])
            formatted_name = ", ".join(name_parts)

            return lat, lon, formatted_name

        except requests.RequestException as e:
            logger.error(f"Geocoding API error: {e}")
            raise ValueError(f"Failed to geocode location: {e}")

    def _is_coordinates(self, location: str) -> bool:
        """Check if location string is in lat,lon format."""
        try:
            parts = location.split(",")
            if len(parts) == 2:
                float(parts[0])
                float(parts[1])
                return True
        except ValueError:
            pass
        return False

    def fetch_weather_data(
        self, lat: float, lon: float, start_date: str, end_date: str, units: str
    ) -> Dict[str, Any]:
        """
        Fetch weather data from Open-Meteo API.
        """
        try:
            # Convert units
            temperature_unit = "celsius" if units == "metric" else "fahrenheit"
            wind_speed_unit = "kmh" if units == "metric" else "mph"
            precipitation_unit = "mm"

            params = {
                "latitude": lat,
                "longitude": lon,
                "start_date": start_date,
                "end_date": end_date,
                "daily": [
                    "temperature_2m_min",
                    "temperature_2m_max",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                    "weather_code",
                ],
                "temperature_unit": temperature_unit,
                "wind_speed_unit": wind_speed_unit,
                "precipitation_unit": precipitation_unit,
                "timezone": "UTC",
            }

            response = requests.get(self.weather_url, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()

            # Transform to required format
            daily_data = []
            daily = data.get("daily", {})
            dates = daily.get("time", [])

            for i, date in enumerate(dates):
                daily_entry = {
                    "date": date,
                    "tmin": self._safe_get(daily.get("temperature_2m_min"), i),
                    "tmax": self._safe_get(daily.get("temperature_2m_max"), i),
                    "precip_mm": self._safe_get(daily.get("precipitation_sum"), i, 0.0),
                    "wind_max_kph": self._convert_wind_speed(
                        self._safe_get(daily.get("wind_speed_10m_max"), i), units
                    ),
                    "code": self._safe_get(daily.get("weather_code"), i, 0),
                }
                daily_data.append(daily_entry)

            return {"daily": daily_data, "source": "open-meteo"}

        except requests.RequestException as e:
            logger.error(f"Weather API error: {e}")
            raise ValueError(f"Failed to fetch weather data: {e}")

    def _safe_get(
        self, data_list: Optional[List], index: int, default: Any = None
    ) -> Any:
        """Safely get item from list at index."""
        if data_list and 0 <= index < len(data_list):
            value = data_list[index]
            return value if value is not None else default
        return default

    def _convert_wind_speed(self, speed: Optional[float], units: str) -> float:
        """Convert wind speed to km/h for consistent output."""
        if speed is None:
            return 0.0

        if units == "imperial":
            # Convert mph to km/h
            return speed * 1.60934

        return speed  # Already in km/h for metric
