#!/usr/bin/env python3
"""
Docker entrypoint script for WeatherSense.
Manages both API server and MCP server processes for Cloud Run deployment.
"""
import os
import sys
import signal
import subprocess
import time
import logging
from typing import Optional


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global process references
api_process: Optional[subprocess.Popen] = None
cleanup_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global cleanup_requested
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    cleanup_requested = True


def start_api_server():
    """Start the FastAPI server."""
    global api_process
    
    port = os.getenv("PORT", "8000")
    cmd = [
        sys.executable, "-m", "uvicorn", 
        "api.main:app", 
        "--host", "0.0.0.0", 
        "--port", port,
        "--workers", "1",
        "--log-level", "info"
    ]
    
    logger.info(f"Starting API server on port {port}")
    
    try:
        api_process = subprocess.Popen(
            cmd,
            stdout=None,  # Inherit stdout to see logs
            stderr=None,  # Inherit stderr to see logs
            text=True
        )
        
        logger.info(f"API server started with PID {api_process.pid}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to start API server: {e}")
        return False


def monitor_processes():
    """Monitor API server and handle restarts if needed."""
    global api_process, cleanup_requested
    
    while not cleanup_requested:
        if api_process is None or api_process.poll() is not None:
            if not cleanup_requested:
                logger.error("API server stopped unexpectedly, restarting...")
                if not start_api_server():
                    logger.error("Failed to restart API server, exiting")
                    break
        
        # Check process status every 5 seconds
        time.sleep(5)


def cleanup():
    """Clean up processes on shutdown."""
    global api_process
    
    logger.info("Starting cleanup...")
    
    if api_process and api_process.poll() is None:
        logger.info("Terminating API server...")
        try:
            api_process.terminate()
            api_process.wait(timeout=10)
            logger.info("API server terminated gracefully")
        except subprocess.TimeoutExpired:
            logger.warning("API server did not terminate gracefully, killing...")
            api_process.kill()
            api_process.wait()
        except Exception as e:
            logger.error(f"Error terminating API server: {e}")
    
    logger.info("Cleanup complete")


def main():
    """Main entrypoint for Docker container."""
    logger.info("WeatherSense Docker entrypoint starting...")
    
    # Set Docker environment flag
    os.environ["DEPLOYMENT_ENV"] = "docker"
    
    # Validate required environment variables
    required_vars = ["API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start API server
        if not start_api_server():
            logger.error("Failed to start API server")
            sys.exit(1)
        
        logger.info("All services started successfully")
        
        # Monitor processes
        monitor_processes()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        cleanup()
        logger.info("WeatherSense Docker entrypoint shutdown complete")


if __name__ == "__main__":
    main()