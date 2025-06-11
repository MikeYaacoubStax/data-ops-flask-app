import json
import os
import threading
import time
import logging
import psutil
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ApplicationState:
    """Application state data structure"""
    infrastructure_ready: bool = False
    databases_configured: bool = False
    setup_completed: Dict[str, bool] = None
    database_config: Dict[str, Any] = None
    running_benchmarks: Dict[str, Dict[str, Any]] = None
    last_updated: str = None
    
    def __post_init__(self):
        if self.setup_completed is None:
            self.setup_completed = {}
        if self.database_config is None:
            self.database_config = {}
        if self.running_benchmarks is None:
            self.running_benchmarks = {}
        if self.last_updated is None:
            self.last_updated = datetime.now().isoformat()

class StateManager:
    """Manages persistent application state"""
    
    def __init__(self, state_file: str = "app_state.json"):
        # Store state file in project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.state_file = os.path.join(project_root, state_file)
        self.lock = threading.Lock()
        self._state = ApplicationState()
        self.load_state()
        
    def load_state(self):
        """Load state from disk"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    self._state = ApplicationState(**data)
                logger.info(f"Loaded state from {self.state_file}")
            else:
                logger.info("No existing state file found, starting with default state")
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            self._state = ApplicationState()
    
    def save_state(self):
        """Save state to disk"""
        try:
            with self.lock:
                self._state.last_updated = datetime.now().isoformat()
                with open(self.state_file, 'w') as f:
                    json.dump(asdict(self._state), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state as dictionary"""
        with self.lock:
            return asdict(self._state)
    
    def update_infrastructure_status(self, ready: bool):
        """Update infrastructure readiness status"""
        with self.lock:
            self._state.infrastructure_ready = ready
        self.save_state()
    
    def update_database_config(self, config: Dict[str, Any]):
        """Update database configuration"""
        with self.lock:
            self._state.database_config = config.copy()
            self._state.databases_configured = bool(config)
        self.save_state()
    
    def update_setup_status(self, workload: str, completed: bool):
        """Update setup completion status for a workload"""
        with self.lock:
            self._state.setup_completed[workload] = completed
        self.save_state()
    
    def get_setup_status(self, workload: str = None) -> Dict[str, bool]:
        """Get setup status for workload(s)"""
        with self.lock:
            if workload:
                return self._state.setup_completed.get(workload, False)
            return self._state.setup_completed.copy()
    
    def update_running_benchmark(self, workload: str, status: Dict[str, Any]):
        """Update running benchmark status"""
        with self.lock:
            if status is None:
                # Remove benchmark
                self._state.running_benchmarks.pop(workload, None)
            else:
                # Update benchmark status
                self._state.running_benchmarks[workload] = status.copy()
        self.save_state()
    
    def get_running_benchmarks(self) -> Dict[str, Dict[str, Any]]:
        """Get all running benchmarks"""
        with self.lock:
            return self._state.running_benchmarks.copy()
    
    def is_infrastructure_ready(self) -> bool:
        """Check if infrastructure is ready"""
        with self.lock:
            return self._state.infrastructure_ready
    
    def is_databases_configured(self) -> bool:
        """Check if databases are configured"""
        with self.lock:
            return self._state.databases_configured
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        with self.lock:
            return self._state.database_config.copy()
    
    def validate_running_processes(self, benchmark_manager):
        """Validate that running processes in state actually exist"""
        with self.lock:
            validated_benchmarks = {}
            
            for workload, status in self._state.running_benchmarks.items():
                pid = status.get('pid')
                if pid and self._is_process_running(pid):
                    # Process is still running, keep it
                    validated_benchmarks[workload] = status
                    logger.info(f"Validated running benchmark: {workload} (PID: {pid})")
                else:
                    # Process is not running, remove it
                    logger.info(f"Removing stale benchmark: {workload} (PID: {pid})")
            
            self._state.running_benchmarks = validated_benchmarks
        
        self.save_state()
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is running"""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def reset_state(self):
        """Reset state to defaults (useful for testing)"""
        with self.lock:
            self._state = ApplicationState()
        self.save_state()

    def clear_all_state(self):
        """Clear all state and delete state file (for graceful shutdown)"""
        with self.lock:
            self._state = ApplicationState()

        # Delete the state file
        try:
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
                logger.info(f"Deleted state file: {self.state_file}")
        except Exception as e:
            logger.error(f"Failed to delete state file: {e}")
    
    def cleanup_terminated_benchmarks(self):
        """Remove benchmarks that have terminated"""
        with self.lock:
            active_benchmarks = {}
            
            for workload, status in self._state.running_benchmarks.items():
                if status.get('status') == 'running':
                    pid = status.get('pid')
                    if pid and self._is_process_running(pid):
                        active_benchmarks[workload] = status
                    else:
                        logger.info(f"Benchmark {workload} (PID: {pid}) has terminated")
                        
            self._state.running_benchmarks = active_benchmarks
        
        self.save_state()
