from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_socketio import SocketIO, emit
import logging
import threading
import time
import signal
import sys
import atexit
from config import config
from services.docker_manager import DockerManager
from services.benchmark_manager import BenchmarkManager
from services.state_manager import StateManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.secret_key
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize managers
docker_manager = DockerManager()
state_manager = StateManager()
benchmark_manager = BenchmarkManager(config, state_manager)

# Validate existing state on startup
state_manager.validate_running_processes(benchmark_manager)

# Graceful shutdown flag
shutdown_in_progress = False

def graceful_shutdown():
    """Perform graceful shutdown of all workloads and clean up state"""
    global shutdown_in_progress
    if shutdown_in_progress:
        return

    shutdown_in_progress = True
    logger.info("🛑 Graceful shutdown initiated...")

    try:
        # First try graceful stop
        logger.info("Attempting graceful stop of all running benchmarks...")
        cleanup_result = benchmark_manager.cleanup_all()

        if cleanup_result["stopped"]:
            logger.info(f"✅ Gracefully stopped benchmarks: {', '.join(cleanup_result['stopped'])}")

        # If there were errors, try force cleanup
        if cleanup_result["errors"]:
            logger.warning(f"⚠️ Errors with graceful stop, attempting force cleanup...")
            force_result = benchmark_manager.force_cleanup_all()

            if force_result["stopped"]:
                logger.info(f"✅ Force stopped benchmarks: {', '.join(force_result['stopped'])}")

            if force_result["errors"]:
                logger.error(f"❌ Failed to force stop: {', '.join(force_result['errors'])}")

        # Clear state manager
        logger.info("Clearing application state...")
        state_manager.clear_all_state()

        logger.info("✅ Graceful shutdown completed")

    except Exception as e:
        logger.error(f"❌ Error during graceful shutdown: {e}")
        # Try force cleanup as last resort
        try:
            logger.info("Attempting emergency force cleanup...")
            benchmark_manager.force_cleanup_all()
            state_manager.clear_all_state()
        except Exception as emergency_error:
            logger.error(f"❌ Emergency cleanup failed: {emergency_error}")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}")
    graceful_shutdown()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Termination signal

# Register cleanup function to run on exit
atexit.register(graceful_shutdown)

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html',
                         workloads=config.workload_configs.keys(),
                         state=state_manager.get_state())

@app.route('/api/infrastructure/start', methods=['POST'])
def start_infrastructure():
    """Start Grafana and VictoriaMetrics containers"""
    try:
        # Start VictoriaMetrics first
        vm_result = docker_manager.start_victoriametrics(config.infrastructure.victoriametrics_port)
        
        # Start Grafana with VictoriaMetrics as datasource
        # Use internal endpoint for container-to-container communication
        vm_internal_endpoint = vm_result.get('internal_endpoint', vm_result['endpoint'])
        grafana_result = docker_manager.start_grafana(
            config.infrastructure.grafana_port,
            vm_internal_endpoint
        )
        
        state_manager.update_infrastructure_status(True)

        return jsonify({
            'success': True,
            'victoriametrics': vm_result,
            'grafana': grafana_result
        })
        
    except Exception as e:
        logger.error(f"Failed to start infrastructure: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/infrastructure/status', methods=['GET'])
def infrastructure_status():
    """Get status of infrastructure containers"""
    try:
        vm_status = docker_manager.get_container_status("demo-victoriametrics")
        grafana_status = docker_manager.get_container_status("demo-grafana")
        
        infrastructure_ready = (vm_status['status'] == 'running' and
                              grafana_status['status'] == 'running')

        state_manager.update_infrastructure_status(infrastructure_ready)
        
        return jsonify({
            'infrastructure_ready': infrastructure_ready,
            'victoriametrics': vm_status,
            'grafana': grafana_status
        })
        
    except Exception as e:
        logger.error(f"Failed to get infrastructure status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/infrastructure/stop', methods=['POST'])
def stop_infrastructure():
    """Stop infrastructure containers"""
    try:
        result = docker_manager.cleanup_all()
        state_manager.update_infrastructure_status(False)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        logger.error(f"Failed to stop infrastructure: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/databases/configure', methods=['POST'])
def configure_databases():
    """Configure database endpoints"""
    try:
        data = request.get_json()
        
        # Update database configuration
        if 'cassandra_host' in data:
            config.database.cassandra_host = data['cassandra_host']
            config.database.cassandra_port = data.get('cassandra_port', 9042)
        
        if 'opensearch_host' in data:
            config.database.opensearch_host = data['opensearch_host']
            config.database.opensearch_port = data.get('opensearch_port', 9200)
        
        if 'presto_host' in data:
            config.database.presto_host = data['presto_host']
            config.database.presto_port = data.get('presto_port', 8080)
            config.database.presto_user = data.get('presto_user', 'testuser')
        
        # Store in state manager
        database_config = {
            'cassandra_host': config.database.cassandra_host,
            'cassandra_port': config.database.cassandra_port,
            'opensearch_host': config.database.opensearch_host,
            'opensearch_port': config.database.opensearch_port,
            'presto_host': config.database.presto_host,
            'presto_port': config.database.presto_port,
            'presto_user': config.database.presto_user
        }

        state_manager.update_database_config(database_config)

        return jsonify({'success': True, 'config': database_config})

    except Exception as e:
        logger.error(f"Failed to configure databases: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/workloads/available', methods=['GET'])
def get_available_workloads():
    """Get list of workloads available based on configured databases"""
    try:
        if not state_manager.is_databases_configured():
            return jsonify({'success': False, 'error': 'Databases not configured'}), 400

        available_workloads = benchmark_manager.get_available_workloads(state_manager.get_database_config())
        all_workloads = list(config.workload_configs.keys())

        workload_info = {}
        for workload in all_workloads:
            workload_config = config.workload_configs[workload]
            driver = workload_config["driver"]
            db_name = {"cql": "Cassandra", "opensearch": "OpenSearch", "jdbc": "Presto"}.get(driver, driver)

            workload_info[workload] = {
                "available": workload in available_workloads,
                "database": db_name,
                "driver": driver,
                "description": workload_config.get("description", "")
            }

        return jsonify({
            'success': True,
            'workloads': workload_info,
            'available_count': len(available_workloads),
            'total_count': len(all_workloads)
        })

    except Exception as e:
        logger.error(f"Failed to get available workloads: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/setup/run', methods=['POST'])
def run_setup():
    """Run setup phases for selected workloads"""
    try:
        data = request.get_json()
        selected_workloads = data.get('workloads', [])

        if not state_manager.is_databases_configured():
            return jsonify({'success': False, 'error': 'Databases not configured'}), 400

        # Validate that all selected workloads have configured databases
        available_workloads = benchmark_manager.get_available_workloads(state_manager.get_database_config())
        invalid_workloads = [w for w in selected_workloads if w not in available_workloads]

        if invalid_workloads:
            return jsonify({
                'success': False,
                'error': f'The following workloads cannot be run because their databases are not configured: {", ".join(invalid_workloads)}'
            }), 400

        # Run setup in background thread
        def setup_thread():
            for workload in selected_workloads:
                logger.info(f"Running setup for {workload}")

                # Emit setup started event
                with app.app_context():
                    socketio.emit('setup_started', {
                        'workload': workload
                    })

                result = benchmark_manager.run_setup_phase(workload, state_manager.get_database_config())
                state_manager.update_setup_status(workload, result['success'])

                # Emit progress update with app context
                with app.app_context():
                    socketio.emit('setup_progress', {
                        'workload': workload,
                        'success': result['success'],
                        'details': result
                    })

                    # Also emit general status update to keep everything in sync
                    try:
                        status_response = get_status()
                        if isinstance(status_response, tuple):
                            response_data = status_response[0].get_json()
                        else:
                            response_data = status_response.get_json()
                        socketio.emit('status_update', response_data)
                    except Exception as e:
                        logger.error(f"Failed to broadcast status update: {e}")
        
        threading.Thread(target=setup_thread, daemon=True).start()
        
        return jsonify({'success': True, 'message': 'Setup started'})
        
    except Exception as e:
        logger.error(f"Failed to start setup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/benchmarks/start', methods=['POST'])
def start_benchmark():
    """Start a benchmark with specified cycle rate"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        cycle_rate = data.get('cycle_rate', config.benchmark.default_cycle_rate)
        
        if not workload:
            return jsonify({'success': False, 'error': 'Workload not specified'}), 400
        
        if not state_manager.get_setup_status(workload):
            return jsonify({'success': False, 'error': f'Setup not completed for {workload}'}), 400

        result = benchmark_manager.start_benchmark(
            workload, cycle_rate, state_manager.get_database_config()
        )

        # Update state manager with benchmark status
        if result.get('success'):
            state_manager.update_running_benchmark(workload, {
                'status': 'running',
                'pid': result.get('pid'),
                'cycle_rate': cycle_rate,
                'phase': 'run',
                'start_time': time.time()
            })

            # Immediately broadcast status update for real-time feel
            try:
                with app.app_context():
                    status_response = get_status()
                    if isinstance(status_response, tuple):
                        response_data = status_response[0].get_json()
                    else:
                        response_data = status_response.get_json()
                    socketio.emit('status_update', response_data)
            except Exception as e:
                logger.error(f"Failed to broadcast status update: {e}")

        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to start benchmark: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/benchmarks/stop', methods=['POST'])
def stop_benchmark():
    """Stop a running benchmark"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        
        if not workload:
            return jsonify({'success': False, 'error': 'Workload not specified'}), 400
        
        result = benchmark_manager.stop_benchmark(workload)

        # Update state manager
        if result.get('success'):
            state_manager.update_running_benchmark(workload, None)

            # Immediately broadcast status update for real-time feel
            try:
                with app.app_context():
                    status_response = get_status()
                    if isinstance(status_response, tuple):
                        response_data = status_response[0].get_json()
                    else:
                        response_data = status_response.get_json()
                    socketio.emit('status_update', response_data)
            except Exception as e:
                logger.error(f"Failed to broadcast status update: {e}")

        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to stop benchmark: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/benchmarks/update-rate', methods=['POST'])
def update_cycle_rate():
    """Update cycle rate for a running benchmark"""
    try:
        data = request.get_json()
        workload = data.get('workload')
        new_cycle_rate = data.get('cycle_rate')
        
        if not workload or new_cycle_rate is None:
            return jsonify({'success': False, 'error': 'Workload or cycle_rate not specified'}), 400
        
        result = benchmark_manager.update_cycle_rate(
            workload, new_cycle_rate, state_manager.get_database_config()
        )

        # Update state manager with new cycle rate, preserving runtime continuity
        if result.get('success'):
            # Get the fresh status from benchmark manager (which has correct runtime)
            fresh_status = benchmark_manager.get_running_benchmarks().get(workload, {})
            if fresh_status:
                # Update the cycle rate in the fresh status and save to state manager
                fresh_status['cycle_rate'] = new_cycle_rate
                state_manager.update_running_benchmark(workload, fresh_status)
                logger.info(f"Updated cycle rate for {workload} to {new_cycle_rate}, runtime preserved: {fresh_status.get('runtime_seconds', 0):.1f}s")

                # Immediately broadcast status update for real-time feel
                try:
                    with app.app_context():
                        status_response = get_status()
                        if isinstance(status_response, tuple):
                            response_data = status_response[0].get_json()
                        else:
                            response_data = status_response.get_json()
                        socketio.emit('status_update', response_data)
                except Exception as e:
                    logger.error(f"Failed to broadcast status update: {e}")

        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to update cycle rate: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get overall application status"""
    try:
        # Get running benchmarks from both sources and merge
        bm_running_benchmarks = benchmark_manager.get_running_benchmarks()
        state_running_benchmarks = state_manager.get_running_benchmarks()

        # Update state manager with current benchmark status
        for workload, status in bm_running_benchmarks.items():
            if status.get('status') == 'running':
                state_manager.update_running_benchmark(workload, status)
            elif status.get('status') == 'terminated':
                state_manager.update_running_benchmark(workload, None)

        # Clean up any stale benchmarks in state
        state_manager.cleanup_terminated_benchmarks()

        # Get setup status from both sources and merge
        bm_setup_status = benchmark_manager.get_setup_status()
        state_setup_status = state_manager.get_setup_status()

        # Merge setup status (benchmark manager is authoritative)
        for workload, phases in bm_setup_status.items():
            if all(phases.values()):
                state_manager.update_setup_status(workload, True)

        return jsonify({
            'infrastructure_ready': state_manager.is_infrastructure_ready(),
            'databases_configured': state_manager.is_databases_configured(),
            'setup_status': state_manager.get_setup_status(),
            'running_benchmarks': state_manager.get_running_benchmarks(),
            'database_config': state_manager.get_database_config()
        })

    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/cleanup', methods=['POST'])
def cleanup_all():
    """Stop all benchmarks and clear state"""
    try:
        logger.info("Manual cleanup requested")
        graceful_shutdown()
        return jsonify({'success': True, 'message': 'Cleanup completed'})
    except Exception as e:
        logger.error(f"Failed to cleanup: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@socketio.on('connect')
def handle_connect(auth=None):
    """Handle client connection"""
    logger.info('Client connected')
    try:
        with app.app_context():
            status_response = get_status()
            # Handle both successful response and error tuple
            if isinstance(status_response, tuple):
                # Error case - status_response is (response, status_code)
                response_data = status_response[0].get_json()
            else:
                # Success case - status_response is a Response object
                response_data = status_response.get_json()

            emit('status_update', response_data)
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        emit('status_update', {'error': 'Failed to get status'})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info('Client disconnected')

def status_broadcast_thread():
    """Background thread to broadcast status updates"""
    while True:
        try:
            with app.app_context():
                status_response = get_status()
                # Handle both successful response and error tuple
                if isinstance(status_response, tuple):
                    # Error case - status_response is (response, status_code)
                    response_data = status_response[0].get_json()
                else:
                    # Success case - status_response is a Response object
                    response_data = status_response.get_json()

                socketio.emit('status_update', response_data)
            time.sleep(2)  # Update every 2 seconds for better real-time feel
        except Exception as e:
            logger.error(f"Error in status broadcast: {e}")
            time.sleep(5)  # Shorter retry interval

if __name__ == '__main__':
    # Start status broadcast thread
    threading.Thread(target=status_broadcast_thread, daemon=True).start()

    try:
        # Run the application
        socketio.run(app, host='0.0.0.0', port=5000, debug=config.debug)
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        graceful_shutdown()
    except Exception as e:
        logger.error(f"Application error: {e}")
        graceful_shutdown()
        raise
