import subprocess
import threading
import time
import logging
import psutil
import signal
import os
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class BenchmarkProcess:
    """Represents a running benchmark process"""
    workload_name: str
    phase: str
    process: subprocess.Popen
    cycle_rate: int
    start_time: float
    pid: int
    test_id: str
    stdout_file: Any = None
    stderr_file: Any = None
    original_start_time: float = None  # Track original start time for runtime continuity

class BenchmarkManager:
    """Manages NoSQLBench processes for different workloads"""

    def __init__(self, config_obj, state_manager=None):
        self.config = config_obj
        self.running_processes: Dict[str, BenchmarkProcess] = {}
        self.setup_status: Dict[str, Dict[str, bool]] = {}
        self.lock = threading.Lock()
        self.state_manager = state_manager

        # Ensure logs directory exists (relative to project root)
        logs_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
        os.makedirs(logs_path, exist_ok=True)
        self.logs_path = logs_path

        # Ensure results directory exists (relative to project root)
        results_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'results')
        os.makedirs(results_path, exist_ok=True)
        self.results_path = results_path

    def is_database_configured(self, driver: str, database_config: Dict[str, Any]) -> bool:
        """Check if a database is properly configured"""
        if driver == "cql":
            return (database_config.get("cassandra_host") is not None and
                   database_config.get("cassandra_host").strip() != "")
        elif driver == "opensearch":
            return (database_config.get("opensearch_host") is not None and
                   database_config.get("opensearch_host").strip() != "")
        elif driver == "jdbc":
            return (database_config.get("presto_host") is not None and
                   database_config.get("presto_host").strip() != "")
        return False

    def get_available_workloads(self, database_config: Dict[str, Any]) -> List[str]:
        """Get list of workloads that can be run based on configured databases"""
        available_workloads = []

        for workload_name, workload_config in self.config.workload_configs.items():
            driver = workload_config["driver"]
            if self.is_database_configured(driver, database_config):
                available_workloads.append(workload_name)

        return available_workloads
    
    def get_workload_command_args(self, workload_name: str, phase: str, cycle_rate: int = None,
                                 database_config: Dict[str, Any] = None, test_id: str = None) -> List[str]:
        """Build NoSQLBench command arguments for a specific workload and phase"""
        workload_config = self.config.workload_configs.get(workload_name)
        if not workload_config:
            raise ValueError(f"Unknown workload: {workload_name}")

        # Generate test ID if not provided
        if test_id is None:
            test_id = f"{workload_name}_{phase}_{uuid.uuid4().hex[:8]}"

        # Use Docker if configured
        if self.config.benchmark.use_docker:
            return self._build_docker_command(workload_name, phase, cycle_rate, database_config, test_id)
        else:
            return self._build_local_command(workload_name, phase, cycle_rate, database_config, test_id)

    def _build_local_command(self, workload_name: str, phase: str, cycle_rate: int = None,
                            database_config: Dict[str, Any] = None, test_id: str = None) -> List[str]:
        """Build local NoSQLBench command arguments"""
        workload_config = self.config.workload_configs.get(workload_name)

        cmd = [self.config.benchmark.nosqlbench_command]
        cmd.append(workload_config["file"])
        cmd.append(phase)

        return self._add_common_args(cmd, workload_config, cycle_rate, database_config, test_id)

    def _build_docker_command(self, workload_name: str, phase: str, cycle_rate: int = None,
                             database_config: Dict[str, Any] = None, test_id: str = None) -> List[str]:
        """Build Docker command for NoSQLBench"""
        workload_config = self.config.workload_configs.get(workload_name)

        # Create log directory for this specific run
        log_dir = os.path.join(self.logs_path, f"{workload_name}_{phase}_{test_id}")
        os.makedirs(log_dir, exist_ok=True)

        # Build Docker command
        cmd = [
            "docker", "run", "--rm",
            "--name", f"nosqlbench-{workload_name}-{test_id}",
            "--network", self.config.benchmark.docker_network,
            "-v", f"{os.path.abspath(self.config.workloads_path)}:/workloads",
            "-v", f"{os.path.abspath(self.results_path)}:/results",
            "-v", f"{os.path.abspath(log_dir)}:/logs",
            self.config.benchmark.docker_image,
            "--include=/workloads", workload_config['file'], phase
        ]

        return self._add_common_args(cmd, workload_config, cycle_rate, database_config, test_id, is_docker=True)

    def _add_common_args(self, cmd: List[str], workload_config: dict, cycle_rate: int = None,
                        database_config: Dict[str, Any] = None, test_id: str = None, is_docker: bool = False) -> List[str]:
        """Add common arguments to NoSQLBench command"""
        # Add driver-specific arguments
        driver = workload_config["driver"]

        if driver == "cql":
            # Cassandra/CQL arguments
            host = database_config.get("cassandra_host", "127.0.0.1")
            port = database_config.get("cassandra_port", 9042)
            keyspace = workload_config.get("keyspace", "test")

            cmd.extend([
                f"driver={driver}",
                f"host={host}",
                f"port={port}",
                f"keyspace={keyspace}",
                "localdc=datacenter1"
            ])

        elif driver == "opensearch":
            # OpenSearch arguments
            host = database_config.get("opensearch_host", "127.0.0.1")
            port = database_config.get("opensearch_port", 9200)

            cmd.extend([
                f"driver={driver}",
                f"host={host}",
                f"port={port}"
            ])

        elif driver == "jdbc":
            # JDBC/Presto arguments
            host = database_config.get("presto_host", "127.0.0.1")
            port = database_config.get("presto_port", 8080)
            user = database_config.get("presto_user", "testuser")

            dburl = f"jdbc:presto://{host}:{port}/memory?user={user}"
            cmd.extend([
                f"dburl={dburl}",
                "use_hikaricp=true"
            ])

        # Add common arguments
        if cycle_rate:
            cmd.append(f"cyclerate={cycle_rate}")

        # Add threads configuration
        if self.config.benchmark.threads_auto:
            cmd.append("threads=auto")

        # Add errors mode
        cmd.append(f"errors={self.config.benchmark.errors_mode}")

        # Add VictoriaMetrics reporting with new pattern
        vm_endpoint = self.config.infrastructure.victoriametrics_endpoint
        metrics_endpoint = f"{vm_endpoint}/api/v1/import/prometheus/metrics/job/nosqlbench/instance/{test_id}"
        cmd.append(f"--report-prompush-to={metrics_endpoint}")

        # Determine db_type based on driver
        db_type = "unknown"
        if driver == "cql":
            db_type = "cassandra"
        elif driver == "opensearch":
            db_type = "opensearch"
        elif driver == "jdbc":
            db_type = "presto"

        # Add labels and reporting interval
        cmd.append(f"--add-labels=job:nosqlbench,instance:{test_id},db_type:{db_type}")
        cmd.append("--report-interval=10")

        # Add logs directory - different for Docker vs local
        if is_docker:
            cmd.append("--logs-dir=/logs")
        else:
            log_dir = os.path.join(self.logs_path, f"{workload_config.get('name', 'unknown')}_{test_id}")
            os.makedirs(log_dir, exist_ok=True)
            cmd.append(f"--logs-dir={log_dir}")

        return cmd
    
    def run_setup_phase(self, workload_name: str, database_config: Dict[str, Any], auto_start_benchmark: bool = True) -> Dict[str, Any]:
        """Run setup phases for a workload"""
        workload_config = self.config.workload_configs.get(workload_name)
        if not workload_config:
            return {"success": False, "error": f"Unknown workload: {workload_name}"}

        # Check if the required database is configured
        driver = workload_config["driver"]
        if not self.is_database_configured(driver, database_config):
            db_name = {"cql": "Cassandra", "opensearch": "OpenSearch", "jdbc": "Presto"}.get(driver, driver)
            return {"success": False, "error": f"{db_name} database is not configured for workload {workload_name}"}

        setup_phases = workload_config["setup_phases"]
        results = []

        # Initialize setup status for this workload
        if workload_name not in self.setup_status:
            self.setup_status[workload_name] = {}

        for phase in setup_phases:
            logger.info(f"Running setup phase {phase} for {workload_name}")

            try:
                # Generate unique test ID for this setup phase
                test_id = f"{workload_name}_{phase}_setup_{uuid.uuid4().hex[:8]}"
                cmd = self.get_workload_command_args(workload_name, phase, database_config=database_config, test_id=test_id)

                logger.info(f"Executing command: {' '.join(cmd)}")

                # Create log directory for this specific command
                log_dir = os.path.join(self.logs_path, f"{workload_name}_{phase}_{test_id}")
                os.makedirs(log_dir, exist_ok=True)

                # Capture output to files
                stdout_file = os.path.join(log_dir, "stdout.log")
                stderr_file = os.path.join(log_dir, "stderr.log")

                with open(stdout_file, 'w') as stdout_f, open(stderr_file, 'w') as stderr_f:
                    # Run setup phase synchronously
                    result = subprocess.run(
                        cmd,
                        stdout=stdout_f,
                        stderr=stderr_f,
                        text=True,
                        timeout=600  # 10 minute timeout for setup phases
                    )

                success = result.returncode == 0
                self.setup_status[workload_name][phase] = success

                results.append({
                    "phase": phase,
                    "success": success,
                    "stdout": "",  # Output is captured in files
                    "stderr": "",  # Output is captured in files
                    "return_code": result.returncode
                })

                if not success:
                    logger.error(f"Setup phase {phase} failed for {workload_name}")
                    break

            except subprocess.TimeoutExpired:
                logger.error(f"Setup phase {phase} timed out for {workload_name}")
                results.append({
                    "phase": phase,
                    "success": False,
                    "error": "Timeout"
                })
                break
            except Exception as e:
                logger.error(f"Error running setup phase {phase} for {workload_name}: {e}")
                results.append({
                    "phase": phase,
                    "success": False,
                    "error": str(e)
                })
                break

        all_success = all(result.get("success", False) for result in results)

        # Auto-start benchmark if setup completed successfully and auto_start_benchmark is True
        benchmark_started = False
        if all_success and auto_start_benchmark:
            logger.info(f"Setup completed successfully for {workload_name}, auto-starting benchmark")
            benchmark_result = self.start_benchmark(
                workload_name,
                self.config.benchmark.default_cycle_rate,
                database_config
            )
            benchmark_started = benchmark_result.get("success", False)
            if benchmark_started:
                logger.info(f"Auto-started benchmark for {workload_name} with cycle rate {self.config.benchmark.default_cycle_rate}")
            else:
                logger.warning(f"Failed to auto-start benchmark for {workload_name}: {benchmark_result.get('error', 'Unknown error')}")

        return {
            "success": all_success,
            "workload": workload_name,
            "results": results,
            "benchmark_started": benchmark_started
        }
    
    def start_benchmark(self, workload_name: str, cycle_rate: int,
                       database_config: Dict[str, Any], original_start_time: float = None) -> Dict[str, Any]:
        """Start a long-running benchmark"""
        with self.lock:
            # Check if benchmark is already running
            if workload_name in self.running_processes:
                return {
                    "success": False,
                    "error": f"Benchmark {workload_name} is already running"
                }
            
            # Check if setup was completed
            if (workload_name not in self.setup_status or 
                not all(self.setup_status[workload_name].values())):
                return {
                    "success": False,
                    "error": f"Setup not completed for {workload_name}"
                }
            
            workload_config = self.config.workload_configs.get(workload_name)
            if not workload_config:
                return {"success": False, "error": f"Unknown workload: {workload_name}"}

            # Check if the required database is configured
            driver = workload_config["driver"]
            if not self.is_database_configured(driver, database_config):
                db_name = {"cql": "Cassandra", "opensearch": "OpenSearch", "jdbc": "Presto"}.get(driver, driver)
                return {"success": False, "error": f"{db_name} database is not configured for workload {workload_name}"}
            
            try:
                run_phase = workload_config["run_phase"]
                # Generate unique test ID for this benchmark run
                test_id = f"{workload_name}_{run_phase}_run_{uuid.uuid4().hex[:8]}"
                cmd = self.get_workload_command_args(
                    workload_name, run_phase, cycle_rate, database_config, test_id
                )
                

                
                logger.info(f"Starting benchmark {workload_name} with command: {' '.join(cmd)}")

                # Create log directory for this specific benchmark run
                log_dir = f"logs/{workload_name}_{run_phase}_{test_id}"
                os.makedirs(log_dir, exist_ok=True)

                # Open log files for capturing output
                stdout_file = os.path.join(log_dir, "stdout.log")
                stderr_file = os.path.join(log_dir, "stderr.log")

                stdout_f = open(stdout_file, 'w')
                stderr_f = open(stderr_file, 'w')

                # Start process
                process = subprocess.Popen(
                    cmd,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    text=True,
                    preexec_fn=os.setsid  # Create new process group
                )
                
                # Store process info
                current_time = time.time()
                benchmark_process = BenchmarkProcess(
                    workload_name=workload_name,
                    phase=run_phase,
                    process=process,
                    cycle_rate=cycle_rate,
                    start_time=current_time,
                    pid=process.pid,
                    test_id=test_id,
                    stdout_file=stdout_f,
                    stderr_file=stderr_f,
                    original_start_time=original_start_time or current_time
                )
                
                self.running_processes[workload_name] = benchmark_process
                
                return {
                    "success": True,
                    "workload": workload_name,
                    "pid": process.pid,
                    "cycle_rate": cycle_rate
                }
                
            except Exception as e:
                logger.error(f"Failed to start benchmark {workload_name}: {e}")
                return {"success": False, "error": str(e)}
    
    def stop_benchmark(self, workload_name: str) -> Dict[str, Any]:
        """Stop a running benchmark"""
        with self.lock:
            if workload_name not in self.running_processes:
                return {
                    "success": False,
                    "error": f"Benchmark {workload_name} is not running"
                }
            
            benchmark_process = self.running_processes[workload_name]
            
            try:
                # Terminate the process group
                os.killpg(os.getpgid(benchmark_process.pid), signal.SIGTERM)

                # Wait for process to terminate
                benchmark_process.process.wait(timeout=10)

                # Close log files
                if benchmark_process.stdout_file:
                    benchmark_process.stdout_file.close()
                if benchmark_process.stderr_file:
                    benchmark_process.stderr_file.close()

                # Remove from running processes
                del self.running_processes[workload_name]

                # Use original start time for final runtime calculation
                runtime = time.time() - benchmark_process.original_start_time
                
                return {
                    "success": True,
                    "workload": workload_name,
                    "runtime_seconds": runtime
                }
                
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination failed
                try:
                    os.killpg(os.getpgid(benchmark_process.pid), signal.SIGKILL)

                    # Close log files
                    if benchmark_process.stdout_file:
                        benchmark_process.stdout_file.close()
                    if benchmark_process.stderr_file:
                        benchmark_process.stderr_file.close()

                    del self.running_processes[workload_name]
                    return {
                        "success": True,
                        "workload": workload_name,
                        "note": "Force killed"
                    }
                except Exception as e:
                    return {"success": False, "error": f"Failed to kill process: {e}"}
            except Exception as e:
                logger.error(f"Error stopping benchmark {workload_name}: {e}")
                return {"success": False, "error": str(e)}
    
    def update_cycle_rate(self, workload_name: str, new_cycle_rate: int,
                         database_config: Dict[str, Any]) -> Dict[str, Any]:
        """Update cycle rate by restarting the benchmark"""
        # Capture original start time and current runtime before stopping
        original_start_time = None
        current_runtime = 0
        with self.lock:
            if workload_name in self.running_processes:
                benchmark_process = self.running_processes[workload_name]
                original_start_time = benchmark_process.original_start_time
                current_runtime = time.time() - benchmark_process.original_start_time
                logger.info(f"Updating cycle rate for {workload_name}: preserving original_start_time={original_start_time}, current_runtime={current_runtime:.1f}s")

        # Stop current benchmark
        stop_result = self.stop_benchmark(workload_name)
        if not stop_result["success"]:
            return stop_result

        # Start with new cycle rate, preserving original start time
        time.sleep(1)  # Brief pause
        start_result = self.start_benchmark(workload_name, new_cycle_rate, database_config, original_start_time)

        if start_result.get("success"):
            logger.info(f"Successfully restarted {workload_name} with new cycle rate {new_cycle_rate}, runtime continuity preserved")

        return start_result
    
    def get_running_benchmarks(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all running benchmarks"""
        with self.lock:
            status = {}
            terminated_workloads = []

            # Create a copy of items to avoid "dictionary changed size during iteration"
            for workload_name, benchmark_process in list(self.running_processes.items()):
                # Check if process is still running
                if benchmark_process.process.poll() is None:
                    # Use original start time for runtime calculation to maintain continuity across restarts
                    runtime = time.time() - benchmark_process.original_start_time
                    status[workload_name] = {
                        "status": "running",
                        "pid": benchmark_process.pid,
                        "cycle_rate": benchmark_process.cycle_rate,
                        "runtime_seconds": runtime,
                        "phase": benchmark_process.phase,
                        "start_time": benchmark_process.original_start_time  # Add start time for frontend
                    }
                    # Debug logging for runtime tracking (can be removed later)
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(f"Runtime for {workload_name}: {runtime:.1f}s (original_start: {benchmark_process.original_start_time}, current_start: {benchmark_process.start_time})")
                else:
                    # Process has terminated
                    status[workload_name] = {
                        "status": "terminated",
                        "return_code": benchmark_process.process.returncode
                    }
                    # Close log files and mark for cleanup
                    if benchmark_process.stdout_file:
                        benchmark_process.stdout_file.close()
                    if benchmark_process.stderr_file:
                        benchmark_process.stderr_file.close()
                    terminated_workloads.append(workload_name)

            # Clean up terminated processes after iteration
            for workload_name in terminated_workloads:
                del self.running_processes[workload_name]

            return status
    
    def get_setup_status(self) -> Dict[str, Dict[str, bool]]:
        """Get setup status for all workloads"""
        with self.lock:
            return self.setup_status.copy()

    def get_workloads_ready_for_benchmark(self, database_config: Dict[str, Any]) -> List[str]:
        """Get list of workloads that have completed setup and are ready for benchmarking"""
        ready_workloads = []

        with self.lock:
            for workload_name, phases_status in self.setup_status.items():
                # Check if all setup phases are completed
                if all(phases_status.values()):
                    # Check if the required database is still configured
                    workload_config = self.config.workload_configs.get(workload_name)
                    if workload_config:
                        driver = workload_config["driver"]
                        if self.is_database_configured(driver, database_config):
                            ready_workloads.append(workload_name)

        return ready_workloads

    def is_workload_ready_for_benchmark(self, workload_name: str, database_config: Dict[str, Any]) -> bool:
        """Check if a specific workload is ready for benchmarking"""
        return workload_name in self.get_workloads_ready_for_benchmark(database_config)
    
    def cleanup_all(self) -> Dict[str, Any]:
        """Stop all running benchmarks"""
        stopped = []
        errors = []

        for workload_name in list(self.running_processes.keys()):
            result = self.stop_benchmark(workload_name)
            if result["success"]:
                stopped.append(workload_name)
            else:
                errors.append(f"{workload_name}: {result.get('error', 'Unknown error')}")

        return {"stopped": stopped, "errors": errors}

    def force_cleanup_all(self) -> Dict[str, Any]:
        """Forcefully stop all running benchmarks (for shutdown)"""
        stopped = []
        errors = []

        with self.lock:
            for workload_name, benchmark_process in list(self.running_processes.items()):
                try:
                    # Force kill the process group
                    os.killpg(os.getpgid(benchmark_process.pid), signal.SIGKILL)

                    # Close log files
                    if benchmark_process.stdout_file:
                        benchmark_process.stdout_file.close()
                    if benchmark_process.stderr_file:
                        benchmark_process.stderr_file.close()

                    stopped.append(workload_name)
                    logger.info(f"Force killed benchmark: {workload_name} (PID: {benchmark_process.pid})")

                except Exception as e:
                    errors.append(f"{workload_name}: {str(e)}")
                    logger.error(f"Failed to force kill {workload_name}: {e}")

            # Clear all running processes
            self.running_processes.clear()

        return {"stopped": stopped, "errors": errors}
