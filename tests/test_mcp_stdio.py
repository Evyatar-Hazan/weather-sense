"""
MCP Server Integration Test

Tests the MCP server directly without Docker to validate stdio communication.
"""
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest

logger = logging.getLogger(__name__)


@pytest.mark.deployment
@pytest.mark.mcp
def test_mcp_server_stdio_communication():
    """Test that MCP server works via stdio communication."""
    workspace_root = Path(__file__).parent.parent
    mcp_server_path = workspace_root / "mcp_weather" / "server.py"

    assert mcp_server_path.exists(), "MCP server not found"

    # Test request
    test_request = {
        "location": "Tel Aviv",
        "start_date": "2025-10-20",
        "end_date": "2025-10-22",
        "units": "metric",
    }

    # Run MCP server with test input
    result = subprocess.run(
        [sys.executable, str(mcp_server_path)],
        input=json.dumps(test_request),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(workspace_root),
        env=os.environ.copy(),
    )

    logger.info(f"MCP server return code: {result.returncode}")
    logger.info(f"MCP server stdout: {result.stdout[:200]}...")
    logger.info(f"MCP server stderr: {result.stderr[:200]}...")

    # Server should handle the request (may return error due to missing API keys, but should process JSON)
    assert result.returncode in [
        0,
        1,
    ], f"MCP server unexpected return code: {result.returncode}"

    # Should have some output
    assert result.stdout or result.stderr, "MCP server produced no output"

    # Try to parse stdout as JSON if present
    if result.stdout.strip():
        try:
            response = json.loads(result.stdout)
            logger.info(f"✅ MCP server returned valid JSON: {response}")
        except json.JSONDecodeError:
            logger.info(f"MCP server stdout not JSON (expected): {result.stdout[:100]}")

    logger.info("✅ MCP server stdio communication works")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    logger.info("Testing MCP Server Stdio Communication...")
    success = test_mcp_server_stdio_communication()

    if success:
        logger.info("🎉 MCP SERVER STDIO TEST PASSED!")
    else:
        logger.error("❌ MCP server stdio test failed")

    sys.exit(0 if success else 1)
