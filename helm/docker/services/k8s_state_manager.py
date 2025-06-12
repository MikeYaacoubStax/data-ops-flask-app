"""
Kubernetes State Manager for NoSQLBench Demo
Manages application state using Kubernetes ConfigMaps
"""

import os
import json
import logging
import threading
from typing import Dict, Any, Optional
from datetime import datetime

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

class KubernetesStateManager:
    """Manages persistent application state using Kubernetes ConfigMaps"""
    
    def __init__(self):
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
        
        self.core_v1 = client.CoreV1Api()
        
        # Get namespace and release info from environment
        self.namespace = os.getenv('KUBERNETES_NAMESPACE', 'default')
        self.release_name = os.getenv('RELEASE_NAME', 'nosqlbench-demo')
        self.state_configmap_name = f"{self.release_name}-state"
        
        # Initialize state
        self._state = {
            "configured_databases": {},  # {db_id: {type, host, port, name, username, password, verified}}
            "running_jobs": {},  # {job_id: {workload, scenario, database_id, start_time, cycle_rate}}
            "last_updated": datetime.now().isoformat()
        }
        
        # Load existing state
        self.load_state()
        
        logger.info(f"Initialized KubernetesStateManager for namespace: {self.namespace}")
    
    def load_state(self):
        """Load state from Kubernetes ConfigMap"""
        try:
            configmap = self.core_v1.read_namespaced_config_map(
                name=self.state_configmap_name,
                namespace=self.namespace
            )
            
            if 'state.json' in configmap.data:
                state_data = json.loads(configmap.data['state.json'])
                self._state.update(state_data)
                logger.info(f"Loaded state from ConfigMap {self.state_configmap_name}")
            
        except ApiException as e:
            if e.status == 404:
                logger.info("State ConfigMap not found, will create new one")
                self.save_state()
            else:
                logger.error(f"Failed to load state from ConfigMap: {e}")
        except Exception as e:
            logger.error(f"Failed to parse state data: {e}")
    
    def save_state(self):
        """Save state to Kubernetes ConfigMap"""
        try:
            # Get a copy of the state to avoid holding the lock during API calls
            with self.lock:
                state_copy = self._state.copy()
                state_copy["last_updated"] = datetime.now().isoformat()

            state_json = json.dumps(state_copy, indent=2)

            configmap_body = {
                "apiVersion": "v1",
                "kind": "ConfigMap",
                "metadata": {
                    "name": self.state_configmap_name,
                    "namespace": self.namespace,
                    "labels": {
                        "app.kubernetes.io/name": "nosqlbench-demo",
                        "app.kubernetes.io/instance": self.release_name,
                        "app.kubernetes.io/component": "state"
                    }
                },
                "data": {
                    "state.json": state_json
                }
            }

            try:
                # Try to update existing ConfigMap
                self.core_v1.patch_namespaced_config_map(
                    name=self.state_configmap_name,
                    namespace=self.namespace,
                    body=configmap_body
                )
            except ApiException as e:
                if e.status == 404:
                    # ConfigMap doesn't exist, create it
                    self.core_v1.create_namespaced_config_map(
                        namespace=self.namespace,
                        body=configmap_body
                    )
                else:
                    raise

            logger.debug(f"Saved state to ConfigMap {self.state_configmap_name}")

        except Exception as e:
            logger.error(f"Failed to save state to ConfigMap: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state as dictionary"""
        with self.lock:
            return self._state.copy()

    def get_configured_databases(self) -> Dict[str, Any]:
        """Get all configured databases"""
        with self.lock:
            return self._state.get("configured_databases", {}).copy()

    def add_database(self, database_config: Dict[str, Any]) -> Dict[str, Any]:
        """Add a new database configuration"""
        try:
            # Generate unique ID for the database
            import uuid
            db_id = str(uuid.uuid4())

            # Add timestamp
            database_config['added_at'] = datetime.now().isoformat()
            database_config['id'] = db_id

            with self.lock:
                # Store in state
                if "configured_databases" not in self._state:
                    self._state["configured_databases"] = {}

                self._state["configured_databases"][db_id] = database_config

            # Save state outside of lock to avoid blocking
            try:
                self.save_state()
            except Exception as save_error:
                logger.error(f"Failed to save state after adding database: {save_error}")
                # Don't fail the operation if save fails

            logger.info(f"Added database {database_config['name']} ({database_config['type']}) with ID {db_id}")

            return {
                "success": True,
                "database_id": db_id,
                "message": f"Database {database_config['name']} added successfully"
            }

        except Exception as e:
            logger.error(f"Failed to add database: {e}")
            return {"success": False, "error": str(e)}

    def remove_database(self, db_id: str) -> Dict[str, Any]:
        """Remove a database configuration"""
        try:
            db_name = None
            with self.lock:
                if "configured_databases" not in self._state:
                    return {"success": False, "error": "No databases configured"}

                if db_id not in self._state["configured_databases"]:
                    return {"success": False, "error": "Database not found"}

                db_name = self._state["configured_databases"][db_id].get('name', db_id)
                del self._state["configured_databases"][db_id]

            # Save state outside of lock
            try:
                self.save_state()
            except Exception as save_error:
                logger.error(f"Failed to save state after removing database: {save_error}")

            logger.info(f"Removed database {db_name} with ID {db_id}")

            return {
                "success": True,
                "message": f"Database {db_name} removed successfully"
            }

        except Exception as e:
            logger.error(f"Failed to remove database: {e}")
            return {"success": False, "error": str(e)}

    def update_database_verification(self, db_id: str, verified: bool) -> Dict[str, Any]:
        """Update database verification status"""
        try:
            # Update state within lock
            with self.lock:
                if "configured_databases" not in self._state:
                    return {"success": False, "error": "No databases configured"}

                if db_id not in self._state["configured_databases"]:
                    return {"success": False, "error": "Database not found"}

                self._state["configured_databases"][db_id]["verified"] = verified
                self._state["configured_databases"][db_id]["verified_at"] = datetime.now().isoformat()

            # Save state outside of lock to avoid blocking
            try:
                self.save_state()
            except Exception as save_error:
                logger.error(f"Failed to save state after updating verification: {save_error}")
                # Don't fail the operation if save fails

            return {"success": True}

        except Exception as e:
            logger.error(f"Failed to update database verification: {e}")
            return {"success": False, "error": str(e)}

    def get_database(self, db_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific database configuration"""
        with self.lock:
            return self._state.get("configured_databases", {}).get(db_id)
    
    # Legacy methods - keeping for compatibility but not used in new simplified flow
    def update_setup_status(self, workload: str, completed: bool):
        """Update setup completion status for a workload (legacy)"""
        pass  # No longer needed in simplified flow

    def is_setup_completed(self, workload: str) -> bool:
        """Check if setup is completed for a workload (legacy)"""
        return True  # Always return True since we removed setup requirements

    def get_setup_status(self) -> Dict[str, bool]:
        """Get setup status for all workloads (legacy)"""
        return {}  # Return empty since we removed setup requirements
    
    def add_running_job(self, job_id: str, job_info: Dict[str, Any]):
        """Add a running job"""
        with self.lock:
            if "running_jobs" not in self._state:
                self._state["running_jobs"] = {}

            job_info['start_time'] = datetime.now().isoformat()
            self._state["running_jobs"][job_id] = job_info

        # Save state outside of lock
        try:
            self.save_state()
        except Exception as save_error:
            logger.error(f"Failed to save state after adding job: {save_error}")

        logger.info(f"Added running job: {job_id}")

    def remove_running_job(self, job_id: str):
        """Remove a running job"""
        removed = False
        with self.lock:
            if job_id in self._state.get("running_jobs", {}):
                del self._state["running_jobs"][job_id]
                removed = True

        if removed:
            # Save state outside of lock
            try:
                self.save_state()
            except Exception as save_error:
                logger.error(f"Failed to save state after removing job: {save_error}")

            logger.info(f"Removed running job: {job_id}")

    def get_running_jobs(self) -> Dict[str, Any]:
        """Get all running jobs"""
        with self.lock:
            return self._state.get("running_jobs", {}).copy()

    def is_job_running(self, job_id: str) -> bool:
        """Check if a job is currently running"""
        with self.lock:
            return job_id in self._state.get("running_jobs", {})

    # Legacy methods for backward compatibility
    def add_running_benchmark(self, workload: str, job_name: str, cycle_rate: int, start_time: float):
        """Add a running benchmark (legacy)"""
        job_info = {
            "workload": workload,
            "scenario": "live",  # Assume live for legacy calls
            "job_name": job_name,
            "cycle_rate": cycle_rate,
            "start_time": start_time,
            "status": "running"
        }
        self.add_running_job(job_name, job_info)

    def remove_running_benchmark(self, workload: str):
        """Remove a running benchmark (legacy)"""
        # Find job by workload name and remove it
        with self.lock:
            jobs_to_remove = []
            for job_id, job_info in self._state.get("running_jobs", {}).items():
                if job_info.get("workload") == workload:
                    jobs_to_remove.append(job_id)

            for job_id in jobs_to_remove:
                self.remove_running_job(job_id)

    def get_running_benchmarks(self) -> Dict[str, Dict[str, Any]]:
        """Get all running benchmarks (legacy)"""
        # Convert new job format to legacy benchmark format
        with self.lock:
            benchmarks = {}
            for job_id, job_info in self._state.get("running_jobs", {}).items():
                workload = job_info.get("workload")
                if workload:
                    benchmarks[workload] = job_info
            return benchmarks
    
    def update_benchmark_status(self, workload: str, status: str, **kwargs):
        """Update status of a running benchmark"""
        with self.lock:
            if workload in self._state["running_benchmarks"]:
                self._state["running_benchmarks"][workload]["status"] = status
                self._state["running_benchmarks"][workload].update(kwargs)
        self.save_state()
    
    def cleanup_completed_benchmarks(self):
        """Remove completed benchmarks from state"""
        with self.lock:
            completed = []
            for workload, benchmark_info in self._state["running_benchmarks"].items():
                if benchmark_info.get("status") in ["completed", "failed", "stopped"]:
                    completed.append(workload)
            
            for workload in completed:
                del self._state["running_benchmarks"][workload]
                logger.info(f"Cleaned up completed benchmark for {workload}")
        
        if completed:
            self.save_state()
    
    def reset_state(self):
        """Reset all state (for testing/debugging)"""
        with self.lock:
            self._state = {
                "setup_completed": {},
                "running_benchmarks": {},
                "last_updated": datetime.now().isoformat()
            }
        self.save_state()
        logger.info("Reset application state")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get state metrics for monitoring"""
        with self.lock:
            return {
                "setup_completed_count": len(self._state["setup_completed"]),
                "running_benchmarks_count": len(self._state["running_benchmarks"]),
                "last_updated": self._state["last_updated"]
            }
