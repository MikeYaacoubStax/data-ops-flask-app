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

# Initialize SocketIO with better connection stability
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet',
                   ping_timeout=60, ping_interval=25)

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

            # Sleep for configurable interval for better connection stability
            time.sleep(update_interval)

        except Exception as e:
            logger.error(f"Error in status monitor: {e}")
            time.sleep(update_interval * 2)

def get_application_status():
    """Get comprehensive application status"""
    try:
        # Get configured databases
        databases = state_manager.get_configured_databases()

        # Get all available workloads
        available_workloads = config_manager.get_all_workloads()

        # Get running jobs
        running_jobs = job_manager.get_running_jobs()

        return {
            "kubernetes": {
                "namespace": job_manager.namespace,
                "ready": True
            },
            "databases": {
                "configured": len(databases) > 0,
                "list": databases
            },
            "workloads": {
                "available": available_workloads
            },
            "jobs": {
                "running": running_jobs
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
        # Simple readiness check - just verify the app is running
        # Don't make external API calls that might timeout
        return jsonify({"status": "ready", "timestamp": time.time()})
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({"status": "not ready", "error": str(e)}), 503

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return app.send_static_file(filename)

@app.route('/api/status')
def status():
    """Get application status"""
    return jsonify(get_application_status())

@app.route('/api/databases/list')
def get_databases():
    """Get list of configured databases"""
    try:
        databases = state_manager.get_configured_databases()
        return jsonify({"success": True, "databases": databases})
    except Exception as e:
        logger.error(f"Failed to get databases: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/databases/add', methods=['POST'])
def add_database():
    """Add a new database endpoint"""
    logger.info("Received add database request")
    try:
        logger.info("Getting JSON data from request")
        data = request.get_json()
        logger.info(f"Received data: {data}")

        db_type = data.get('type')  # cassandra, opensearch, presto
        host = data.get('host')
        port = data.get('port')
        name = data.get('name')  # user-defined name for this database

        logger.info(f"Parsed fields: type={db_type}, host={host}, port={port}, name={name}")

        if not all([db_type, host, port, name]):
            logger.warning("Missing required fields")
            return jsonify({"success": False, "error": "Missing required fields: type, host, port, name"}), 400

        if db_type not in ['cassandra', 'opensearch', 'presto']:
            logger.warning(f"Invalid database type: {db_type}")
            return jsonify({"success": False, "error": "Invalid database type. Must be: cassandra, opensearch, or presto"}), 400

        # Add optional authentication fields
        username = data.get('username', '')
        password = data.get('password', '')

        database_config = {
            'type': db_type,
            'host': host,
            'port': int(port),
            'name': name,
            'username': username,
            'password': password,
            'verified': False  # Will be set to True after connectivity test
        }

        logger.info(f"Calling state_manager.add_database with config: {database_config}")
        result = state_manager.add_database(database_config)
        logger.info(f"Got result from state_manager: {result}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to add database: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/databases/test', methods=['POST'])
def test_database_connectivity():
    """Test database connectivity"""
    try:
        logger.info("Received database connectivity test request")
        data = request.get_json()
        db_id = data.get('db_id')
        logger.info(f"Testing connectivity for database ID: {db_id}")

        if not db_id:
            return jsonify({"success": False, "error": "Database ID required"}), 400

        # Run connectivity test with timeout protection
        logger.info("Starting connectivity test...")
        result = job_manager.test_database_connectivity(db_id)
        logger.info(f"Connectivity test completed with result: {result}")
        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to test database connectivity: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/databases/remove', methods=['DELETE'])
def remove_database():
    """Remove a database endpoint"""
    try:
        data = request.get_json()
        db_id = data.get('db_id')

        if not db_id:
            return jsonify({"success": False, "error": "Database ID required"}), 400

        result = state_manager.remove_database(db_id)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to remove database: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/workloads/available')
def get_available_workloads():
    """Get all available workloads (all 7 workloads from helm/workloads/)"""
    try:
        workloads = config_manager.get_all_workloads()
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
    """Start a benchmark job (setup or live scenario)"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        scenario = data.get('scenario')  # 'setup' or 'live'
        database_id = data.get('database_id')
        cycle_rate = data.get('cycle_rate', 10)

        if not all([workload, scenario, database_id]):
            return jsonify({"success": False, "error": "Missing required fields: workload, scenario, database_id"}), 400

        if scenario not in ['setup', 'live']:
            return jsonify({"success": False, "error": "Scenario must be 'setup' or 'live'"}), 400

        result = job_manager.start_job(workload, scenario, database_id, cycle_rate)
        return jsonify(result)

    except Exception as e:
        logger.error(f"Failed to start benchmark: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/benchmarks/stop', methods=['POST'])
def stop_benchmark():
    """Stop a benchmark job"""
    try:
        data = request.get_json()
        job_id = data.get('job_id')

        if not job_id:
            return jsonify({"success": False, "error": "Job ID required"}), 400

        result = job_manager.stop_job(job_id)
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

@app.route('/api/jobs/running')
def get_running_jobs():
    """Get all running jobs"""
    try:
        jobs = job_manager.get_running_jobs()
        return jsonify({"success": True, "jobs": jobs})
    except Exception as e:
        logger.error(f"Failed to get running jobs: {e}")
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
        
        # Auto-setup removed in simplified flow
        
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
