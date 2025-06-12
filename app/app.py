#!/usr/bin/env python3
"""
NoSQLBench Demo Flask Application
Main application file with Flask routes and SocketIO handlers
"""

import os
import sys
import logging
import threading
import time
import signal
import atexit
from flask import Flask, render_template, request, jsonify, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.serving import make_server

# Import our services
from config import config
from services.benchmark_manager import BenchmarkManager
from services.docker_manager import DockerManager
from services.state_manager import StateManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.secret_key

# Initialize SocketIO (using threading mode instead of eventlet for compatibility)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading',
                   ping_timeout=60, ping_interval=25)

# Initialize managers
state_manager = StateManager()
benchmark_manager = BenchmarkManager(config, state_manager)
docker_manager = DockerManager()

# Global variables for graceful shutdown
shutdown_event = threading.Event()
status_thread = None

def start_status_monitor():
    """Start the status monitoring thread"""
    global status_thread
    if status_thread is None or not status_thread.is_alive():
        status_thread = threading.Thread(target=status_monitor_loop, daemon=True)
        status_thread.start()
        logger.info("Status monitor thread started")

def status_monitor_loop():
    """Background thread to monitor and emit status updates"""
    last_status = None
    # Get status update interval from environment (default 5 seconds)
    update_interval = int(os.getenv('STATUS_UPDATE_INTERVAL', '5'))

    while not shutdown_event.is_set():
        try:
            # Get current status
            status = get_application_status()

            # Only emit if status actually changed (reduce unnecessary updates)
            if status != last_status:
                socketio.emit('status_update', status)
                last_status = status.copy() if isinstance(status, dict) else status
                logger.debug("Status update emitted")

            # Wait for next update - configurable interval for stability
            shutdown_event.wait(update_interval)

        except Exception as e:
            logger.error(f"Error in status monitor: {e}")
            shutdown_event.wait(update_interval * 2)  # Wait longer on error

def get_application_status():
    """Get comprehensive application status"""
    try:
        # Get infrastructure status
        vm_status = docker_manager.get_container_status("demo-victoriametrics")
        grafana_status = docker_manager.get_container_status("demo-grafana")

        # Get database configuration
        db_config = state_manager.get_database_config()

        # Get available workloads
        available_workloads = benchmark_manager.get_available_workloads(db_config)

        # Get setup status
        setup_status = benchmark_manager.get_setup_status()

        # Get workloads ready for benchmarking
        ready_for_benchmark = benchmark_manager.get_workloads_ready_for_benchmark(db_config)

        # Get running benchmarks
        running_benchmarks = benchmark_manager.get_running_benchmarks()

        return {
            "infrastructure": {
                "victoriametrics": vm_status,
                "grafana": grafana_status,
                "ready": vm_status.get("status") == "running" and grafana_status.get("status") == "running"
            },
            "databases": {
                "configured": state_manager.is_databases_configured(),
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

@app.route('/api/status')
def api_status():
    """Get current application status"""
    return jsonify(get_application_status())

@app.route('/api/infrastructure/start', methods=['POST'])
def start_infrastructure():
    """Start monitoring infrastructure (VictoriaMetrics and Grafana)"""
    try:
        # Start VictoriaMetrics
        vm_result = docker_manager.start_victoriametrics(config.infrastructure.victoriametrics_port)
        
        # Start Grafana
        grafana_result = docker_manager.start_grafana(
            config.infrastructure.grafana_port,
            vm_result["internal_endpoint"]
        )
        
        # Update state
        state_manager.update_infrastructure_status(True)
        
        return jsonify({
            "success": True,
            "victoriametrics": vm_result,
            "grafana": grafana_result
        })
        
    except Exception as e:
        logger.error(f"Failed to start infrastructure: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/infrastructure/stop', methods=['POST'])
def stop_infrastructure():
    """Stop monitoring infrastructure"""
    try:
        result = docker_manager.cleanup_all()
        state_manager.update_infrastructure_status(False)
        
        return jsonify({
            "success": True,
            "result": result
        })
        
    except Exception as e:
        logger.error(f"Failed to stop infrastructure: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/databases/configure', methods=['POST'])
def configure_databases():
    """Configure database connections"""
    try:
        db_config = request.get_json()
        
        # Validate configuration
        if not db_config:
            return jsonify({"success": False, "error": "No configuration provided"}), 400
        
        # Update state
        state_manager.update_database_config(db_config)
        
        # Get available workloads with new configuration
        available_workloads = benchmark_manager.get_available_workloads(db_config)
        
        return jsonify({
            "success": True,
            "available_workloads": available_workloads
        })
        
    except Exception as e:
        logger.error(f"Failed to configure databases: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/workloads/available')
def get_available_workloads():
    """Get list of available workloads based on current database configuration"""
    try:
        db_config = state_manager.get_database_config()
        available_workloads = benchmark_manager.get_available_workloads(db_config)
        
        return jsonify({
            "success": True,
            "workloads": available_workloads
        })
        
    except Exception as e:
        logger.error(f"Failed to get available workloads: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/setup/run', methods=['POST'])
def run_setup():
    """Run setup phases for selected workloads"""
    try:
        data = request.get_json()
        workloads = data.get('workloads', [])
        auto_start_benchmarks = data.get('auto_start_benchmarks', True)

        if not workloads:
            return jsonify({"success": False, "error": "No workloads specified"}), 400

        db_config = state_manager.get_database_config()
        results = []

        for workload in workloads:
            logger.info(f"Running setup for workload: {workload}")
            result = benchmark_manager.run_setup_phase(workload, db_config, auto_start_benchmarks)
            results.append(result)

            # Update setup status
            state_manager.update_setup_status(workload, result.get("success", False))

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
        
        db_config = state_manager.get_database_config()
        result = benchmark_manager.start_benchmark(workload, cycle_rate, db_config)
        
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
        
        result = benchmark_manager.stop_benchmark(workload)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to stop benchmark: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/benchmarks/update-rate', methods=['POST'])
def update_cycle_rate():
    """Update cycle rate for a running benchmark"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        new_rate = data.get('cycle_rate')
        
        if not workload or new_rate is None:
            return jsonify({"success": False, "error": "Missing workload or cycle_rate"}), 400
        
        db_config = state_manager.get_database_config()
        result = benchmark_manager.update_cycle_rate(workload, new_rate, db_config)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to update cycle rate: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/cleanup', methods=['POST'])
def cleanup():
    """Stop all benchmarks and cleanup"""
    try:
        # Stop all running benchmarks
        running_benchmarks = benchmark_manager.get_running_benchmarks()
        stopped_benchmarks = []
        
        for workload in running_benchmarks.keys():
            result = benchmark_manager.stop_benchmark(workload)
            if result.get("success"):
                stopped_benchmarks.append(workload)
        
        return jsonify({
            "success": True,
            "stopped_benchmarks": stopped_benchmarks
        })
        
    except Exception as e:
        logger.error(f"Failed to cleanup: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    emit('status_update', get_application_status())

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")

def graceful_shutdown():
    """Graceful shutdown handler"""
    logger.info("Initiating graceful shutdown...")

    # Signal status monitor to stop
    shutdown_event.set()

    # Stop all running benchmarks
    try:
        running_benchmarks = benchmark_manager.get_running_benchmarks()
        for workload in running_benchmarks.keys():
            logger.info(f"Stopping benchmark: {workload}")
            benchmark_manager.stop_benchmark(workload)
    except Exception as e:
        logger.error(f"Error stopping benchmarks during shutdown: {e}")

    # Clear state
    try:
        state_manager.clear_all_state()
    except Exception as e:
        logger.error(f"Error clearing state during shutdown: {e}")

    logger.info("Graceful shutdown completed")

    # Force exit
    import os
    os._exit(0)

# Global flag to prevent multiple shutdowns
shutdown_in_progress = False

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    global shutdown_in_progress
    if shutdown_in_progress:
        logger.info("Shutdown already in progress, forcing exit...")
        import os
        os._exit(1)

    shutdown_in_progress = True
    logger.info(f"Received signal {signum}, initiating shutdown...")
    graceful_shutdown()

# Register shutdown handlers
atexit.register(graceful_shutdown)
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    try:
        # Start status monitoring
        start_status_monitor()

        # Run the application
        logger.info("Starting NoSQLBench Demo Application")
        logger.info("Dashboard available at: http://localhost:5000")

        # Use allow_unsafe_werkzeug=True to avoid warnings in development
        socketio.run(app, host='0.0.0.0', port=5000, debug=config.debug, allow_unsafe_werkzeug=True)

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
