#!/usr/bin/env python3
"""
NoSQLBench Kubernetes Demo Flask Application
Main application file with Flask routes and SocketIO handlers for Kubernetes deployment
"""

import os
import sys
import logging
import threading
import time
import signal
import atexit
import yaml
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from werkzeug.serving import make_server

# Import Kubernetes services
from services.k8s_job_manager import KubernetesJobManager
from services.k8s_state_manager import KubernetesStateManager
from services.config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Initialize managers
config_manager = ConfigManager()
state_manager = KubernetesStateManager()
job_manager = KubernetesJobManager(config_manager, state_manager)

# Global variables for graceful shutdown
shutdown_event = threading.Event()
status_thread = None

def start_status_monitor():
    """Start background thread for status monitoring"""
    global status_thread
    if status_thread is None or not status_thread.is_alive():
        status_thread = threading.Thread(target=status_monitor_loop, daemon=True)
        status_thread.start()
        logger.info("Status monitor thread started")

def status_monitor_loop():
    """Background loop for monitoring job status and emitting updates"""
    while not shutdown_event.is_set():
        try:
            # Get current status
            status = get_application_status()
            
            # Emit status update via WebSocket
            socketio.emit('status_update', status)
            
            # Sleep for 2 seconds
            time.sleep(2)
            
        except Exception as e:
            logger.error(f"Error in status monitor: {e}")
            time.sleep(5)

def get_application_status():
    """Get comprehensive application status"""
    try:
        # Get database configuration
        db_config = config_manager.get_database_config()
        
        # Get available workloads
        available_workloads = config_manager.get_available_workloads()
        
        # Get setup status
        setup_status = job_manager.get_setup_status()
        
        # Get workloads ready for benchmarking
        ready_for_benchmark = job_manager.get_workloads_ready_for_benchmark()
        
        # Get running benchmarks
        running_benchmarks = job_manager.get_running_benchmarks()
        
        return {
            "kubernetes": {
                "namespace": job_manager.namespace,
                "ready": True
            },
            "databases": {
                "configured": len([db for db, config in db_config.items() if config.get('enabled')]) > 0,
                "config": db_config
            },
            "workloads": {
                "available": available_workloads,
                "setup_status": setup_status,
                "ready_for_benchmark": ready_for_benchmark
            },
            "benchmarks": {
                "running": running_benchmarks
            }
        }
    except Exception as e:
        logger.error(f"Error getting application status: {e}")
        return {"error": str(e)}

# Routes
@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": time.time()})

@app.route('/api/ready')
def ready():
    """Readiness check endpoint"""
    try:
        # Check if we can connect to Kubernetes API
        job_manager.list_jobs()
        return jsonify({"status": "ready", "timestamp": time.time()})
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({"status": "not ready", "error": str(e)}), 503

@app.route('/api/status')
def status():
    """Get application status"""
    return jsonify(get_application_status())

@app.route('/api/databases/config')
def get_database_config():
    """Get database configuration"""
    try:
        config = config_manager.get_database_config()
        return jsonify({"success": True, "config": config})
    except Exception as e:
        logger.error(f"Failed to get database config: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/workloads/available')
def get_available_workloads():
    """Get available workloads"""
    try:
        workloads = config_manager.get_available_workloads()
        return jsonify({"success": True, "workloads": workloads})
    except Exception as e:
        logger.error(f"Failed to get available workloads: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/setup/status')
def get_setup_status():
    """Get setup status for all workloads"""
    try:
        status = job_manager.get_setup_status()
        return jsonify({"success": True, "status": status})
    except Exception as e:
        logger.error(f"Failed to get setup status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/setup/run', methods=['POST'])
def run_setup():
    """Run setup phases for selected workloads"""
    try:
        data = request.get_json()
        workloads = data.get('workloads', [])
        
        if not workloads:
            return jsonify({"success": False, "error": "No workloads specified"}), 400
        
        results = []
        for workload in workloads:
            logger.info(f"Running setup for workload: {workload}")
            result = job_manager.run_setup_phases(workload)
            results.append(result)
        
        return jsonify({
            "success": True,
            "results": results
        })
        
    except Exception as e:
        logger.error(f"Failed to run setup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/benchmarks/start', methods=['POST'])
def start_benchmark():
    """Start a benchmark"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        cycle_rate = data.get('cycle_rate', 10)
        
        if not workload:
            return jsonify({"success": False, "error": "No workload specified"}), 400
        
        result = job_manager.start_benchmark(workload, cycle_rate)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to start benchmark: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/benchmarks/stop', methods=['POST'])
def stop_benchmark():
    """Stop a benchmark"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        
        if not workload:
            return jsonify({"success": False, "error": "No workload specified"}), 400
        
        result = job_manager.stop_benchmark(workload)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to stop benchmark: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/benchmarks/update-throughput', methods=['POST'])
def update_throughput():
    """Update benchmark throughput"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        cycle_rate = data.get('cycle_rate')
        
        if not workload or cycle_rate is None:
            return jsonify({"success": False, "error": "Workload and cycle_rate required"}), 400
        
        result = job_manager.update_benchmark_throughput(workload, cycle_rate)
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to update throughput: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/benchmarks/running')
def get_running_benchmarks():
    """Get running benchmarks"""
    try:
        benchmarks = job_manager.get_running_benchmarks()
        return jsonify({"success": True, "benchmarks": benchmarks})
    except Exception as e:
        logger.error(f"Failed to get running benchmarks: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# WebSocket handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    emit('status_update', get_application_status())

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    graceful_shutdown()

def graceful_shutdown():
    """Gracefully shutdown the application"""
    logger.info("Shutting down application...")
    shutdown_event.set()
    
    # Stop any running jobs if needed
    try:
        job_manager.cleanup()
    except Exception as e:
        logger.error(f"Error during job manager cleanup: {e}")

# Register shutdown handlers
atexit.register(graceful_shutdown)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    try:
        # Start status monitoring
        start_status_monitor()
        
        # Auto-setup if enabled
        if config_manager.is_auto_setup_enabled():
            logger.info("Auto-setup is enabled, starting workload setup...")
            try:
                available_workloads = config_manager.get_available_workloads()
                for workload in available_workloads:
                    logger.info(f"Auto-setting up workload: {workload}")
                    job_manager.run_setup_phases(workload)
            except Exception as e:
                logger.error(f"Auto-setup failed: {e}")
        
        # Run the application
        logger.info("Starting NoSQLBench Kubernetes Demo Application")
        logger.info("Dashboard available at: http://localhost:5000")
        
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        graceful_shutdown()
    except Exception as e:
        logger.error(f"Application error: {e}")
        graceful_shutdown()
    finally:
        # Ensure we exit
        import os
        os._exit(0)
