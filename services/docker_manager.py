import docker
import time
import logging
from typing import Dict, Optional, List
from docker.errors import DockerException, NotFound, APIError

logger = logging.getLogger(__name__)

class DockerManager:
    """Manages Docker containers for Grafana and VictoriaMetrics"""
    
    def __init__(self):
        try:
            self.client = docker.from_env()
            self.network_name = "demo-network"
            self._ensure_network()
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise
    
    def _ensure_network(self):
        """Ensure the demo network exists"""
        try:
            self.client.networks.get(self.network_name)
            logger.info(f"Network {self.network_name} already exists")
        except NotFound:
            logger.info(f"Creating network {self.network_name}")
            self.client.networks.create(
                self.network_name,
                driver="bridge"
            )
    
    def start_victoriametrics(self, port: int = 8428) -> Dict[str, str]:
        """Start VictoriaMetrics container"""
        container_name = "demo-victoriametrics"
        
        try:
            # Check if container already exists
            try:
                container = self.client.containers.get(container_name)
                if container.status == "running":
                    return {
                        "status": "already_running",
                        "container_id": container.id,
                        "endpoint": f"http://localhost:{port}",
                        "internal_endpoint": f"http://{container_name}:{port}"
                    }
                else:
                    container.start()
                    return {
                        "status": "started",
                        "container_id": container.id,
                        "endpoint": f"http://localhost:{port}",
                        "internal_endpoint": f"http://{container_name}:{port}"
                    }
            except NotFound:
                pass
            
            # Create new container
            container = self.client.containers.run(
                "victoriametrics/victoria-metrics:latest",
                name=container_name,
                ports={f'{port}/tcp': port},
                command=[
                    '--storageDataPath=/victoria-metrics-data',
                    '--retentionPeriod=1w',
                    f'--httpListenAddr=:{port}',
                    '--influxListenAddr=:8089',
                    '--graphiteListenAddr=:2003'
                ],
                network=self.network_name,
                detach=True,
                remove=False,
                restart_policy={"Name": "unless-stopped"}
            )
            
            # Wait for container to be ready
            self._wait_for_container_health(container, port, "/health")
            
            return {
                "status": "created",
                "container_id": container.id,
                "endpoint": f"http://localhost:{port}",
                "internal_endpoint": f"http://{container_name}:{port}"
            }
            
        except APIError as e:
            logger.error(f"Failed to start VictoriaMetrics: {e}")
            raise
    
    def start_grafana(self, port: int = 3001, vm_endpoint: str = "http://demo-victoriametrics:8428") -> Dict[str, str]:
        """Start Grafana container with VictoriaMetrics as datasource"""
        container_name = "demo-grafana"
        
        try:
            # Check if container already exists
            try:
                container = self.client.containers.get(container_name)
                if container.status == "running":
                    return {
                        "status": "already_running",
                        "container_id": container.id,
                        "endpoint": f"http://localhost:{port}",
                        "credentials": {"username": "admin", "password": "admin"}
                    }
                else:
                    container.start()
                    return {
                        "status": "started",
                        "container_id": container.id,
                        "endpoint": f"http://localhost:{port}",
                        "credentials": {"username": "admin", "password": "admin"}
                    }
            except NotFound:
                pass
            
            # Create new container with volume mounts for provisioning
            import os
            current_dir = os.getcwd()

            container = self.client.containers.run(
                "grafana/grafana:latest",
                name=container_name,
                ports={'3000/tcp': port},  # Map container port 3000 to host port
                environment={
                    'GF_SECURITY_ADMIN_PASSWORD': 'admin',
                    'GF_SECURITY_ADMIN_USER': 'admin',
                    'GF_INSTALL_PLUGINS': 'grafana-clock-panel,grafana-simple-json-datasource',
                    'GF_AUTH_ANONYMOUS_ENABLED': 'true',
                    'GF_AUTH_ANONYMOUS_ORG_ROLE': 'Admin',
                    'GF_AUTH_DISABLE_LOGIN_FORM': 'true',
                    'GF_AUTH_DISABLE_SIGNOUT_MENU': 'true'
                },
                volumes={
                    f'{current_dir}/docker/monitoring/grafana/provisioning': {'bind': '/etc/grafana/provisioning', 'mode': 'ro'}
                },
                network=self.network_name,
                detach=True,
                remove=False,
                restart_policy={"Name": "unless-stopped"}
            )
            
            # Wait for container to be ready
            self._wait_for_container_health(container, port, "/api/health")
            
            # Configure VictoriaMetrics as datasource (fallback if provisioning doesn't work)
            self._configure_grafana_datasource(port, vm_endpoint)

            # Import dashboard (fallback if provisioning doesn't work)
            self._import_grafana_dashboard(port)
            
            return {
                "status": "created",
                "container_id": container.id,
                "endpoint": f"http://localhost:{port}",
                "credentials": {"username": "admin", "password": "admin"}
            }
            
        except APIError as e:
            logger.error(f"Failed to start Grafana: {e}")
            raise
    
    def _wait_for_container_health(self, container, port: int, health_path: str, timeout: int = 60):
        """Wait for container to be healthy"""
        import requests
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                container.reload()
                if container.status == "running":
                    response = requests.get(f"http://localhost:{port}{health_path}", timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Container {container.name} is healthy")
                        return
            except Exception:
                pass
            time.sleep(2)
        
        raise TimeoutError(f"Container {container.name} did not become healthy within {timeout} seconds")
    
    def _configure_grafana_datasource(self, grafana_port: int, vm_endpoint: str):
        """Configure VictoriaMetrics as Grafana datasource"""
        import requests
        
        datasource_config = {
            "name": "VictoriaMetrics",
            "type": "prometheus",
            "url": vm_endpoint,
            "access": "proxy",
            "isDefault": True
        }
        
        try:
            # Try without auth first (anonymous mode), fallback to admin auth
            response = requests.post(
                f"http://localhost:{grafana_port}/api/datasources",
                json=datasource_config,
                timeout=10
            )

            # If anonymous access fails, try with admin auth
            if response.status_code == 401:
                response = requests.post(
                    f"http://localhost:{grafana_port}/api/datasources",
                    json=datasource_config,
                    auth=("admin", "admin"),
                    timeout=10
                )
            if response.status_code in [200, 409]:  # 409 means datasource already exists
                logger.info("VictoriaMetrics datasource configured in Grafana")
            else:
                logger.warning(f"Failed to configure datasource: {response.status_code}")
        except Exception as e:
            logger.warning(f"Could not configure Grafana datasource: {e}")

    def _import_grafana_dashboard(self, grafana_port: int):
        """Import the tentative dashboard via API as fallback"""
        import requests
        import json
        import os

        dashboard_path = os.path.join(os.getcwd(), "docker/monitoring/grafana/provisioning/dashboards/database-benchmarking-overview.json")

        if not os.path.exists(dashboard_path):
            logger.warning(f"Dashboard file not found: {dashboard_path}")
            return

        try:
            # Read the dashboard JSON
            with open(dashboard_path, 'r') as f:
                dashboard_json = json.load(f)

            # Prepare the dashboard import payload
            import_payload = {
                "dashboard": dashboard_json,
                "overwrite": True,
                "inputs": []
            }

            # Try without auth first (anonymous mode), fallback to admin auth
            response = requests.post(
                f"http://localhost:{grafana_port}/api/dashboards/import",
                json=import_payload,
                timeout=10
            )

            # If anonymous access fails, try with admin auth
            if response.status_code == 401:
                response = requests.post(
                    f"http://localhost:{grafana_port}/api/dashboards/import",
                    json=import_payload,
                    auth=("admin", "admin"),
                    timeout=10
                )

            if response.status_code in [200, 412]:  # 412 means dashboard already exists
                logger.info("Dashboard imported successfully")
            else:
                logger.warning(f"Failed to import dashboard: {response.status_code} - {response.text}")

        except Exception as e:
            logger.warning(f"Could not import Grafana dashboard: {e}")

    def stop_container(self, container_name: str) -> Dict[str, str]:
        """Stop and remove a container"""
        try:
            container = self.client.containers.get(container_name)
            container.stop()
            container.remove()
            return {"status": "stopped", "container_name": container_name}
        except NotFound:
            return {"status": "not_found", "container_name": container_name}
        except APIError as e:
            logger.error(f"Failed to stop container {container_name}: {e}")
            raise
    
    def get_container_status(self, container_name: str) -> Dict[str, str]:
        """Get status of a container"""
        try:
            container = self.client.containers.get(container_name)
            return {
                "name": container_name,
                "status": container.status,
                "id": container.id
            }
        except NotFound:
            return {
                "name": container_name,
                "status": "not_found",
                "id": None
            }
    
    def cleanup_all(self) -> Dict[str, List[str]]:
        """Stop and remove all demo containers"""
        containers = ["demo-victoriametrics", "demo-grafana"]
        stopped = []
        errors = []
        
        for container_name in containers:
            try:
                result = self.stop_container(container_name)
                if result["status"] in ["stopped", "not_found"]:
                    stopped.append(container_name)
            except Exception as e:
                errors.append(f"{container_name}: {str(e)}")
        
        return {"stopped": stopped, "errors": errors}
