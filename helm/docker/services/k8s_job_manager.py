"""
Kubernetes Job Manager for NoSQLBench workloads
Manages NoSQLBench setup and benchmark jobs in Kubernetes
"""

import os
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
            job_name = f"{self.release_name}-setup-{workload_name}-{phase}-{uuid.uuid4().hex[:8]}"
            
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
            job_name = f"{self.release_name}-benchmark-{workload_name}-{uuid.uuid4().hex[:8]}"
            
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
