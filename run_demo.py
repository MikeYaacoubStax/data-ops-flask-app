#!/usr/bin/env python3
"""
NoSQLBench Demo Application Launcher
"""

import sys
import os
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_requirements():
    """Check if required dependencies are installed"""
    try:
        import flask
        import docker
        import psutil
        logger.info("✓ All required Python packages are available")
        return True
    except ImportError as e:
        logger.error(f"✗ Missing required package: {e}")
        logger.info("Please install requirements: pip install -r requirements.txt")
        return False

def check_docker():
    """Check if Docker is available and running"""
    try:
        import docker
        client = docker.from_env()
        client.ping()
        logger.info("✓ Docker is available and running")
        return True
    except Exception as e:
        logger.error(f"✗ Docker is not available: {e}")
        logger.info("Please ensure Docker is installed and running")
        return False

def check_nosqlbench():
    """Check if NoSQLBench is available"""
    try:
        result = subprocess.run(['nb5', '--version'], capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            logger.info("✓ NoSQLBench (nb5) is available")
            return True
        else:
            logger.warning("✗ NoSQLBench (nb5) not found in PATH")
            logger.info("Please install NoSQLBench or ensure 'nb5' is in your PATH")
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        logger.warning("✗ NoSQLBench (nb5) not found in PATH")
        logger.info("Please install NoSQLBench or ensure 'nb5' is in your PATH")
        return False

def main():
    """Main entry point"""
    logger.info("🚀 Starting NoSQLBench Demo Application")
    
    # Check prerequisites
    logger.info("Checking prerequisites...")
    
    checks_passed = 0
    total_checks = 3
    
    if check_requirements():
        checks_passed += 1
    
    if check_docker():
        checks_passed += 1
    
    if check_nosqlbench():
        checks_passed += 1
    
    logger.info(f"Prerequisites check: {checks_passed}/{total_checks} passed")
    
    if checks_passed < 2:  # Allow running without NoSQLBench for demo purposes
        logger.error("Critical prerequisites not met. Please fix the issues above.")
        sys.exit(1)
    
    if checks_passed < total_checks:
        logger.warning("Some prerequisites not met. Some features may not work correctly.")
    
    # Start the Flask application
    logger.info("Starting Flask application...")
    logger.info("Dashboard will be available at: http://localhost:5000")
    logger.info("Press Ctrl+C to stop the application")
    
    try:
        from app import app, socketio, graceful_shutdown
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        graceful_shutdown()
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        graceful_shutdown()
        sys.exit(1)

if __name__ == "__main__":
    main()
