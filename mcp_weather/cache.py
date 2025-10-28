"""
Cache implementation for weather data with TTL support.
"""
import time
from typing import Dict, Any, Optional


class InMemoryCache:
    def __init__(self, ttl_seconds: int = 600):  # 10 minutes default
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Dict[str, Any]] = {}
    
    def _generate_key(self, lat: float, lon: float, start_date: str, end_date: str, units: str) -> str:
        """Generate cache key from parameters."""
        return f"{lat:.2f},{lon:.2f},{start_date},{end_date},{units}"
    
    def get(self, lat: float, lon: float, start_date: str, end_date: str, units: str) -> Optional[Dict[str, Any]]:
        """Get cached weather data if not expired."""
        key = self._generate_key(lat, lon, start_date, end_date, units)
        
        if key not in self._cache:
            return None
            
        entry = self._cache[key]
        if time.time() - entry["timestamp"] > self.ttl_seconds:
            del self._cache[key]
            return None
            
        return entry["data"]
    
    def set(self, lat: float, lon: float, start_date: str, end_date: str, units: str, data: Dict[str, Any]) -> None:
        """Cache weather data with current timestamp."""
        key = self._generate_key(lat, lon, start_date, end_date, units)
        self._cache[key] = {
            "data": data,
            "timestamp": time.time()
        }
    
    def clear(self) -> None:
        """Clear all cached data."""
        self._cache.clear()


# Global cache instance
weather_cache = InMemoryCache()