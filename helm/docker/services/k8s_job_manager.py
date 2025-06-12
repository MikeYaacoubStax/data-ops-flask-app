"""
Kubernetes Job Manager for NoSQLBench workloads
Manages NoSQLBench setup and benchmark jobs in Kubernetes
"""

import os
import re
import socket
import time
import logging
import threading
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

class KubernetesJobManager:
    """Manages NoSQLBench jobs in Kubernetes"""
    
    def __init__(self, config_manager, state_manager):
        self.config_manager = config_manager
        self.state_manager = state_manager
        self.lock = threading.Lock()
        
        # Initialize Kubernetes client
        try:
            # Load in-cluster config when running in pod
            config.load_incluster_config()
            logger.info("Loaded in-cluster Kubernetes configuration")
        except Exception:
            try:
                # Fallback to local config for development
                config.load_kube_config()
                logger.info("Loaded local Kubernetes configuration")
            except Exception as e:
                logger.error(f"Failed to load Kubernetes configuration: {e}")
                raise
        
        self.batch_v1 = client.BatchV1Api()
        self.core_v1 = client.CoreV1Api()
        
        # Get namespace and release info from environment
        self.namespace = os.getenv('KUBERNETES_NAMESPACE', 'default')
        self.release_name = os.getenv('RELEASE_NAME', 'nosqlbench-demo')
        self.nosqlbench_image = os.getenv('NOSQLBENCH_IMAGE', 'nosqlbench/nosqlbench:5.21.8-preview')
        
        logger.info(f"Initialized KubernetesJobManager for namespace: {self.namespace}")

    def _sanitize_label_value(self, value: str) -> str:
        """Sanitize a string for use in Prometheus labels"""
        if not value:
            return "unknown"

        # Replace spaces and special characters with underscores
        # Prometheus label values can contain letters, numbers, underscores, and hyphens
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', str(value))

        # Remove multiple consecutive underscores
        sanitized = re.sub(r'_+', '_', sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip('_')

        # Ensure it's not empty
        if not sanitized:
            return "unknown"

        return sanitized

    def list_jobs(self, label_selector: str = None) -> List[Any]:
        """List jobs in the namespace"""
        try:
            if label_selector:
                response = self.batch_v1.list_namespaced_job(
                    namespace=self.namespace,
                    label_selector=label_selector
                )
            else:
                response = self.batch_v1.list_namespaced_job(namespace=self.namespace)
            return response.items
        except ApiException as e:
            logger.error(f"Failed to list jobs: {e}")
            return []
    
    def get_job_status(self, job_name: str) -> Dict[str, Any]:
        """Get status of a specific job"""
        try:
            job = self.batch_v1.read_namespaced_job(name=job_name, namespace=self.namespace)
            
            status = {
                "name": job.metadata.name,
                "active": job.status.active or 0,
                "succeeded": job.status.succeeded or 0,
                "failed": job.status.failed or 0,
                "start_time": job.status.start_time,
                "completion_time": job.status.completion_time,
                "conditions": []
            }
            
            if job.status.conditions:
                for condition in job.status.conditions:
                    status["conditions"].append({
                        "type": condition.type,
                        "status": condition.status,
                        "reason": condition.reason,
                        "message": condition.message,
                        "last_transition_time": condition.last_transition_time
                    })
            
            return status
            
        except ApiException as e:
            if e.status == 404:
                return {"name": job_name, "status": "not_found"}
            logger.error(f"Failed to get job status for {job_name}: {e}")
            return {"name": job_name, "status": "error", "error": str(e)}
    
    def create_setup_job(self, workload_name: str, phase: str) -> Dict[str, Any]:
        """Create a setup job for a workload phase"""
        try:
            # Convert names to be Kubernetes-compliant (lowercase, no underscores)
            safe_workload = workload_name.replace("_", "-").lower()
            safe_phase = phase.replace(".", "-").replace("_", "-").lower()
            job_name = f"{self.release_name}-setup-{safe_workload}-{safe_phase}-{uuid.uuid4().hex[:8]}"
            
            # Get workload configuration
            workload_config = self.config_manager.get_workload_config(workload_name)
            if not workload_config:
                return {"success": False, "error": f"Unknown workload: {workload_name}"}
            
            # Build job spec
            job_spec = self._build_job_spec(
                job_name=job_name,
                workload_name=workload_name,
                workload_config=workload_config,
                phase=phase,
                job_type="setup"
            )
            
            # Create the job
            job = self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job_spec
            )
            
            logger.info(f"Created setup job: {job_name} for {workload_name}.{phase}")
            
            return {
                "success": True,
                "job_name": job_name,
                "workload": workload_name,
                "phase": phase
            }
            
        except ApiException as e:
            logger.error(f"Failed to create setup job for {workload_name}.{phase}: {e}")
            return {"success": False, "error": str(e)}
    
    def create_benchmark_job(self, workload_name: str, cycle_rate: int) -> Dict[str, Any]:
        """Create a benchmark job for a workload"""
        try:
            # Convert names to be Kubernetes-compliant (lowercase, no underscores)
            safe_workload = workload_name.replace("_", "-").lower()
            job_name = f"{self.release_name}-benchmark-{safe_workload}-{uuid.uuid4().hex[:8]}"
            
            # Get workload configuration
            workload_config = self.config_manager.get_workload_config(workload_name)
            if not workload_config:
                return {"success": False, "error": f"Unknown workload: {workload_name}"}
            
            # Build job spec
            job_spec = self._build_job_spec(
                job_name=job_name,
                workload_name=workload_name,
                workload_config=workload_config,
                phase=workload_config['run_phase'],
                job_type="benchmark",
                cycle_rate=cycle_rate
            )
            
            # Create the job
            job = self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job_spec
            )
            
            logger.info(f"Created benchmark job: {job_name} for {workload_name} with cycle rate {cycle_rate}")
            
            return {
                "success": True,
                "job_name": job_name,
                "workload": workload_name,
                "cycle_rate": cycle_rate,
                "start_time": time.time()
            }
            
        except ApiException as e:
            logger.error(f"Failed to create benchmark job for {workload_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def delete_job(self, job_name: str) -> Dict[str, Any]:
        """Delete a job"""
        try:
            # Delete the job
            self.batch_v1.delete_namespaced_job(
                name=job_name,
                namespace=self.namespace,
                propagation_policy='Background'
            )
            
            logger.info(f"Deleted job: {job_name}")
            return {"success": True, "job_name": job_name}
            
        except ApiException as e:
            if e.status == 404:
                return {"success": True, "job_name": job_name, "message": "Job not found"}
            logger.error(f"Failed to delete job {job_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def run_setup_phases(self, workload_name: str) -> Dict[str, Any]:
        """Run all setup phases for a workload sequentially"""
        try:
            workload_config = self.config_manager.get_workload_config(workload_name)
            if not workload_config:
                return {"success": False, "error": f"Unknown workload: {workload_name}"}
            
            setup_phases = workload_config.get('setup_phases', [])
            if not setup_phases:
                return {"success": False, "error": f"No setup phases defined for {workload_name}"}
            
            results = []
            
            for phase in setup_phases:
                logger.info(f"Running setup phase {phase} for {workload_name}")
                
                # Create setup job
                result = self.create_setup_job(workload_name, phase)
                if not result.get("success"):
                    results.append(result)
                    break
                
                job_name = result["job_name"]
                
                # Wait for job completion
                success = self._wait_for_job_completion(job_name, timeout=600)  # 10 minutes timeout
                
                result["completed"] = success
                results.append(result)
                
                if not success:
                    logger.error(f"Setup phase {phase} failed for {workload_name}")
                    break
                
                logger.info(f"Setup phase {phase} completed successfully for {workload_name}")
            
            # Update setup status
            all_success = all(r.get("completed", False) for r in results)
            self.state_manager.update_setup_status(workload_name, all_success)
            
            return {
                "success": all_success,
                "workload": workload_name,
                "phases": results
            }
            
        except Exception as e:
            logger.error(f"Failed to run setup phases for {workload_name}: {e}")
            return {"success": False, "error": str(e)}

    def start_benchmark(self, workload_name: str, cycle_rate: int) -> Dict[str, Any]:
        """Start a benchmark job"""
        with self.lock:
            # Check if benchmark is already running
            running_jobs = self.get_running_benchmark_jobs()
            for job in running_jobs:
                if job.get("workload") == workload_name:
                    return {
                        "success": False,
                        "error": f"Benchmark for {workload_name} is already running"
                    }

            # Check if setup was completed
            if not self.state_manager.is_setup_completed(workload_name):
                return {
                    "success": False,
                    "error": f"Setup not completed for {workload_name}"
                }

            # Create benchmark job
            result = self.create_benchmark_job(workload_name, cycle_rate)

            if result.get("success"):
                # Track the running benchmark
                self.state_manager.add_running_benchmark(
                    workload_name,
                    result["job_name"],
                    cycle_rate,
                    result["start_time"]
                )

            return result

    def stop_benchmark(self, workload_name: str) -> Dict[str, Any]:
        """Stop a running benchmark"""
        with self.lock:
            # Find running benchmark job
            running_benchmarks = self.state_manager.get_running_benchmarks()
            if workload_name not in running_benchmarks:
                return {
                    "success": False,
                    "error": f"No running benchmark found for {workload_name}"
                }

            job_name = running_benchmarks[workload_name]["job_name"]

            # Delete the job
            result = self.delete_job(job_name)

            if result.get("success"):
                # Remove from running benchmarks
                self.state_manager.remove_running_benchmark(workload_name)
                logger.info(f"Stopped benchmark for {workload_name}")

            return result

    def update_benchmark_throughput(self, workload_name: str, new_cycle_rate: int) -> Dict[str, Any]:
        """Update benchmark throughput by recreating the job"""
        with self.lock:
            # Stop current benchmark
            stop_result = self.stop_benchmark(workload_name)
            if not stop_result.get("success"):
                return stop_result

            # Wait a moment for cleanup
            time.sleep(2)

            # Start with new cycle rate
            start_result = self.start_benchmark(workload_name, new_cycle_rate)

            if start_result.get("success"):
                logger.info(f"Updated throughput for {workload_name} to {new_cycle_rate}")

            return start_result

    def get_setup_status(self) -> Dict[str, bool]:
        """Get setup status for all workloads"""
        return self.state_manager.get_setup_status()

    def get_workloads_ready_for_benchmark(self) -> List[str]:
        """Get list of workloads ready for benchmarking"""
        ready_workloads = []
        available_workloads = self.config_manager.get_available_workloads()

        for workload in available_workloads:
            if self.state_manager.is_setup_completed(workload):
                ready_workloads.append(workload)

        return ready_workloads

    def get_running_benchmarks(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all running benchmarks"""
        with self.lock:
            running_benchmarks = self.state_manager.get_running_benchmarks()

            # Update status from Kubernetes
            for workload, benchmark_info in list(running_benchmarks.items()):
                job_name = benchmark_info["job_name"]
                job_status = self.get_job_status(job_name)

                # Check if job is still running
                if (job_status.get("succeeded", 0) > 0 or
                    job_status.get("failed", 0) > 0 or
                    job_status.get("status") == "not_found"):
                    # Job completed or failed, remove from running
                    self.state_manager.remove_running_benchmark(workload)
                    logger.info(f"Benchmark job {job_name} for {workload} completed")
                else:
                    # Update with current job status
                    benchmark_info["job_status"] = job_status

            return self.state_manager.get_running_benchmarks()

    def get_running_benchmark_jobs(self) -> List[Dict[str, Any]]:
        """Get list of running benchmark jobs from Kubernetes"""
        try:
            jobs = self.list_jobs(label_selector=f"app.kubernetes.io/instance={self.release_name},job-type=benchmark")

            running_jobs = []
            for job in jobs:
                if job.status.active and job.status.active > 0:
                    # Extract workload name from job name
                    job_name = job.metadata.name
                    workload = self._extract_workload_from_job_name(job_name)

                    running_jobs.append({
                        "job_name": job_name,
                        "workload": workload,
                        "start_time": job.status.start_time
                    })

            return running_jobs

        except Exception as e:
            logger.error(f"Failed to get running benchmark jobs: {e}")
            return []

    def start_job(self, workload_name: str, scenario: str, database_id: str, cycle_rate: int = 10) -> Dict[str, Any]:
        """Start a job for a specific workload scenario and database"""
        try:
            # Get database configuration
            database_config = self.state_manager.get_database(database_id)
            if not database_config:
                return {"success": False, "error": f"Database {database_id} not found"}

            if not database_config.get("verified", False):
                return {"success": False, "error": f"Database {database_id} not verified"}

            # Get workload configuration
            workload_config = self.config_manager.get_workload_config(workload_name)
            if not workload_config:
                return {"success": False, "error": f"Unknown workload: {workload_name}"}

            # Generate job ID and name (shortened to fit Kubernetes 63-char limit)
            # Use abbreviated workload names to save space
            workload_abbrev = self._abbreviate_workload_name(workload_name)
            scenario_abbrev = scenario[:5]  # 'setup' or 'live'
            job_id = f"{workload_abbrev}-{scenario_abbrev}-{database_id[:6]}-{uuid.uuid4().hex[:6]}"
            safe_job_name = job_id.replace("_", "-").lower()
            job_name = f"{self.release_name}-{safe_job_name}"

            # Ensure job name fits in Kubernetes label limit (63 chars)
            if len(job_name) > 63:
                # Truncate release name if needed
                max_release_len = 63 - len(safe_job_name) - 1
                truncated_release = self.release_name[:max_release_len]
                job_name = f"{truncated_release}-{safe_job_name}"

            # Build job spec for scenario
            job_spec = self._build_scenario_job_spec(
                job_name=job_name,
                workload_name=workload_name,
                scenario=scenario,
                database_config=database_config,
                cycle_rate=cycle_rate
            )

            # Create the job
            job = self.batch_v1.create_namespaced_job(
                namespace=self.namespace,
                body=job_spec
            )

            # Track the running job
            job_info = {
                "workload": workload_name,
                "scenario": scenario,
                "database_id": database_id,
                "database_name": database_config.get("name"),
                "cycle_rate": cycle_rate,
                "job_name": job_name,
                "status": "running"
            }

            self.state_manager.add_running_job(job_id, job_info)

            logger.info(f"Started {scenario} job for {workload_name} on {database_config.get('name')}: {job_name}")

            return {
                "success": True,
                "job_id": job_id,
                "job_name": job_name,
                "workload": workload_name,
                "scenario": scenario,
                "database": database_config.get("name")
            }

        except Exception as e:
            logger.error(f"Failed to start job: {e}")
            return {"success": False, "error": str(e)}

    def stop_job(self, job_id: str) -> Dict[str, Any]:
        """Stop a running job"""
        try:
            # Get job info
            running_jobs = self.state_manager.get_running_jobs()
            if job_id not in running_jobs:
                return {"success": False, "error": f"Job {job_id} not found"}

            job_info = running_jobs[job_id]
            job_name = job_info.get("job_name")

            # Delete the Kubernetes job
            result = self.delete_job(job_name)

            if result.get("success"):
                # Remove from state
                self.state_manager.remove_running_job(job_id)
                logger.info(f"Stopped job {job_id}")

            return result

        except Exception as e:
            logger.error(f"Failed to stop job {job_id}: {e}")
            return {"success": False, "error": str(e)}

    def get_running_jobs(self) -> Dict[str, Any]:
        """Get all running jobs with updated status"""
        try:
            running_jobs = self.state_manager.get_running_jobs()

            # Update status from Kubernetes
            for job_id, job_info in list(running_jobs.items()):
                job_name = job_info.get("job_name")
                if job_name:
                    job_status = self.get_job_status(job_name)

                    # Check if job completed or failed
                    if (job_status.get("succeeded", 0) > 0 or
                        job_status.get("failed", 0) > 0 or
                        job_status.get("status") == "not_found"):
                        # Job completed, remove from running
                        self.state_manager.remove_running_job(job_id)
                        logger.info(f"Job {job_id} completed")
                    else:
                        # Update with current status
                        job_info["k8s_status"] = job_status

            return self.state_manager.get_running_jobs()

        except Exception as e:
            logger.error(f"Failed to get running jobs: {e}")
            return {}

    def test_database_connectivity(self, database_id: str) -> Dict[str, Any]:
        """Test connectivity to a database using direct socket connection"""
        try:
            logger.info(f"Starting connectivity test for database {database_id}")

            database_config = self.state_manager.get_database(database_id)
            if not database_config:
                logger.error(f"Database {database_id} not found")
                return {"success": False, "error": "Database not found"}

            # Get connection details
            host = database_config.get("host")
            port = database_config.get("port")
            db_type = database_config.get("type")

            logger.info(f"Testing connectivity to {db_type} at {host}:{port}")

            if not host or not port:
                logger.error(f"Missing host or port for database {database_id}: host={host}, port={port}")
                return {"success": False, "error": "Missing host or port in database configuration"}

            # Perform direct connectivity test with shorter timeout
            logger.info(f"Performing socket connectivity test...")
            success = self._test_socket_connectivity(host, port, timeout=5)
            logger.info(f"Socket connectivity test result: {success}")

            # Update database verification status
            logger.info(f"Updating database verification status to {success}")
            self.state_manager.update_database_verification(database_id, success)

            if success:
                logger.info(f"Database connectivity test passed for {database_id} ({db_type} at {host}:{port})")
                return {"success": True, "message": f"Database connectivity verified for {db_type} at {host}:{port}"}
            else:
                logger.warning(f"Database connectivity test failed for {database_id} ({db_type} at {host}:{port})")
                return {"success": False, "error": f"Cannot connect to {db_type} at {host}:{port}"}

        except Exception as e:
            logger.error(f"Failed to test database connectivity for {database_id}: {e}", exc_info=True)
            return {"success": False, "error": f"Connectivity test error: {str(e)}"}

    def cleanup(self):
        """Cleanup resources"""
        logger.info("Cleaning up KubernetesJobManager resources")
        # Could implement cleanup of old jobs here if needed

    def _build_job_spec(self, job_name: str, workload_name: str, workload_config: Dict[str, Any],
                       phase: str, job_type: str, cycle_rate: int = None) -> Dict[str, Any]:
        """Build Kubernetes Job specification"""

        # Get database configuration
        db_config = self.config_manager.get_database_config()

        # Build NoSQLBench command
        cmd = self._build_nosqlbench_command(workload_config, phase, cycle_rate, db_config)

        # Build environment variables
        env_vars = self._build_environment_variables(workload_config, db_config)

        # Job specification
        job_spec = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/name": "nosqlbench-demo",
                    "app.kubernetes.io/instance": self.release_name,
                    "app.kubernetes.io/component": "nosqlbench",
                    "job-type": job_type,
                    "workload": workload_name,
                    "phase": phase.replace(".", "-")
                }
            },
            "spec": {
                "ttlSecondsAfterFinished": 3600,  # Clean up after 1 hour
                "backoffLimit": 3,
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": "nosqlbench-demo",
                            "app.kubernetes.io/instance": self.release_name,
                            "app.kubernetes.io/component": "nosqlbench",
                            "job-type": job_type,
                            "workload": workload_name
                        }
                    },
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [{
                            "name": "nosqlbench",
                            "image": self.nosqlbench_image,
                            "args": cmd,
                            "env": env_vars,
                            "volumeMounts": [{
                                "name": "workloads",
                                "mountPath": "/workloads",
                                "readOnly": True
                            }],
                            "resources": self._get_nosqlbench_resources()
                        }],
                        "volumes": [{
                            "name": "workloads",
                            "configMap": {
                                "name": f"{self.release_name}-workloads"
                            }
                        }]
                    }
                }
            }
        }

        return job_spec

    def _build_scenario_job_spec(self, job_name: str, workload_name: str, scenario: str,
                                database_config: Dict[str, Any], cycle_rate: int) -> Dict[str, Any]:
        """Build Kubernetes Job specification for a scenario-based job"""

        # Build NoSQLBench command for scenario
        cmd = self._build_scenario_command(workload_name, scenario, database_config, cycle_rate)

        # Build environment variables for database connection
        env_vars = self._build_database_environment_variables(database_config)

        job_spec = {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": job_name,
                "namespace": self.namespace,
                "labels": {
                    "app.kubernetes.io/name": "nosqlbench-demo",
                    "app.kubernetes.io/instance": self.release_name,
                    "app.kubernetes.io/component": "nosqlbench",
                    "job-type": "benchmark",
                    "workload": self._abbreviate_workload_name(workload_name),
                    "scenario": scenario,
                    "database-id": database_config.get("id", "unknown")[:8]
                }
            },
            "spec": {
                "ttlSecondsAfterFinished": 3600,  # Clean up after 1 hour
                "backoffLimit": 3,
                "template": {
                    "metadata": {
                        "labels": {
                            "app.kubernetes.io/name": "nosqlbench-demo",
                            "app.kubernetes.io/instance": self.release_name,
                            "app.kubernetes.io/component": "nosqlbench",
                            "job-type": "benchmark",
                            "workload": self._abbreviate_workload_name(workload_name),
                            "scenario": scenario
                        }
                    },
                    "spec": {
                        "restartPolicy": "Never",
                        "containers": [{
                            "name": "nosqlbench",
                            "image": self.nosqlbench_image,
                            "args": cmd,
                            "env": env_vars,
                            "volumeMounts": [{
                                "name": "workloads",
                                "mountPath": "/workloads",
                                "readOnly": True
                            }],
                            "resources": self._get_nosqlbench_resources()
                        }],
                        "volumes": [{
                            "name": "workloads",
                            "configMap": {
                                "name": f"{self.release_name}-workloads"
                            }
                        }]
                    }
                }
            }
        }

        return job_spec

    def _build_scenario_command(self, workload_name: str, scenario: str,
                               database_config: Dict[str, Any], cycle_rate: int) -> List[str]:
        """Build NoSQLBench command for a specific scenario"""

        # Get workload file name
        workload_config = self.config_manager.get_workload_config(workload_name)
        workload_file = workload_config.get("file", f"{workload_name}.yaml")

        # Base command
        cmd = [
            f"/workloads/{workload_file}",
            scenario  # 'setup' or 'live'
        ]

        # Add database connection parameters based on type
        db_type = database_config.get("type")
        if db_type == "cassandra":
            cmd.extend([
                f"hosts={database_config.get('host')}",
                f"port={database_config.get('port', 9042)}",
                "localdc=datacenter1"
            ])
            if database_config.get("username"):
                cmd.extend([
                    f"username={database_config.get('username')}",
                    f"password={database_config.get('password')}"
                ])
        elif db_type == "opensearch":
            cmd.extend([
                f"host={database_config.get('host')}",
                f"port={database_config.get('port', 9200)}"
            ])
            if database_config.get("username"):
                cmd.extend([
                    f"username={database_config.get('username')}",
                    f"password={database_config.get('password')}"
                ])
        elif db_type == "presto":
            # Build JDBC URL for Presto
            host = database_config.get('host')
            port = database_config.get('port', 8080)
            # Handle empty username - use testuser as default
            raw_user = database_config.get('username')
            logger.info(f"Presto username from database_config: '{raw_user}' (type: {type(raw_user)})")
            user = raw_user or 'testuser'
            if not user or user.strip() == '':
                user = 'testuser'
            catalog = 'memory'
            dburl = f"jdbc:presto://{host}:{port}/{catalog}?user={user}"
            logger.info(f"Built Presto JDBC URL: {dburl}")
            cmd.extend([
                f"dburl={dburl}",
                "use_hikaricp=true"
            ])

        # Add cycle rate for live scenarios
        if scenario == "live" and cycle_rate:
            cmd.append(f"cyclerate={cycle_rate}")

        # Add common parameters
        cmd.extend([
            "threads=auto",
            "errors=count"
        ])

        # Add metrics reporting
        metrics_endpoint = self.config_manager.get_metrics_endpoint()
        test_id = f"{workload_name}_{scenario}_{database_config.get('id', 'unknown')[:8]}_{uuid.uuid4().hex[:8]}"
        metrics_url = f"{metrics_endpoint}/api/v1/import/prometheus/metrics/job/nosqlbench/instance/{test_id}"

        # Sanitize database name for Prometheus labels
        # Note: Don't include workload/scenario labels here as they conflict with workload YAML definitions
        sanitized_db_name = self._sanitize_label_value(database_config.get('name', 'unknown'))

        cmd.extend([
            f"--report-prompush-to={metrics_url}",
            f"--add-labels=job:nosqlbench,instance:{test_id},database:{sanitized_db_name}",
            "--report-interval=10"
        ])

        return cmd

    def _build_database_environment_variables(self, database_config: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build environment variables for database connection"""
        env_vars = []

        db_type = database_config.get("type")
        if db_type == "cassandra":
            env_vars.extend([
                {"name": "CASSANDRA_HOST", "value": database_config.get("host", "")},
                {"name": "CASSANDRA_PORT", "value": str(database_config.get("port", 9042))},
                {"name": "CASSANDRA_LOCALDC", "value": "datacenter1"}
            ])
            if database_config.get("username"):
                env_vars.extend([
                    {"name": "CASSANDRA_USERNAME", "value": database_config.get("username", "")},
                    {"name": "CASSANDRA_PASSWORD", "value": database_config.get("password", "")}
                ])
        elif db_type == "opensearch":
            env_vars.extend([
                {"name": "OPENSEARCH_HOST", "value": database_config.get("host", "")},
                {"name": "OPENSEARCH_PORT", "value": str(database_config.get("port", 9200))}
            ])
            if database_config.get("username"):
                env_vars.extend([
                    {"name": "OPENSEARCH_USERNAME", "value": database_config.get("username", "")},
                    {"name": "OPENSEARCH_PASSWORD", "value": database_config.get("password", "")}
                ])
        elif db_type == "presto":
            env_vars.extend([
                {"name": "PRESTO_HOST", "value": database_config.get("host", "")},
                {"name": "PRESTO_PORT", "value": str(database_config.get("port", 8080))},
                {"name": "PRESTO_USER", "value": "testuser"},
                {"name": "PRESTO_CATALOG", "value": "memory"}
            ])

        return env_vars



    def _build_nosqlbench_command(self, workload_config: Dict[str, Any], phase: str,
                                 cycle_rate: int = None, db_config: Dict[str, Any] = None) -> List[str]:
        """Build NoSQLBench command arguments"""

        cmd = [
            "--include=/workloads",
            workload_config["file"],
            phase
        ]

        # Add driver-specific arguments
        driver = workload_config["driver"]

        if driver == "cql":
            # Cassandra/CQL arguments
            cassandra_config = db_config.get("cassandra", {})
            host = cassandra_config.get("host", "127.0.0.1")
            port = cassandra_config.get("port", 9042)
            keyspace = workload_config.get("keyspace", "test")
            localdc = cassandra_config.get("localdc", "datacenter1")

            cmd.extend([
                f"driver={driver}",
                f"host={host}",
                f"port={port}",
                f"keyspace={keyspace}",
                f"localdc={localdc}"
            ])

        elif driver == "opensearch":
            # OpenSearch arguments
            opensearch_config = db_config.get("opensearch", {})
            host = opensearch_config.get("host", "127.0.0.1")
            port = opensearch_config.get("port", 9200)

            cmd.extend([
                f"driver={driver}",
                f"host={host}",
                f"port={port}"
            ])

        elif driver == "jdbc":
            # JDBC/Presto arguments
            presto_config = db_config.get("presto", {})
            host = presto_config.get("host", "127.0.0.1")
            port = presto_config.get("port", 8080)
            user = presto_config.get("user", "testuser")
            catalog = presto_config.get("catalog", "memory")

            dburl = f"jdbc:presto://{host}:{port}/{catalog}?user={user}"
            cmd.extend([
                f"dburl={dburl}",
                "use_hikaricp=true"
            ])

        # Add cycle rate for benchmark jobs
        if cycle_rate:
            cmd.append(f"cyclerate={cycle_rate}")

        # Add common arguments
        cmd.extend([
            "threads=auto",
            "errors=count"
        ])

        # Add metrics reporting only for benchmark jobs, not setup jobs
        if cycle_rate:  # This is a benchmark job
            metrics_endpoint = self.config_manager.get_metrics_endpoint()
            test_id = f"{workload_config['file']}_{phase}_{uuid.uuid4().hex[:8]}"
            metrics_url = f"{metrics_endpoint}/api/v1/import/prometheus/metrics/job/nosqlbench/instance/{test_id}"

            cmd.extend([
                f"--report-prompush-to={metrics_url}",
                f"--add-labels=job:nosqlbench,instance:{test_id},db_type:{driver}",
                "--report-interval=10"
            ])

        return cmd

    def _build_environment_variables(self, workload_config: Dict[str, Any],
                                   db_config: Dict[str, Any]) -> List[Dict[str, str]]:
        """Build environment variables for the job"""
        env_vars = []

        # Database-specific environment variables
        driver = workload_config["driver"]

        if driver == "cql" and db_config.get("cassandra", {}).get("enabled"):
            cassandra_config = db_config["cassandra"]
            env_vars.extend([
                {"name": "CASSANDRA_HOST", "value": str(cassandra_config.get("host", ""))},
                {"name": "CASSANDRA_PORT", "value": str(cassandra_config.get("port", 9042))},
                {"name": "CASSANDRA_LOCALDC", "value": str(cassandra_config.get("localdc", "datacenter1"))}
            ])

            if cassandra_config.get("username"):
                env_vars.append({"name": "CASSANDRA_USERNAME", "value": cassandra_config["username"]})
            if cassandra_config.get("password"):
                env_vars.append({"name": "CASSANDRA_PASSWORD", "value": cassandra_config["password"]})

        elif driver == "opensearch" and db_config.get("opensearch", {}).get("enabled"):
            opensearch_config = db_config["opensearch"]
            env_vars.extend([
                {"name": "OPENSEARCH_HOST", "value": str(opensearch_config.get("host", ""))},
                {"name": "OPENSEARCH_PORT", "value": str(opensearch_config.get("port", 9200))}
            ])

            if opensearch_config.get("username"):
                env_vars.append({"name": "OPENSEARCH_USERNAME", "value": opensearch_config["username"]})
            if opensearch_config.get("password"):
                env_vars.append({"name": "OPENSEARCH_PASSWORD", "value": opensearch_config["password"]})

        elif driver == "jdbc" and db_config.get("presto", {}).get("enabled"):
            presto_config = db_config["presto"]
            env_vars.extend([
                {"name": "PRESTO_HOST", "value": str(presto_config.get("host", ""))},
                {"name": "PRESTO_PORT", "value": str(presto_config.get("port", 8080))},
                {"name": "PRESTO_USER", "value": str(presto_config.get("user", "testuser"))},
                {"name": "PRESTO_CATALOG", "value": str(presto_config.get("catalog", "memory"))}
            ])

        # Metrics endpoint
        env_vars.append({
            "name": "METRICS_ENDPOINT",
            "value": self.config_manager.get_metrics_endpoint()
        })

        return env_vars

    def _wait_for_job_completion(self, job_name: str, timeout: int = 600) -> bool:
        """Wait for a job to complete"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                job_status = self.get_job_status(job_name)

                if job_status.get("succeeded", 0) > 0:
                    logger.info(f"Job {job_name} completed successfully")
                    return True
                elif job_status.get("failed", 0) > 0:
                    logger.error(f"Job {job_name} failed")
                    return False
                elif job_status.get("status") == "not_found":
                    logger.error(f"Job {job_name} not found")
                    return False

                # Job is still running, wait
                time.sleep(10)

            except Exception as e:
                logger.error(f"Error checking job status for {job_name}: {e}")
                time.sleep(10)

        logger.error(f"Job {job_name} timed out after {timeout} seconds")
        return False

    def _extract_workload_from_job_name(self, job_name: str) -> str:
        """Extract workload name from job name"""
        # Job name format: {release_name}-{type}-{workload}-{phase}-{uuid}
        parts = job_name.split('-')
        if len(parts) >= 4:
            # Find the workload part (after release name and type)
            release_parts = self.release_name.split('-')
            start_idx = len(release_parts) + 1  # Skip release name and type

            # Workload name might contain hyphens, so we need to be careful
            # Look for known workload patterns
            workload_candidates = [
                "cassandra_sai", "cassandra_lwt",
                "opensearch_basic", "opensearch_vector", "opensearch_bulk",
                "presto_analytics", "presto_ecommerce"
            ]

            for candidate in workload_candidates:
                candidate_parts = candidate.replace('_', '-').split('-')
                if len(parts) >= start_idx + len(candidate_parts):
                    potential_workload = '-'.join(parts[start_idx:start_idx + len(candidate_parts)])
                    if potential_workload.replace('-', '_') == candidate:
                        return candidate

        # Fallback: return the part after type
        if len(parts) >= 3:
            return parts[2].replace('-', '_')

        return "unknown"

    def _abbreviate_workload_name(self, workload_name: str) -> str:
        """Abbreviate workload names to save space in job names"""
        abbreviations = {
            "jdbc_analytics_longrun": "jdbc-analytics",
            "jdbc_ecommerce_longrun": "jdbc-ecommerce",
            "opensearch_basic_longrun": "os-basic",
            "opensearch_vector_search_longrun": "os-vector",
            "opensearch_bulk_longrun": "os-bulk",
            "sai_longrun": "sai",
            "lwt_longrun": "lwt"
        }
        return abbreviations.get(workload_name, workload_name[:12])

    def _test_socket_connectivity(self, host: str, port: int, timeout: int = 10) -> bool:
        """Test socket connectivity to a host and port"""
        sock = None
        try:
            logger.info(f"Testing socket connectivity to {host}:{port} with timeout {timeout}s")

            # Create a socket and attempt to connect
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)

            # Use connect_ex for non-blocking connection test
            result = sock.connect_ex((host, port))

            # connect_ex returns 0 on success
            success = result == 0
            logger.info(f"Socket connectivity test for {host}:{port}: {'SUCCESS' if success else 'FAILED'} (result={result})")
            return success

        except socket.timeout:
            logger.warning(f"Socket connectivity test timed out for {host}:{port} after {timeout}s")
            return False
        except socket.gaierror as e:
            logger.warning(f"DNS resolution failed for {host}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Socket connectivity test failed for {host}:{port}: {e}")
            return False
        finally:
            # Ensure socket is always closed
            if sock:
                try:
                    sock.close()
                except:
                    pass

    def _get_nosqlbench_resources(self) -> Dict[str, Any]:
        """Get NoSQLBench resource configuration from environment or defaults"""
        # Try to get from environment variables (set by Helm chart)
        cpu_request = os.getenv('NOSQLBENCH_CPU_REQUEST', '200m')
        memory_request = os.getenv('NOSQLBENCH_MEMORY_REQUEST', '1Gi')
        cpu_limit = os.getenv('NOSQLBENCH_CPU_LIMIT', '2000m')
        memory_limit = os.getenv('NOSQLBENCH_MEMORY_LIMIT', '4Gi')

        return {
            "requests": {
                "cpu": cpu_request,
                "memory": memory_request
            },
            "limits": {
                "cpu": cpu_limit,
                "memory": memory_limit
            }
        }
