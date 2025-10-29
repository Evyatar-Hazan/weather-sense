#!/usr/bin/env python3
"""
WeatherSense Deployment Integration Test Runner

This script runs comprehensive integration tests to validate that the system
fully meets deployment requirements without mocks or stubs.

Usage:
    python run_integration_tests.py [--verbose] [--test-class CLASS_NAME]
    
Example:
    python run_integration_tests.py --verbose
    python run_integration_tests.py --test-class TestSingleDockerImage
"""
import sys
import os
import argparse
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import our integration tests
from tests.test_deployment_integration import (
    TestSingleDockerImage,
    TestCloudRunDeployment,
    TestAuthenticationBehavior,
    TestProcessManagement,
    TestDocumentationValidation,
    run_integration_tests
)


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    format_str = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def run_specific_test_class(class_name: str, verbose: bool = False):
    """Run tests for a specific test class."""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    test_classes = {
        "TestSingleDockerImage": TestSingleDockerImage,
        "TestCloudRunDeployment": TestCloudRunDeployment,
        "TestAuthenticationBehavior": TestAuthenticationBehavior,
        "TestProcessManagement": TestProcessManagement,
        "TestDocumentationValidation": TestDocumentationValidation
    }
    
    if class_name not in test_classes:
        logger.error(f"Unknown test class: {class_name}")
        logger.error(f"Available classes: {', '.join(test_classes.keys())}")
        return False
    
    logger.info(f"Running {class_name} tests...")
    
    test_class = test_classes[class_name]
    test_instance = test_class()
    test_methods = [method for method in dir(test_instance) if method.startswith('test_')]
    
    passed = 0
    total = 0
    
    try:
        for method_name in test_methods:
            total += 1
            logger.info(f"\n--- {method_name} ---")
            try:
                method = getattr(test_instance, method_name)
                method()
                passed += 1
                logger.info(f"✅ {method_name} PASSED")
            except Exception as e:
                logger.error(f"❌ {method_name} FAILED: {e}")
                if verbose:
                    import traceback
                    traceback.print_exc()
            finally:
                # Clean up after each test
                test_instance.cleanup_docker_resources()
                
    except Exception as e:
        logger.error(f"Failed to run {class_name}: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return False
    
    logger.info(f"\n{class_name} Summary: {passed}/{total} tests passed")
    return passed == total


def run_all_tests(verbose: bool = False):
    """Run all integration tests."""
    setup_logging(verbose)
    logger = logging.getLogger(__name__)
    
    logger.info("Starting WeatherSense Deployment Integration Tests")
    logger.info("=" * 80)
    
    # Check dependencies
    try:
        import docker
        import requests
    except ImportError as e:
        logger.error(f"Missing required dependency: {e}")
        logger.error("Please install test dependencies: pip install -e '.[test]'")
        return False
    
    # Check Docker is available
    try:
        docker_client = docker.from_env()
        docker_client.ping()
    except Exception as e:
        logger.error(f"Docker is not available: {e}")
        logger.error("Please ensure Docker is installed and running")
        return False
    
    # Run all tests
    test_results = run_integration_tests()
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("INTEGRATION TESTS SUMMARY")
    logger.info("=" * 80)
    
    total_tests = 0
    passed_tests = 0
    
    for class_name, methods in test_results.items():
        logger.info(f"\n{class_name}:")
        for method, result in methods.items():
            if method != "class_error":
                total_tests += 1
                if result == "PASSED":
                    passed_tests += 1
                    logger.info(f"  ✅ {method}")
                else:
                    logger.info(f"  ❌ {method}: {result}")
        
        if "class_error" in methods:
            logger.error(f"  ❌ Class error: {methods['class_error']}")
    
    logger.info(f"\nFINAL SUMMARY: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("🎉 ALL INTEGRATION TESTS PASSED!")
        logger.info("\n✅ Your WeatherSense deployment meets all requirements:")
        logger.info("   • Single Docker image builds successfully")  
        logger.info("   • FastAPI and MCP communication works correctly")
        logger.info("   • Cloud Run deployment configuration is valid")
        logger.info("   • Authentication behavior matches specifications")
        logger.info("   • Process management works as expected")
        logger.info("   • Documentation is complete and accurate")
        return True
    else:
        failed_count = total_tests - passed_tests
        logger.error(f"❌ {failed_count} test(s) failed")
        logger.error("Please review the failures above and fix the issues")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Run WeatherSense deployment integration tests",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--verbose", "-v", 
        action="store_true",
        help="Enable verbose logging with debug information"
    )
    
    parser.add_argument(
        "--test-class", "-c",
        type=str,
        help="Run tests for specific class only (e.g., TestSingleDockerImage)"
    )
    
    parser.add_argument(
        "--list-classes", "-l",
        action="store_true", 
        help="List available test classes"
    )
    
    args = parser.parse_args()
    
    if args.list_classes:
        print("Available test classes:")
        print("  • TestSingleDockerImage - Validates Docker image and service startup")
        print("  • TestCloudRunDeployment - Validates Cloud Run configuration") 
        print("  • TestAuthenticationBehavior - Validates authentication requirements")
        print("  • TestProcessManagement - Validates process spawning and communication")
        print("  • TestDocumentationValidation - Validates README and Dockerfile")
        return
    
    if args.test_class:
        success = run_specific_test_class(args.test_class, args.verbose)
    else:
        success = run_all_tests(args.verbose)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()