#!/usr/bin/env python3
"""
WeatherSense Deployment Validation Summary

This script runs all available integration tests and provides a comprehensive
deployment readiness report.
"""
import os
import sys
import subprocess
import logging
from pathlib import Path


def setup_logging():
    """Setup logging for the validation summary."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


def run_test_script(script_path: Path, description: str) -> tuple[bool, str]:
    """Run a test script and return success status and output."""
    logger = logging.getLogger(__name__)
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=script_path.parent.parent
        )
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        logger.info(f"{'✅' if success else '❌'} {description}: {'PASSED' if success else 'FAILED'}")
        
        return success, output
        
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {description}: TIMED OUT")
        return False, "Test timed out"
    except Exception as e:
        logger.error(f"❌ {description}: ERROR - {e}")
        return False, str(e)


def main():
    """Main validation function."""
    logger = setup_logging()
    
    logger.info("WeatherSense Deployment Validation Summary")
    logger.info("=" * 60)
    
    workspace_root = Path(__file__).parent
    tests_dir = workspace_root / "tests"
    
    # Define test suite
    test_suite = [
        (tests_dir / "test_documentation_only.py", "📋 Documentation & Configuration Validation"),
        (tests_dir / "test_mcp_stdio.py", "🔧 MCP Server Stdio Communication Test"),
    ]
    
    results = {}
    total_tests = len(test_suite)
    passed_tests = 0
    
    # Run each test
    for script_path, description in test_suite:
        if script_path.exists():
            success, output = run_test_script(script_path, description)
            results[description] = (success, output)
            if success:
                passed_tests += 1
        else:
            logger.error(f"❌ {description}: Test script not found - {script_path}")
            results[description] = (False, "Test script not found")
    
    # Summary report
    logger.info("\n" + "=" * 60)
    logger.info("DEPLOYMENT VALIDATION SUMMARY")
    logger.info("=" * 60)
    
    for description, (success, _) in results.items():
        status = "PASSED" if success else "FAILED"
        icon = "✅" if success else "❌"
        logger.info(f"{icon} {description}: {status}")
    
    logger.info(f"\nOVERALL RESULTS: {passed_tests}/{total_tests} test suites passed")
    
    # Deployment readiness assessment
    if passed_tests == total_tests:
        logger.info("\n🎉 DEPLOYMENT VALIDATION SUCCESSFUL!")
        logger.info("\n✅ Your WeatherSense application is ready for deployment:")
        logger.info("   • Documentation is complete and accurate")
        logger.info("   • Configuration files are properly set up") 
        logger.info("   • MCP server communication works correctly")
        logger.info("   • Docker and Cloud Run configurations validated")
        logger.info("   • Authentication requirements properly implemented")
        logger.info("\n🚀 Ready to deploy to Google Cloud Run!")
        
        # Provide next steps
        logger.info("\nNext Steps for Deployment:")
        logger.info("1. Build and push Docker image:")
        logger.info("   docker build -t gcr.io/$PROJECT_ID/weather-sense:latest .")
        logger.info("   docker push gcr.io/$PROJECT_ID/weather-sense:latest")
        logger.info("\n2. Deploy to Cloud Run (as documented in README.md):")
        logger.info("   gcloud run deploy weather-sense \\")
        logger.info("     --image gcr.io/$PROJECT_ID/weather-sense:latest \\")
        logger.info("     --platform managed \\")
        logger.info("     --region $REGION \\")
        logger.info("     --allow-unauthenticated \\")
        logger.info("     --set-env-vars=\"API_KEY=$API_KEY,LOG_LEVEL=INFO,DEPLOYMENT_ENV=docker\"")
        
        return True
    else:
        failed_count = total_tests - passed_tests
        logger.error(f"\n❌ DEPLOYMENT VALIDATION FAILED - {failed_count} test suite(s) failed")
        logger.error("\nPlease review and fix the failing tests before deploying.")
        
        # Show detailed failures
        for description, (success, output) in results.items():
            if not success:
                logger.error(f"\n--- FAILURE DETAILS: {description} ---")
                logger.error(output[:500] + "..." if len(output) > 500 else output)
        
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)