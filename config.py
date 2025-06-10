import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class DatabaseConfig:
    """Configuration for database endpoints"""
    cassandra_host: Optional[str] = None
    cassandra_port: int = 9042
    opensearch_host: Optional[str] = None
    opensearch_port: int = 9200
    presto_host: Optional[str] = None
    presto_port: int = 8080
    presto_user: str = "testuser"

@dataclass
class InfrastructureConfig:
    """Configuration for monitoring infrastructure"""
    grafana_port: int = 3001
    victoriametrics_port: int = 8428
    victoriametrics_influx_port: int = 8089
    victoriametrics_graphite_port: int = 2003
    victoriametrics_endpoint: str = "http://localhost:8428"
    victoriametrics_influx_endpoint: str = "http://localhost:8089"
    # Removed separate Graphite service - using VictoriaMetrics Graphite interface

@dataclass
class BenchmarkConfig:
    """Configuration for benchmark execution"""
    default_cycle_rate: int = 10
    errors_mode: str = "count"
    threads_auto: bool = True
    nosqlbench_command: str = "nb5"
    # Docker configuration for NoSQLBench
    use_docker: bool = True
    docker_image: str = "nosqlbench/nosqlbench:5.21.8-preview"  # Update when image is available
    docker_network: str = "host"

class AppConfig:
    """Main application configuration"""
    
    def __init__(self):
        self.database = DatabaseConfig()
        self.infrastructure = InfrastructureConfig()
        self.benchmark = BenchmarkConfig()
        
        # Flask configuration
        self.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
        self.debug = os.getenv('FLASK_DEBUG', 'True').lower() == 'true'
        
        # Docker configuration
        self.docker_network = "demo-network"
        
        # Workload configurations
        self.workload_configs = {
            'cassandra_sai': {
                'file': 'sai_longrun.yaml',
                'setup_phases': ['setup.schema', 'setup.rampup'],
                'run_phase': 'sai_reads_test.sai_reads',
                'driver': 'cql',
                'keyspace': 'sai_test'
            },
            'cassandra_lwt': {
                'file': 'lwt_longrun.yaml',
                'setup_phases': ['setup.schema', 'setup.truncating', 'setup.sharding', 'setup.lwt_load'],
                'run_phase': 'lwt-updates.lwt_live_update',
                'driver': 'cql',
                'keyspace': 'lwt_ks'
            },
            'opensearch_basic': {
                'file': 'opensearch_basic_longrun.yaml',
                'setup_phases': ['default.pre_cleanup', 'default.schema', 'default.rampup'],
                'run_phase': 'default.search',
                'driver': 'opensearch'
            },
            'opensearch_vector': {
                'file': 'opensearch_vector_search_longrun.yaml',
                'setup_phases': ['default.pre_cleanup', 'default.schema', 'default.rampup'],
                'run_phase': 'default.search',
                'driver': 'opensearch'
            },
            'opensearch_bulk': {
                'file': 'opensearch_bulk_longrun.yaml',
                'setup_phases': ['default.pre_cleanup', 'default.schema', 'default.bulk_load'],
                'run_phase': 'default.verify',
                'driver': 'opensearch'
            },
            'presto_analytics': {
                'file': 'jdbc_analytics_longrun.yaml',
                'setup_phases': ['default.drop', 'default.schema', 'default.rampup'],
                'run_phase': 'default.analytics',
                'driver': 'jdbc'
            },
            'presto_ecommerce': {
                'file': 'jdbc_ecommerce_longrun.yaml',
                'setup_phases': ['default.drop', 'default.schema', 'default.rampup'],
                'run_phase': 'default.transactions',
                'driver': 'jdbc'
            }
        }

# Global configuration instance
config = AppConfig()
