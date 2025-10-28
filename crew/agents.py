"""
CrewAI Task C - Weather data analysis and summary generation.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime


logger = logging.getLogger(__name__)


class WeatherAnalyst:
    def __init__(self):
        self.weather_code_descriptions = {
            0: "clear sky",
            1: "mainly clear",
            2: "partly cloudy",
            3: "overcast",
            45: "fog",
            48: "depositing rime fog",
            51: "light drizzle",
            53: "moderate drizzle",
            55: "dense drizzle",
            56: "light freezing drizzle",
            57: "dense freezing drizzle",
            61: "slight rain",
            63: "moderate rain",
            65: "heavy rain",
            66: "light freezing rain",
            67: "heavy freezing rain",
            71: "slight snow fall",
            73: "moderate snow fall",
            75: "heavy snow fall",
            77: "snow grains",
            80: "slight rain showers",
            81: "moderate rain showers",
            82: "violent rain showers",
            85: "slight snow showers",
            86: "heavy snow showers",
            95: "thunderstorm",
            96: "thunderstorm with slight hail",
            99: "thunderstorm with heavy hail"
        }
    
    def analyze_weather_data(self, weather_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze weather data and generate summary.
        """
        try:
            # Check if previous tasks failed
            if "error" in weather_data:
                return weather_data
            
            params = weather_data.get("params", {})
            weather_raw = weather_data.get("weather_raw", {})
            daily_data = weather_raw.get("daily", [])
            
            if not daily_data:
                return {
                    "error": "no_weather_data",
                    "hint": "No weather data available for analysis"
                }
            
            # Analyze the weather patterns
            analysis = self._analyze_patterns(daily_data, params.get("units", "metric"))
            
            # Generate summary text
            summary_text = self._generate_summary(analysis, params)
            
            # Calculate confidence
            confidence = self._calculate_confidence(analysis, len(daily_data))
            
            return {
                "summary_text": summary_text,
                "highlights": {
                    "pattern": analysis["pattern"],
                    "extremes": analysis["extremes"],
                    "notable_days": analysis["notable_days"]
                },
                "confidence": confidence
            }
            
        except Exception as e:
            logger.error(f"Weather analysis error: {e}")
            return {
                "error": "analysis_failed",
                "hint": f"Failed to analyze weather data: {str(e)}"
            }
    
    def _analyze_patterns(self, daily_data: List[Dict], units: str) -> Dict[str, Any]:
        """Analyze weather patterns from daily data."""
        if not daily_data:
            return {}
        
        # Temperature analysis
        temps_min = [day.get("tmin", 0) for day in daily_data if day.get("tmin") is not None]
        temps_max = [day.get("tmax", 0) for day in daily_data if day.get("tmax") is not None]
        
        avg_tmin = sum(temps_min) / len(temps_min) if temps_min else 0
        avg_tmax = sum(temps_max) / len(temps_max) if temps_max else 0
        
        # Precipitation analysis
        precip_values = [day.get("precip_mm", 0) for day in daily_data]
        total_precip = sum(precip_values)
        rainy_days = len([p for p in precip_values if p >= 1.0])
        
        # Wind analysis
        wind_values = [day.get("wind_max_kph", 0) for day in daily_data]
        avg_wind = sum(wind_values) / len(wind_values) if wind_values else 0
        
        # Determine patterns
        temp_pattern = self._classify_temperature(avg_tmin, avg_tmax, units)
        precip_pattern = self._classify_precipitation(total_precip, rainy_days, len(daily_data))
        wind_pattern = self._classify_wind(avg_wind)
        
        # Find extremes
        extremes = self._find_extremes(daily_data)
        
        # Find notable days
        notable_days = self._find_notable_days(daily_data)
        
        return {
            "pattern": f"{temp_pattern}, {precip_pattern}, {wind_pattern}",
            "extremes": extremes,
            "notable_days": notable_days,
            "avg_tmin": avg_tmin,
            "avg_tmax": avg_tmax,
            "total_precip": total_precip,
            "avg_wind": avg_wind
        }
    
    def _classify_temperature(self, avg_tmin: float, avg_tmax: float, units: str) -> str:
        """Classify temperature pattern."""
        avg_temp = (avg_tmin + avg_tmax) / 2
        
        if units == "imperial":
            # Fahrenheit thresholds
            if avg_temp >= 80:
                return "hot"
            elif avg_temp >= 65:
                return "warm"
            elif avg_temp >= 50:
                return "cool"
            else:
                return "cold"
        else:
            # Celsius thresholds
            if avg_temp >= 27:
                return "hot"
            elif avg_temp >= 18:
                return "warm"
            elif avg_temp >= 10:
                return "cool"
            else:
                return "cold"
    
    def _classify_precipitation(self, total_precip: float, rainy_days: int, total_days: int) -> str:
        """Classify precipitation pattern."""
        if total_precip >= 25:
            return "wet"
        elif rainy_days >= total_days * 0.5:
            return "wet"
        elif total_precip >= 5:
            return "slightly wet"
        else:
            return "dry"
    
    def _classify_wind(self, avg_wind: float) -> str:
        """Classify wind pattern."""
        if avg_wind >= 40:
            return "windy"
        elif avg_wind >= 20:
            return "breezy"
        else:
            return "calm"
    
    def _find_extremes(self, daily_data: List[Dict]) -> Dict[str, Any]:
        """Find temperature extremes."""
        if not daily_data:
            return {"coldest": None, "hottest": None}
        
        # Find coldest day (by minimum temperature)
        coldest_day = min(daily_data, key=lambda x: x.get("tmin", float('inf')))
        
        # Find hottest day (by maximum temperature)
        hottest_day = max(daily_data, key=lambda x: x.get("tmax", float('-inf')))
        
        return {
            "coldest": {
                "date": coldest_day.get("date"),
                "tmin": coldest_day.get("tmin")
            },
            "hottest": {
                "date": hottest_day.get("date"),
                "tmax": hottest_day.get("tmax")
            }
        }
    
    def _find_notable_days(self, daily_data: List[Dict]) -> List[Dict[str, str]]:
        """Find notable weather days."""
        notable = []
        
        for day in daily_data:
            notes = []
            
            # Heavy rain (≥ 5mm)
            if day.get("precip_mm", 0) >= 5:
                notes.append("heavy rain")
            
            # Strong winds (≥ 40 km/h)
            if day.get("wind_max_kph", 0) >= 40:
                notes.append("strong winds")
            
            # Extreme weather codes
            weather_code = day.get("code", 0)
            if weather_code in [95, 96, 99]:
                notes.append("thunderstorm")
            elif weather_code in [65, 67, 82]:
                notes.append("heavy precipitation")
            elif weather_code in [73, 75, 86]:
                notes.append("heavy snow")
            
            if notes:
                notable.append({
                    "date": day.get("date"),
                    "note": ", ".join(notes)
                })
        
        return notable
    
    def _generate_summary(self, analysis: Dict[str, Any], params: Dict[str, Any]) -> str:
        """Generate weather summary text."""
        location = params.get("location", "the location")
        start_date = params.get("start_date", "")
        end_date = params.get("end_date", "")
        units = params.get("units", "metric")
        
        # Format date range
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y-%m-%d")
            
            if start_date == end_date:
                date_range = f"on {start_dt.strftime('%B %d, %Y')}"
            else:
                date_range = f"from {start_dt.strftime('%B %d')} to {end_dt.strftime('%B %d, %Y')}"
        except:
            date_range = f"from {start_date} to {end_date}"
        
        # Start summary
        pattern_parts = analysis.get("pattern", "").split(", ")
        temp_desc = pattern_parts[0] if len(pattern_parts) > 0 else "moderate"
        precip_desc = pattern_parts[1] if len(pattern_parts) > 1 else "typical"
        wind_desc = pattern_parts[2] if len(pattern_parts) > 2 else "calm"
        
        summary_lines = [
            f"Weather summary for {location} {date_range}:",
            f"The period was generally {temp_desc} with {precip_desc} conditions and {wind_desc} winds."
        ]
        
        # Add temperature details
        temp_unit = "°F" if units == "imperial" else "°C"
        avg_tmin = analysis.get("avg_tmin", 0)
        avg_tmax = analysis.get("avg_tmax", 0)
        
        summary_lines.append(
            f"Average temperatures ranged from {avg_tmin:.1f}{temp_unit} to {avg_tmax:.1f}{temp_unit}."
        )
        
        # Add precipitation details
        total_precip = analysis.get("total_precip", 0)
        if total_precip > 0:
            summary_lines.append(f"Total precipitation was {total_precip:.1f}mm.")
        
        # Add notable events
        notable_days = analysis.get("notable_days", [])
        if notable_days:
            notable_desc = []
            for day in notable_days[:3]:  # Limit to 3 most notable
                try:
                    date_obj = datetime.strptime(day["date"], "%Y-%m-%d")
                    date_str = date_obj.strftime("%B %d")
                    notable_desc.append(f"{date_str} had {day['note']}")
                except:
                    notable_desc.append(f"{day['date']} had {day['note']}")
            
            if notable_desc:
                summary_lines.append("Notable events: " + "; ".join(notable_desc) + ".")
        
        return " ".join(summary_lines)
    
    def _calculate_confidence(self, analysis: Dict[str, Any], data_points: int) -> float:
        """Calculate confidence score for the analysis."""
        confidence = 0.5  # Base confidence
        
        # More data points increase confidence
        if data_points >= 7:
            confidence += 0.2
        elif data_points >= 3:
            confidence += 0.1
        
        # Having extremes increases confidence
        if analysis.get("extremes", {}).get("coldest") and analysis.get("extremes", {}).get("hottest"):
            confidence += 0.1
        
        # Having notable days increases confidence
        if analysis.get("notable_days"):
            confidence += 0.1
        
        # Pattern detection increases confidence
        if analysis.get("pattern"):
            confidence += 0.1
        
        return min(confidence, 1.0)


def analyze_weather(weather_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    CrewAI Task C - Analyze weather data and generate summary.
    """
    analyst = WeatherAnalyst()
    return analyst.analyze_weather_data(weather_data)