"""
Enhanced unit tests for Weather Provider.
"""
import pytest
import requests
from unittest.mock import Mock, patch, MagicMock

# Fix import paths for provider
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp_weather'))

from provider import WeatherProvider


class TestWeatherProviderInitialization:
    """Test WeatherProvider initialization."""
    
    def test_provider_initialization(self):
        """Test provider initializes with correct URLs."""
        provider = WeatherProvider()
        
        assert provider.geocoding_url == "https://geocoding-api.open-meteo.com/v1/search"
        assert provider.weather_url == "https://api.open-meteo.com/v1/forecast"


class TestWeatherProviderCoordinateDetection:
    """Test coordinate string detection."""
    
    def test_is_coordinates_valid_formats(self):
        """Test valid coordinate formats."""
        provider = WeatherProvider()
        
        valid_coordinates = [
            "32.08,34.78",
            "32.08, 34.78",
            "-32.08,34.78",
            "32.08,-34.78",
            "-32.08,-34.78",
            "0,0",
            "0.0,0.0",
            "90.0,180.0",
            "-90.0,-180.0"
        ]
        
        for coord in valid_coordinates:
            assert provider._is_coordinates(coord) == True
    
    def test_is_coordinates_invalid_formats(self):
        """Test invalid coordinate formats."""
        provider = WeatherProvider()
        
        invalid_coordinates = [
            "Tel Aviv",
            "32.08",  # Only one coordinate
            "32.08,34.78,25.5",  # Three coordinates
            "abc,def",  # Non-numeric
            "32.08,",  # Missing second coordinate
            ",34.78",  # Missing first coordinate
            "",  # Empty string
            "32.08 34.78",  # Space separated instead of comma
        ]
        
        for coord in invalid_coordinates:
            assert provider._is_coordinates(coord) == False


class TestWeatherProviderGeocoding:
    """Test geocoding functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.provider = WeatherProvider()
    
    def test_geocode_coordinates_input(self):
        """Test geocoding with coordinate input."""
        lat, lon, formatted = self.provider.geocode_location("32.08,34.78")
        
        assert lat == 32.08
        assert lon == 34.78
        assert formatted == "32.08,34.78"
    
    def test_geocode_coordinates_with_spaces(self):
        """Test geocoding with spaced coordinates."""
        lat, lon, formatted = self.provider.geocode_location("32.08, 34.78")
        
        assert lat == 32.08
        assert lon == 34.78
        assert formatted == "32.08,34.78"
    
    @patch('requests.get')
    def test_geocode_location_name_success(self, mock_get):
        """Test successful geocoding of location name."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [{
                "latitude": 32.08,
                "longitude": 34.78,
                "name": "Tel Aviv",
                "country": "Israel"
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        lat, lon, formatted = self.provider.geocode_location("Tel Aviv")
        
        assert lat == 32.08
        assert lon == 34.78
        assert formatted == "Tel Aviv, Israel"
        
        # Verify API call
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        params = kwargs.get('params', {})
        assert params['name'] == 'Tel Aviv'
    
    @patch('requests.get')
    def test_geocode_location_name_no_country(self, mock_get):
        """Test geocoding when country is not provided."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [{
                "latitude": 40.71,
                "longitude": -74.01,
                "name": "New York"
                # No country field
            }]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        lat, lon, formatted = self.provider.geocode_location("New York")
        
        assert lat == 40.71
        assert lon == -74.01
        assert formatted == "New York"
    
    @patch('requests.get')
    def test_geocode_location_not_found(self, mock_get):
        """Test geocoding when location is not found."""
        mock_response = Mock()
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError, match="Location 'NonexistentPlace' not found"):
            self.provider.geocode_location("NonexistentPlace")
    
    @patch('requests.get')
    def test_geocode_api_request_error(self, mock_get):
        """Test geocoding when API request fails."""
        mock_get.side_effect = requests.RequestException("Network error")
        
        with pytest.raises(ValueError, match="Failed to geocode location"):
            self.provider.geocode_location("Tel Aviv")
    
    @patch('requests.get')
    def test_geocode_api_http_error(self, mock_get):
        """Test geocoding when API returns HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError, match="Failed to geocode location"):
            self.provider.geocode_location("Tel Aviv")


class TestWeatherProviderWindSpeedConversion:
    """Test wind speed conversion functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.provider = WeatherProvider()
    
    def test_convert_wind_speed_metric(self):
        """Test wind speed conversion for metric units."""
        # Metric units should return km/h as-is
        result = self.provider._convert_wind_speed(15.0, "metric")
        assert result == 15.0
    
    def test_convert_wind_speed_imperial(self):
        """Test wind speed conversion for imperial units."""
        # Imperial units should convert mph to km/h
        result = self.provider._convert_wind_speed(10.0, "imperial")  # 10 mph
        expected = 10.0 * 1.60934  # ~16.09 km/h
        assert abs(result - expected) < 0.001
    
    def test_convert_wind_speed_none_value(self):
        """Test wind speed conversion with None value."""
        result_metric = self.provider._convert_wind_speed(None, "metric")
        result_imperial = self.provider._convert_wind_speed(None, "imperial")
        
        assert result_metric == 0.0
        assert result_imperial == 0.0
    
    def test_convert_wind_speed_zero(self):
        """Test wind speed conversion with zero value."""
        result_metric = self.provider._convert_wind_speed(0.0, "metric")
        result_imperial = self.provider._convert_wind_speed(0.0, "imperial")
        
        assert result_metric == 0.0
        assert result_imperial == 0.0


class TestWeatherProviderSafeGet:
    """Test safe get functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.provider = WeatherProvider()
    
    def test_safe_get_valid_index(self):
        """Test safe get with valid index."""
        data = [10, 20, 30, 40, 50]
        
        assert self.provider._safe_get(data, 0) == 10
        assert self.provider._safe_get(data, 2) == 30
        assert self.provider._safe_get(data, 4) == 50
    
    def test_safe_get_invalid_index(self):
        """Test safe get with invalid index."""
        data = [10, 20, 30]
        
        # Out of bounds indices should return None
        assert self.provider._safe_get(data, 5) is None
        assert self.provider._safe_get(data, -1) is None
    
    def test_safe_get_none_list(self):
        """Test safe get with None list."""
        assert self.provider._safe_get(None, 0) is None
    
    def test_safe_get_empty_list(self):
        """Test safe get with empty list."""
        assert self.provider._safe_get([], 0) is None
    
    def test_safe_get_with_default(self):
        """Test safe get with custom default value."""
        data = [10, 20, 30]
        
        # Valid index should return actual value
        assert self.provider._safe_get(data, 1, default="default") == 20
        
        # Invalid index should return default
        assert self.provider._safe_get(data, 5, default="default") == "default"
        assert self.provider._safe_get(None, 0, default=42) == 42
    
    def test_safe_get_none_values_in_list(self):
        """Test safe get with None values in the list."""
        data = [10, None, 30]
        
        # None value should return default
        assert self.provider._safe_get(data, 1, default=99) == 99
        assert self.provider._safe_get(data, 1) is None


class TestWeatherProviderFetchWeatherData:
    """Test weather data fetching functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.provider = WeatherProvider()
    
    @patch('requests.get')
    def test_fetch_weather_data_metric_success(self, mock_get):
        """Test successful weather data fetch with metric units."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "daily": {
                "time": ["2025-10-20", "2025-10-21"],
                "temperature_2m_min": [18.5, 19.2],
                "temperature_2m_max": [26.3, 27.1],
                "precipitation_sum": [0.0, 2.5],
                "wind_speed_10m_max": [12.3, 15.7],
                "weather_code": [1, 61]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.fetch_weather_data(
            32.08, 34.78, "2025-10-20", "2025-10-21", "metric"
        )
        
        expected = {
            "daily": [
                {
                    "date": "2025-10-20",
                    "tmin": 18.5,
                    "tmax": 26.3,
                    "precip_mm": 0.0,
                    "wind_max_kph": 12.3,
                    "code": 1
                },
                {
                    "date": "2025-10-21", 
                    "tmin": 19.2,
                    "tmax": 27.1,
                    "precip_mm": 2.5,
                    "wind_max_kph": 15.7,
                    "code": 61
                }
            ],
            "source": "open-meteo"
        }
        
        assert result == expected
    
    @patch('requests.get')
    def test_fetch_weather_data_imperial_success(self, mock_get):
        """Test successful weather data fetch with imperial units."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "daily": {
                "time": ["2025-10-20"],
                "temperature_2m_min": [65.3],  # Fahrenheit
                "temperature_2m_max": [79.3],  # Fahrenheit
                "precipitation_sum": [0.0],
                "wind_speed_10m_max": [7.6],  # mph
                "weather_code": [1]
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.fetch_weather_data(
            32.08, 34.78, "2025-10-20", "2025-10-20", "imperial"
        )
        
        # Wind speed should be converted from mph to km/h
        expected_wind_kph = 7.6 * 1.60934
        
        assert len(result["daily"]) == 1
        assert result["daily"][0]["tmin"] == 65.3
        assert result["daily"][0]["tmax"] == 79.3
        assert abs(result["daily"][0]["wind_max_kph"] - expected_wind_kph) < 0.001
        assert result["source"] == "open-meteo"
    
    @patch('requests.get')
    def test_fetch_weather_data_missing_values(self, mock_get):
        """Test weather data fetch with missing values."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "daily": {
                "time": ["2025-10-20", "2025-10-21"],
                "temperature_2m_min": [18.5, None],  # None value
                "temperature_2m_max": [26.3],  # Missing second value
                "precipitation_sum": [None, 2.5],  # None value
                "wind_speed_10m_max": [12.3, 15.7],
                "weather_code": [1]  # Missing second value
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.fetch_weather_data(
            32.08, 34.78, "2025-10-20", "2025-10-21", "metric"
        )
        
        assert len(result["daily"]) == 2
        
        # First day
        assert result["daily"][0]["tmin"] == 18.5
        assert result["daily"][0]["tmax"] == 26.3
        assert result["daily"][0]["precip_mm"] == 0.0  # None -> default 0.0
        assert result["daily"][0]["code"] == 1
        
        # Second day
        assert result["daily"][1]["tmin"] is None  # None value preserved
        assert result["daily"][1]["tmax"] is None  # Missing value
        assert result["daily"][1]["precip_mm"] == 2.5
        assert result["daily"][1]["code"] == 0  # Missing -> default 0
    
    @patch('requests.get')
    def test_fetch_weather_data_api_error(self, mock_get):
        """Test weather data fetch when API request fails."""
        mock_get.side_effect = requests.RequestException("API error")
        
        with pytest.raises(ValueError, match="Failed to fetch weather data"):
            self.provider.fetch_weather_data(
                32.08, 34.78, "2025-10-20", "2025-10-21", "metric"
            )
    
    @patch('requests.get')
    def test_fetch_weather_data_http_error(self, mock_get):
        """Test weather data fetch when API returns HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_get.return_value = mock_response
        
        with pytest.raises(ValueError, match="Failed to fetch weather data"):
            self.provider.fetch_weather_data(
                32.08, 34.78, "2025-10-20", "2025-10-21", "metric"
            )
    
    @patch('requests.get')
    def test_fetch_weather_data_request_parameters(self, mock_get):
        """Test that correct parameters are sent to the weather API."""
        mock_response = Mock()
        mock_response.json.return_value = {"daily": {"time": []}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        self.provider.fetch_weather_data(
            32.08, 34.78, "2025-10-20", "2025-10-21", "metric"
        )
        
        # Verify API call parameters
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        
        params = kwargs['params']
        assert params['latitude'] == 32.08
        assert params['longitude'] == 34.78
        assert params['start_date'] == "2025-10-20"
        assert params['end_date'] == "2025-10-21"
        assert params['temperature_unit'] == "celsius"
        assert params['wind_speed_unit'] == "kmh"
        assert params['precipitation_unit'] == "mm"
        assert params['timezone'] == "UTC"
        
        expected_daily_params = [
            "temperature_2m_min", "temperature_2m_max", "precipitation_sum",
            "wind_speed_10m_max", "weather_code"
        ]
        for param in expected_daily_params:
            assert param in params['daily']


class TestWeatherProviderEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def setup_method(self):
        """Setup test fixtures."""
        self.provider = WeatherProvider()
    
    def test_extreme_coordinates(self):
        """Test with extreme coordinate values."""
        # Should accept extreme but valid coordinates
        lat, lon, formatted = self.provider.geocode_location("89.99,-179.99")
        assert lat == 89.99
        assert lon == -179.99
    
    def test_zero_coordinates(self):
        """Test with zero coordinates."""
        lat, lon, formatted = self.provider.geocode_location("0.0,0.0")
        assert lat == 0.0
        assert lon == 0.0
    
    @patch('requests.get')
    def test_empty_api_response(self, mock_get):
        """Test handling of empty API response."""
        mock_response = Mock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        result = self.provider.fetch_weather_data(
            32.08, 34.78, "2025-10-20", "2025-10-20", "metric"
        )
        
        # Should handle missing 'daily' key gracefully
        assert result["daily"] == []
        assert result["source"] == "open-meteo"
    
    @patch('requests.get')
    def test_malformed_api_response(self, mock_get):
        """Test handling of malformed API response."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "daily": "not a dict"  # Should be a dict
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        # This should raise an AttributeError because 'str' object has no attribute 'get'
        with pytest.raises(AttributeError, match="'str' object has no attribute 'get'"):
            self.provider.fetch_weather_data(
                32.08, 34.78, "2025-10-20", "2025-10-20", "metric"
            )


@pytest.mark.integration
class TestWeatherProviderIntegration:
    """Integration tests for WeatherProvider."""
    
    def test_provider_full_workflow(self):
        """Test the complete provider workflow with mocked responses."""
        provider = WeatherProvider()
        
        with patch('requests.get') as mock_get:
            # Mock geocoding response
            geocoding_response = Mock()
            geocoding_response.json.return_value = {
                "results": [{
                    "latitude": 32.08,
                    "longitude": 34.78,
                    "name": "Tel Aviv",
                    "country": "Israel"
                }]
            }
            geocoding_response.raise_for_status.return_value = None
            
            # Mock weather response
            weather_response = Mock()
            weather_response.json.return_value = {
                "daily": {
                    "time": ["2025-10-20"],
                    "temperature_2m_min": [20.0],
                    "temperature_2m_max": [28.0],
                    "precipitation_sum": [0.0],
                    "wind_speed_10m_max": [15.0],
                    "weather_code": [1]
                }
            }
            weather_response.raise_for_status.return_value = None
            
            mock_get.side_effect = [geocoding_response, weather_response]
            
            # Test geocoding
            lat, lon, formatted = provider.geocode_location("Tel Aviv")
            assert lat == 32.08
            assert lon == 34.78
            assert formatted == "Tel Aviv, Israel"
            
            # Test weather data fetch
            weather_data = provider.fetch_weather_data(
                lat, lon, "2025-10-20", "2025-10-20", "metric"
            )
            
            assert len(weather_data["daily"]) == 1
            assert weather_data["daily"][0]["tmin"] == 20.0
            assert weather_data["daily"][0]["tmax"] == 28.0
            assert weather_data["source"] == "open-meteo"
    
    def test_provider_error_propagation(self):
        """Test that provider errors are properly propagated."""
        provider = WeatherProvider()
        
        # Test geocoding error propagation
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")
            
            with pytest.raises(ValueError, match="Failed to geocode location"):
                provider.geocode_location("Tel Aviv")
        
        # Test weather API error propagation
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("API error")
            
            with pytest.raises(ValueError, match="Failed to fetch weather data"):
                provider.fetch_weather_data(32.08, 34.78, "2025-10-20", "2025-10-20", "metric")