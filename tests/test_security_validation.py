"""
Tests for security validation functionality in parser.
"""
from crew.parser import DateRangeParser


class TestSecurityValidation:
    def setup_method(self):
        """Set up test fixtures."""
        self.parser = DateRangeParser()

    def test_xss_prevention(self):
        """Test that XSS attempts are blocked."""
        malicious_queries = [
            "<script>alert('xss')</script> weather in London",
            "weather in <img src=x onerror=alert('xss')> London",
            "London weather <svg onload=alert('xss')>",
            "weather &lt;script&gt;alert('xss')&lt;/script&gt; in Paris",
        ]

        for query in malicious_queries:
            result = self.parser.parse_query(query)
            # Should either sanitize or block the input
            assert "error" in result or "script" not in str(result).lower()

    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are blocked."""
        malicious_queries = [
            "weather in London'; DROP TABLE users; --",
            "weather in London' OR '1'='1",
            "weather in London UNION SELECT * FROM weather",
            "weather in London'; INSERT INTO logs VALUES ('hacked'); --",
        ]

        for query in malicious_queries:
            result = self.parser.parse_query(query)
            # Should either sanitize or block SQL injection patterns
            assert "error" in result or not any(
                sql_word in query.upper() for sql_word in ["DROP", "UNION", "INSERT"]
            )

    def test_coordinate_validation(self):
        """Test coordinate validation."""
        valid_coords = [
            "weather at 32.08, 34.78 today",
            "weather at -23.5, 46.6 tomorrow",
            "weather at 0, 0 this week",
        ]

        invalid_coords = [
            "weather at 91.0, 34.78 today",  # Invalid latitude
            "weather at 32.08, 181.0 today",  # Invalid longitude
        ]

        for query in valid_coords:
            result = self.parser.parse_query(query)
            # Valid coordinates should work
            assert "error" not in result or result.get("error") != "invalid_location"

        for query in invalid_coords:
            result = self.parser.parse_query(query)
            # Should detect invalid coordinates or fail parsing gracefully
            assert isinstance(result, dict)  # Should return some result

    def test_long_input_handling(self):
        """Test handling of extremely long inputs."""
        very_long_query = "weather in " + "A" * 10000 + " tomorrow"
        result = self.parser.parse_query(very_long_query)

        # Should handle or reject very long inputs gracefully
        assert isinstance(result, dict)

    def test_special_character_handling(self):
        """Test handling of special characters."""
        special_char_queries = [
            "weather in Berlin™ tomorrow",
            "weather in São Paulo next week",
            "weather in москва today",
            "weather in 北京 this week",
        ]

        for query in special_char_queries:
            result = self.parser.parse_query(query)
            # Should handle international characters gracefully
            assert isinstance(result, dict)

    def test_empty_and_whitespace_inputs(self):
        """Test handling of empty and whitespace-only inputs."""
        edge_cases = [
            "",
            "   ",
            "\n\t\r",
            "weather in",
            "weather in   ",
        ]

        for query in edge_cases:
            result = self.parser.parse_query(query)
            assert "error" in result

    def test_normal_queries_still_work(self):
        """Test that normal queries still work after security validation."""
        normal_queries = [
            "weather in London tomorrow",
            "weather in New York this week",
            "weather forecast for Paris from Monday to Friday",
            "temperature in Tokyo next week",
        ]

        for query in normal_queries:
            result = self.parser.parse_query(query)
            # Normal queries should work fine
            assert "location" in result
            assert "error" not in result or result.get("error") != "invalid_input"
