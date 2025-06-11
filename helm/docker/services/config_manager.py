"""
Configuration Manager for NoSQLBench Kubernetes Demo
Manages application configuration from Kubernetes ConfigMaps and environment variables
"""

import os
import yaml
import logging
from typing import Dict, List, Any, Optional

from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration from Kubernetes resources"""
    
    def __init__(self):
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
        self.config_configmap_name = f"{self.release_name}-config"
        self.workloads_configmap_name = f"{self.release_name}-workloads"
        
        # Load configuration
        self._app_config = {}
        self._workload_definitions = {}
        self.load_configuration()
        
        logger.info(f"Initialized ConfigManager for namespace: {self.namespace}")
    
    def load_configuration(self):
        """Load configuration from Kubernetes ConfigMaps"""
        try:
            # Load app configuration
            config_cm = self.core_v1.read_namespaced_config_map(
                name=self.config_configmap_name,
                namespace=self.namespace
            )
            
            if 'app-config.yaml' in config_cm.data:
                self._app_config = yaml.safe_load(config_cm.data['app-config.yaml'])
                logger.info("Loaded app configuration from ConfigMap")
            
            if 'workload-definitions.yaml' in config_cm.data:
                workload_data = yaml.safe_load(config_cm.data['workload-definitions.yaml'])
                self._workload_definitions = workload_data.get('workloads', {})
                logger.info("Loaded workload definitions from ConfigMap")
            
        except ApiException as e:
            logger.error(f"Failed to load configuration from ConfigMap: {e}")
            # Use default configuration
            self._load_default_config()
        except Exception as e:
            logger.error(f"Failed to parse configuration: {e}")
            self._load_default_config()
    
    def _load_default_config(self):
        """Load default configuration as fallback"""
        logger.info("Loading default configuration")
        
        self._app_config = {
            "databases": {
                "cassandra": {"enabled": False},
                "opensearch": {"enabled": False},
                "presto": {"enabled": False}
            },
            "metrics": {
                "endpoint": "http://victoriametrics:8428"
            },
            "workloads": {
                "defaultCycleRate": 10,
                "threadsAuto": True,
                "errorsMode": "count"
            },
            "autoSetup": False
        }
        
        self._workload_definitions = {
            "sai_longrun": {
                "file": "sai_longrun.yaml",
                "driver": "cql",
                "keyspace": "sai_test",
                "enabled": True
            },
            "lwt_longrun": {
                "file": "lwt_longrun.yaml",
                "driver": "cql",
                "keyspace": "lwt_ks",
                "enabled": True
            },
            "opensearch_basic_longrun": {
                "file": "opensearch_basic_longrun.yaml",
                "driver": "opensearch",
                "enabled": True
            },
            "opensearch_bulk_longrun": {
                "file": "opensearch_bulk_longrun.yaml",
                "driver": "opensearch",
                "enabled": True
            },
            "opensearch_vector_search_longrun": {
                "file": "opensearch_vector_search_longrun.yaml",
                "driver": "opensearch",
                "enabled": True
            },
            "jdbc_analytics_longrun": {
                "file": "jdbc_analytics_longrun.yaml",
                "driver": "jdbc",
                "enabled": True
            },
            "jdbc_ecommerce_longrun": {
                "file": "jdbc_ecommerce_longrun.yaml",
                "driver": "jdbc",
                "enabled": True
            }
        }
    
    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return self._app_config.get("databases", {})
    
    def get_metrics_endpoint(self) -> str:
        """Get metrics endpoint"""
        return self._app_config.get("metrics", {}).get("endpoint", "http://victoriametrics:8428")
    
    def get_workload_config(self, workload_name: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific workload"""
        return self._workload_definitions.get(workload_name)
    
    def get_all_workload_configs(self) -> Dict[str, Dict[str, Any]]:
        """Get all workload configurations"""
        return self._workload_definitions.copy()
    
    def get_available_workloads(self) -> List[str]:
        """Get list of available workloads based on enabled databases (legacy)"""
        # Legacy method - return all workloads for backward compatibility
        return list(self._workload_definitions.keys())

    def get_all_workloads(self) -> List[Dict[str, Any]]:
        """Get all workloads with their metadata"""
        workloads = []

        for workload_name, workload_config in self._workload_definitions.items():
            workload_info = {
                "name": workload_name,
                "file": workload_config.get("file"),
                "driver": workload_config.get("driver"),
                "database_type": self._get_database_type_from_driver(workload_config.get("driver")),
                "description": self._get_workload_description(workload_name)
            }
            workloads.append(workload_info)

        return workloads

    def _get_database_type_from_driver(self, driver: str) -> str:
        """Map driver to database type"""
        driver_mapping = {
            "cql": "cassandra",
            "opensearch": "opensearch",
            "jdbc": "presto"
        }
        return driver_mapping.get(driver, "unknown")

    def _get_workload_description(self, workload_name: str) -> str:
        """Get human-readable description for workload"""
        descriptions = {
            "sai_longrun": "Cassandra Secondary Index (SAI) workload",
            "lwt_longrun": "Cassandra Lightweight Transactions (LWT) workload",
            "opensearch_basic_longrun": "OpenSearch basic CRUD operations",
            "opensearch_bulk_longrun": "OpenSearch bulk operations",
            "opensearch_vector_search_longrun": "OpenSearch vector similarity search",
            "jdbc_analytics_longrun": "Presto/Trino analytics queries",
            "jdbc_ecommerce_longrun": "Presto/Trino e-commerce transactions"
        }
        return descriptions.get(workload_name, workload_name.replace("_", " ").title())
    
    def is_auto_setup_enabled(self) -> bool:
        """Check if auto-setup is enabled"""
        return self._app_config.get("autoSetup", False)
    
    def get_default_cycle_rate(self) -> int:
        """Get default cycle rate for benchmarks"""
        return self._app_config.get("workloads", {}).get("defaultCycleRate", 10)
    
    def is_database_enabled(self, database_type: str) -> bool:
        """Check if a database type is enabled"""
        db_config = self._app_config.get("databases", {}).get(database_type, {})
        return db_config.get("enabled", False)
    
    def get_database_connection_info(self, database_type: str) -> Dict[str, Any]:
        """Get connection information for a database"""
        return self._app_config.get("databases", {}).get(database_type, {})
    
    def reload_configuration(self):
        """Reload configuration from Kubernetes"""
        logger.info("Reloading configuration from Kubernetes")
        self.load_configuration()
    
    def get_workload_files(self) -> Dict[str, str]:
        """Get workload file contents from ConfigMap"""
        try:
            workloads_cm = self.core_v1.read_namespaced_config_map(
                name=self.workloads_configmap_name,
                namespace=self.namespace
            )
            
            return workloads_cm.data or {}
            
        except ApiException as e:
            logger.error(f"Failed to load workload files from ConfigMap: {e}")
            return {}
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate current configuration"""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check if at least one database is enabled
        enabled_databases = [
            db_type for db_type, db_config in self._app_config.get("databases", {}).items()
            if db_config.get("enabled", False)
        ]
        
        if not enabled_databases:
            validation_result["warnings"].append("No databases are enabled")
        
        # Check if enabled workloads have corresponding enabled databases
        for workload_name, workload_config in self._workload_definitions.items():
            if workload_config.get("enabled", False):
                driver = workload_config.get("driver")
                
                if driver == "cql" and not self.is_database_enabled("cassandra"):
                    validation_result["errors"].append(
                        f"Workload {workload_name} is enabled but Cassandra database is not enabled"
                    )
                elif driver == "opensearch" and not self.is_database_enabled("opensearch"):
                    validation_result["errors"].append(
                        f"Workload {workload_name} is enabled but OpenSearch database is not enabled"
                    )
                elif driver == "jdbc" and not self.is_database_enabled("presto"):
                    validation_result["errors"].append(
                        f"Workload {workload_name} is enabled but Presto database is not enabled"
                    )
        
        # Check metrics endpoint
        metrics_endpoint = self.get_metrics_endpoint()
        if not metrics_endpoint or not metrics_endpoint.startswith("http"):
            validation_result["errors"].append("Invalid metrics endpoint")
        
        validation_result["valid"] = len(validation_result["errors"]) == 0
        
        return validation_result
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """Get a summary of current configuration"""
        enabled_databases = [
            db_type for db_type, db_config in self._app_config.get("databases", {}).items()
            if db_config.get("enabled", False)
        ]
        
        enabled_workloads = [
            workload for workload, config in self._workload_definitions.items()
            if config.get("enabled", False)
        ]
        
        return {
            "namespace": self.namespace,
            "release_name": self.release_name,
            "enabled_databases": enabled_databases,
            "enabled_workloads": enabled_workloads,
            "auto_setup": self.is_auto_setup_enabled(),
            "metrics_endpoint": self.get_metrics_endpoint(),
            "default_cycle_rate": self.get_default_cycle_rate()
        }
