"""
Kubernetes State Manager for NoSQLBench Demo
Manages application state using Kubernetes ConfigMaps
"""

import os
import json
import logging
import threading
from typing import Dict, Any
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
            "setup_completed": {},
            "running_benchmarks": {},
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
            with self.lock:
                self._state["last_updated"] = datetime.now().isoformat()
                state_json = json.dumps(self._state, indent=2)
                
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
    
    def update_setup_status(self, workload: str, completed: bool):
        """Update setup completion status for a workload"""
        with self.lock:
            self._state["setup_completed"][workload] = completed
        self.save_state()
        logger.info(f"Updated setup status for {workload}: {completed}")
    
    def is_setup_completed(self, workload: str) -> bool:
        """Check if setup is completed for a workload"""
        with self.lock:
            return self._state["setup_completed"].get(workload, False)
    
    def get_setup_status(self) -> Dict[str, bool]:
        """Get setup status for all workloads"""
        with self.lock:
            return self._state["setup_completed"].copy()
    
    def add_running_benchmark(self, workload: str, job_name: str, cycle_rate: int, start_time: float):
        """Add a running benchmark"""
        with self.lock:
            self._state["running_benchmarks"][workload] = {
                "job_name": job_name,
                "cycle_rate": cycle_rate,
                "start_time": start_time,
                "status": "running"
            }
        self.save_state()
        logger.info(f"Added running benchmark for {workload}: {job_name}")
    
    def remove_running_benchmark(self, workload: str):
        """Remove a running benchmark"""
        with self.lock:
            if workload in self._state["running_benchmarks"]:
                del self._state["running_benchmarks"][workload]
        self.save_state()
        logger.info(f"Removed running benchmark for {workload}")
    
    def get_running_benchmarks(self) -> Dict[str, Dict[str, Any]]:
        """Get all running benchmarks"""
        with self.lock:
            return self._state["running_benchmarks"].copy()
    
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
