"""
Enhanced unit tests for MCP Weather Cache.
"""
# Fix import paths for cache
import os
import sys
import threading
import time
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mcp_weather"))

from cache import InMemoryCache, weather_cache


class TestInMemoryCacheBasic:
    def setup_method(self):
        """Setup test fixtures."""
        self.cache = InMemoryCache(ttl_seconds=600)
        self.test_data = {
            "location": "Tel Aviv, IL",
            "latitude": 32.08,
            "longitude": 34.78,
            "daily": [{"date": "2025-10-20", "tmin": 20.0, "tmax": 28.0}],
        }

    def test_cache_initialization_default_ttl(self):
        """Test cache initialization with default TTL."""
        cache = InMemoryCache()
        assert cache.ttl_seconds == 600
        assert cache._cache == {}

    def test_cache_initialization_custom_ttl(self):
        """Test cache initialization with custom TTL."""
        cache = InMemoryCache(ttl_seconds=300)
        assert cache.ttl_seconds == 300
        assert cache._cache == {}

    def test_generate_key_format(self):
        """Test cache key generation format."""
        key = self.cache._generate_key(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric"
        )
        expected = "32.08,34.78,2025-10-20,2025-10-24,metric"
        assert key == expected

    def test_generate_key_precision(self):
        """Test cache key generation with float precision."""
        key = self.cache._generate_key(
            32.08456, 34.78123, "2025-10-20", "2025-10-24", "imperial"
        )
        expected = "32.08,34.78,2025-10-20,2025-10-24,imperial"
        assert key == expected

    def test_generate_key_consistency(self):
        """Test cache key generation is consistent."""
        key1 = self.cache._generate_key(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric"
        )
        key2 = self.cache._generate_key(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric"
        )
        assert key1 == key2


class TestInMemoryCacheOperations:
    def setup_method(self):
        """Setup test fixtures."""
        self.cache = InMemoryCache(ttl_seconds=600)
        self.test_data = {
            "location": "Tel Aviv, IL",
            "daily": [{"date": "2025-10-20", "tmin": 20.0, "tmax": 28.0}],
        }

    def test_set_and_get_data(self):
        """Test basic cache set and get operations."""
        # Set data
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )

        # Get data
        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")

        assert result == self.test_data

    def test_get_nonexistent_key(self):
        """Test getting data for non-existent key."""
        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result is None

    def test_cache_miss_different_parameters(self):
        """Test cache miss with slightly different parameters."""
        # Set data
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )

        # Try different coordinates
        result = self.cache.get(32.09, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result is None

        # Try different dates
        result = self.cache.get(32.08, 34.78, "2025-10-21", "2025-10-24", "metric")
        assert result is None

        # Try different units
        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "imperial")
        assert result is None

    def test_cache_overwrite_same_key(self):
        """Test overwriting data for the same key."""
        # Set initial data
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )

        # Set new data for same key
        new_data = {"location": "Tel Aviv, IL", "updated": True}
        self.cache.set(32.08, 34.78, "2025-10-20", "2025-10-24", "metric", new_data)

        # Get data should return new data
        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result == new_data
        assert result != self.test_data


class TestInMemoryCacheTTL:
    def setup_method(self):
        """Setup test fixtures."""
        self.cache = InMemoryCache(ttl_seconds=2)  # 2 seconds for faster testing
        self.test_data = {"location": "Tel Aviv, IL"}

    @patch("time.time")
    def test_ttl_not_expired(self, mock_time):
        """Test data retrieval before TTL expiration."""
        # Mock time progression
        mock_time.side_effect = [1000, 1000, 1001]  # set, get, check

        # Set data
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )

        # Get data before expiration
        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result == self.test_data

    def test_ttl_expired(self):
        """Test data expiration after TTL."""
        import time

        # Set data
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )

        # Manually expire the data by modifying timestamp
        key = self.cache._generate_key(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric"
        )
        self.cache._cache[key]["timestamp"] = time.time() - (self.cache.ttl_seconds + 1)

        # Get data after expiration
        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result is None

    def test_expired_data_removed_from_cache(self):
        """Test that expired data is removed from internal cache."""
        import time

        # Set data
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )
        assert len(self.cache._cache) == 1

        # Manually expire the data by modifying timestamp
        key = self.cache._generate_key(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric"
        )
        self.cache._cache[key]["timestamp"] = time.time() - (self.cache.ttl_seconds + 1)

        # Access expired data
        self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")

        # Check that cache is cleaned up
        assert len(self.cache._cache) == 0

    def test_ttl_real_time_integration(self):
        """Test TTL behavior with real time (integration test)."""
        cache = InMemoryCache(ttl_seconds=0.1)  # 100ms

        # Set data
        cache.set(32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data)

        # Get immediately
        result = cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result == self.test_data

        # Wait for expiration
        time.sleep(0.2)

        # Get after expiration
        result = cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result is None


class TestInMemoryCacheClear:
    def setup_method(self):
        """Setup test fixtures."""
        self.cache = InMemoryCache()
        self.test_data = {"location": "Tel Aviv, IL"}

    def test_clear_empty_cache(self):
        """Test clearing empty cache."""
        self.cache.clear()
        assert len(self.cache._cache) == 0

    def test_clear_cache_with_data(self):
        """Test clearing cache with data."""
        # Add multiple entries
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )
        self.cache.set(
            40.71, -74.01, "2025-10-20", "2025-10-24", "imperial", self.test_data
        )

        assert len(self.cache._cache) == 2

        # Clear cache
        self.cache.clear()
        assert len(self.cache._cache) == 0

    def test_clear_and_reuse_cache(self):
        """Test cache functionality after clearing."""
        # Add data
        self.cache.set(
            32.08, 34.78, "2025-10-20", "2025-10-24", "metric", self.test_data
        )

        # Clear
        self.cache.clear()

        # Add new data
        new_data = {"location": "New York, US"}
        self.cache.set(40.71, -74.01, "2025-10-20", "2025-10-24", "imperial", new_data)

        # Verify old data is gone and new data is accessible
        old_result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        new_result = self.cache.get(
            40.71, -74.01, "2025-10-20", "2025-10-24", "imperial"
        )

        assert old_result is None
        assert new_result == new_data


class TestInMemoryCacheEdgeCases:
    def setup_method(self):
        """Setup test fixtures."""
        self.cache = InMemoryCache()

    def test_negative_coordinates(self):
        """Test cache with negative coordinates."""
        data = {"location": "Southern Hemisphere"}
        self.cache.set(-33.87, -151.21, "2025-10-20", "2025-10-24", "metric", data)

        result = self.cache.get(-33.87, -151.21, "2025-10-20", "2025-10-24", "metric")
        assert result == data

    def test_zero_coordinates(self):
        """Test cache with zero coordinates."""
        data = {"location": "Equator/Prime Meridian"}
        self.cache.set(0.0, 0.0, "2025-10-20", "2025-10-24", "metric", data)

        result = self.cache.get(0.0, 0.0, "2025-10-20", "2025-10-24", "metric")
        assert result == data

    def test_extreme_coordinates(self):
        """Test cache with extreme coordinate values."""
        data = {"location": "Extreme location"}
        self.cache.set(89.99, 179.99, "2025-10-20", "2025-10-24", "metric", data)

        result = self.cache.get(89.99, 179.99, "2025-10-20", "2025-10-24", "metric")
        assert result == data

    def test_same_date_range(self):
        """Test cache with same start and end date."""
        data = {"location": "Single day"}
        self.cache.set(32.08, 34.78, "2025-10-20", "2025-10-20", "metric", data)

        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-20", "metric")
        assert result == data

    def test_empty_data(self):
        """Test cache with empty data."""
        empty_data = {}
        self.cache.set(32.08, 34.78, "2025-10-20", "2025-10-24", "metric", empty_data)

        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result == empty_data

    def test_complex_data_structure(self):
        """Test cache with complex nested data."""
        complex_data = {
            "location": "Complex Location",
            "metadata": {"source": "test", "nested": {"deep": "value"}},
            "daily": [
                {"date": "2025-10-20", "data": [1, 2, 3]},
                {"date": "2025-10-21", "data": [4, 5, 6]},
            ],
        }

        self.cache.set(32.08, 34.78, "2025-10-20", "2025-10-24", "metric", complex_data)
        result = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")

        assert result == complex_data
        assert result["metadata"]["nested"]["deep"] == "value"


class TestGlobalCacheInstance:
    def test_global_cache_exists(self):
        """Test that global cache instance exists."""
        assert weather_cache is not None
        assert isinstance(weather_cache, InMemoryCache)

    def test_global_cache_default_ttl(self):
        """Test global cache has default TTL."""
        assert weather_cache.ttl_seconds == 600

    def test_global_cache_functionality(self):
        """Test global cache basic functionality."""
        test_data = {"test": "global"}

        # Clear any existing data
        weather_cache.clear()

        # Test set/get
        weather_cache.set(1.0, 1.0, "2025-01-01", "2025-01-02", "metric", test_data)
        result = weather_cache.get(1.0, 1.0, "2025-01-01", "2025-01-02", "metric")

        assert result == test_data

        # Clean up
        weather_cache.clear()


class TestInMemoryCachePerformance:
    def setup_method(self):
        """Setup test fixtures."""
        self.cache = InMemoryCache()

    def test_multiple_entries_performance(self):
        """Test cache performance with multiple entries."""
        # Add 100 entries
        for i in range(100):
            data = {"entry": i}
            self.cache.set(
                float(i),
                float(i),
                f"2025-10-{i%28+1:02d}",
                f"2025-10-{(i%28+1)+1:02d}",
                "metric",
                data,
            )

        assert len(self.cache._cache) == 100

        # Verify all entries are retrievable
        for i in range(100):
            result = self.cache.get(
                float(i),
                float(i),
                f"2025-10-{i%28+1:02d}",
                f"2025-10-{(i%28+1)+1:02d}",
                "metric",
            )
            assert result["entry"] == i

    def test_key_collision_resistance(self):
        """Test that similar parameters don't cause key collisions."""
        data1 = {"type": "first"}
        data2 = {"type": "second"}

        # Very similar but different coordinates
        self.cache.set(32.08, 34.78, "2025-10-20", "2025-10-24", "metric", data1)
        self.cache.set(32.09, 34.78, "2025-10-20", "2025-10-24", "metric", data2)

        result1 = self.cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        result2 = self.cache.get(32.09, 34.78, "2025-10-20", "2025-10-24", "metric")

        assert result1 == data1
        assert result2 == data2
        assert result1 != result2


@pytest.mark.mcp
class TestInMemoryCacheIntegration:
    """Integration tests for cache with realistic scenarios."""

    def test_realistic_weather_data_caching(self):
        """Test caching with realistic weather data structure."""
        cache = InMemoryCache(ttl_seconds=600)

        realistic_data = {
            "location": "Tel Aviv, Israel",
            "latitude": 32.08,
            "longitude": 34.78,
            "units": "metric",
            "start_date": "2025-10-20",
            "end_date": "2025-10-24",
            "daily": [
                {
                    "date": "2025-10-20",
                    "tmin": 18.5,
                    "tmax": 26.2,
                    "precip_mm": 0.0,
                    "wind_max_kph": 12.3,
                    "code": 1,
                },
                {
                    "date": "2025-10-21",
                    "tmin": 19.1,
                    "tmax": 27.8,
                    "precip_mm": 2.1,
                    "wind_max_kph": 15.7,
                    "code": 61,
                },
            ],
            "source": "open-meteo",
        }

        # Test caching
        cache.set(32.08, 34.78, "2025-10-20", "2025-10-24", "metric", realistic_data)
        result = cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")

        assert result == realistic_data
        assert len(result["daily"]) == 2
        assert result["daily"][0]["tmin"] == 18.5

    def test_cache_hit_miss_patterns(self):
        """Test typical cache hit/miss patterns."""
        cache = InMemoryCache()

        test_data = {"cached": True}

        # First call - cache miss
        result = cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
        assert result is None

        # Set data
        cache.set(32.08, 34.78, "2025-10-20", "2025-10-24", "metric", test_data)

        # Subsequent calls - cache hits
        for _ in range(5):
            result = cache.get(32.08, 34.78, "2025-10-20", "2025-10-24", "metric")
            assert result == test_data

        # Different location - cache miss
        result = cache.get(40.71, -74.01, "2025-10-20", "2025-10-24", "metric")
        assert result is None
