// NoSQLBench Demo Dashboard JavaScript

class DashboardApp {
    constructor() {
        this.socket = io();
        this.state = {
            infrastructure_ready: false,
            databases_configured: false,
            setup_status: {},
            running_benchmarks: {},
            database_config: {}
        };

        // Track currently selected workloads for setup batch
        this.selectedWorkloads = null;

        // Track workloads that completed setup in the current session
        this.currentSessionCompletedWorkloads = new Set();

        // Track local runtime calculation for smooth updates
        this.localRuntimeTracking = {};

        this.initializeEventListeners();
        this.initializeSocketListeners();
        this.startRuntimeTimer();
    }
    
    initializeEventListeners() {
        // Infrastructure controls
        document.getElementById('start-infrastructure').addEventListener('click', () => {
            this.startInfrastructure();
        });
        
        document.getElementById('stop-infrastructure').addEventListener('click', () => {
            this.stopInfrastructure();
        });
        
        // Database configuration
        document.getElementById('database-config-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveDatabaseConfig();
        });
        
        // Setup controls
        document.getElementById('run-setup').addEventListener('click', () => {
            this.runSetup();
        });
        
        // Enable/disable setup button based on database configuration
        this.updateSetupButton();
    }
    
    initializeSocketListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.updateStatusIndicator('success', 'Connected');
        });
        
        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.updateStatusIndicator('danger', 'Disconnected');
        });
        
        this.socket.on('status_update', (data) => {
            this.updateState(data);
        });
        
        this.socket.on('setup_progress', (data) => {
            this.updateSetupProgress(data);
        });

        this.socket.on('setup_started', (data) => {
            this.updateSetupStarted(data);
        });
    }
    
    updateState(newState) {
        // Update local runtime tracking when new benchmark data arrives
        if (newState.running_benchmarks) {
            const currentTime = Date.now();

            Object.keys(newState.running_benchmarks).forEach(workload => {
                const benchmark = newState.running_benchmarks[workload];
                if (benchmark && benchmark.status === 'running') {
                    // Update or initialize local tracking for this benchmark
                    this.localRuntimeTracking[workload] = {
                        backendRuntimeSeconds: benchmark.runtime_seconds || 0,
                        lastUpdateTime: currentTime
                    };
                }
            });

            // Clean up tracking for stopped benchmarks
            Object.keys(this.localRuntimeTracking).forEach(workload => {
                if (!newState.running_benchmarks[workload] ||
                    newState.running_benchmarks[workload].status !== 'running') {
                    delete this.localRuntimeTracking[workload];
                }
            });
        }

        this.state = { ...this.state, ...newState };
        this.updateUI();
    }
    
    updateUI() {
        this.updateInfrastructureStatus();
        this.updateDatabaseConfigStatus();
        this.updateSetupStatus();
        this.updateBenchmarkControls();
        this.updateRunningBenchmarks();
        this.updateSetupButton();
        this.updateWorkloadSelection();
    }
    
    updateStatusIndicator(type, message) {
        const indicator = document.getElementById('status-indicator');
        indicator.className = `badge bg-${type} me-2`;
        indicator.innerHTML = `<i class="fas fa-circle"></i> ${message}`;
    }
    
    async startInfrastructure() {
        const button = document.getElementById('start-infrastructure');
        const originalText = button.innerHTML;
        
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Starting...';
        
        try {
            const response = await fetch('/api/infrastructure/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert('success', 'Infrastructure started successfully');
                this.state.infrastructure_ready = true;
                this.updateInfrastructureStatus();
            } else {
                this.showAlert('danger', `Failed to start infrastructure: ${result.error}`);
            }
        } catch (error) {
            this.showAlert('danger', `Error starting infrastructure: ${error.message}`);
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
    
    async stopInfrastructure() {
        const button = document.getElementById('stop-infrastructure');
        const originalText = button.innerHTML;
        
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Stopping...';
        
        try {
            const response = await fetch('/api/infrastructure/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert('success', 'Infrastructure stopped successfully');
                this.state.infrastructure_ready = false;
                this.updateInfrastructureStatus();
            } else {
                this.showAlert('danger', `Failed to stop infrastructure: ${result.error}`);
            }
        } catch (error) {
            this.showAlert('danger', `Error stopping infrastructure: ${error.message}`);
        } finally {
            button.disabled = false;
            button.innerHTML = originalText;
        }
    }
    
    updateInfrastructureStatus() {
        const statusDiv = document.getElementById('infrastructure-status');
        const startButton = document.getElementById('start-infrastructure');
        const stopButton = document.getElementById('stop-infrastructure');
        
        if (this.state.infrastructure_ready) {
            statusDiv.innerHTML = `
                <div class="alert alert-success">
                    <i class="fas fa-check-circle"></i> Infrastructure is running
                    <div class="mt-2">
                        <a href="http://localhost:3001" target="_blank" class="btn btn-sm btn-outline-primary me-2">
                            <i class="fas fa-chart-line"></i> Open Grafana
                        </a>
                        <a href="http://localhost:8428" target="_blank" class="btn btn-sm btn-outline-secondary">
                            <i class="fas fa-database"></i> VictoriaMetrics
                        </a>
                    </div>
                </div>
            `;
            startButton.disabled = true;
            stopButton.disabled = false;
        } else {
            statusDiv.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> Infrastructure not started
                </div>
            `;
            startButton.disabled = false;
            stopButton.disabled = true;
        }
    }
    
    async saveDatabaseConfig() {
        const config = {
            cassandra_host: document.getElementById('cassandra-host').value,
            cassandra_port: parseInt(document.getElementById('cassandra-port').value),
            opensearch_host: document.getElementById('opensearch-host').value,
            opensearch_port: parseInt(document.getElementById('opensearch-port').value),
            presto_host: document.getElementById('presto-host').value,
            presto_port: parseInt(document.getElementById('presto-port').value),
            presto_user: document.getElementById('presto-user').value
        };
        
        try {
            const response = await fetch('/api/databases/configure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert('success', 'Database configuration saved');
                this.state.databases_configured = true;
                this.state.database_config = result.config;
                this.updateSetupButton();
                this.updateWorkloadSelection();
            } else {
                this.showAlert('danger', `Failed to save configuration: ${result.error}`);
            }
        } catch (error) {
            this.showAlert('danger', `Error saving configuration: ${error.message}`);
        }
    }
    
    updateDatabaseConfigStatus() {
        // Update form fields with current configuration
        if (this.state.database_config) {
            const config = this.state.database_config;
            if (config.cassandra_host) document.getElementById('cassandra-host').value = config.cassandra_host;
            if (config.cassandra_port) document.getElementById('cassandra-port').value = config.cassandra_port;
            if (config.opensearch_host) document.getElementById('opensearch-host').value = config.opensearch_host;
            if (config.opensearch_port) document.getElementById('opensearch-port').value = config.opensearch_port;
            if (config.presto_host) document.getElementById('presto-host').value = config.presto_host;
            if (config.presto_port) document.getElementById('presto-port').value = config.presto_port;
            if (config.presto_user) document.getElementById('presto-user').value = config.presto_user;
        }
    }

    async updateWorkloadSelection() {
        if (!this.state.databases_configured) {
            return;
        }

        try {
            const response = await fetch('/api/workloads/available');
            const result = await response.json();

            if (result.success) {
                this.renderWorkloadSelection(result.workloads);
            } else {
                console.error('Failed to get available workloads:', result.error);
            }
        } catch (error) {
            console.error('Error fetching available workloads:', error);
        }
    }

    renderWorkloadSelection(workloads) {
        const container = document.getElementById('workload-selection');
        if (!container) return;

        // Only render the checkboxes, not the header (header is already in HTML template)
        let html = '';

        Object.entries(workloads).forEach(([workloadName, info]) => {
            const displayName = workloadName.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
            const isDisabled = !info.available;
            const statusClass = info.available ? 'text-success' : 'text-muted';
            const statusIcon = info.available ? 'fa-check-circle' : 'fa-times-circle';

            html += `
                <div class="form-check mb-2">
                    <input class="form-check-input" type="checkbox" value="${workloadName}"
                           id="workload-${workloadName}" ${isDisabled ? 'disabled' : ''}>
                    <label class="form-check-label ${statusClass}" for="workload-${workloadName}">
                        <i class="fas ${statusIcon} me-1"></i>
                        ${displayName}
                        <small class="text-muted">(${info.database})</small>
                        ${!info.available ? '<br><small class="text-danger">Database not configured</small>' : ''}
                    </label>
                </div>
            `;
        });

        container.innerHTML = html;
    }

    updateSetupButton() {
        const button = document.getElementById('run-setup');
        button.disabled = !this.state.databases_configured;

        // Only show "Ready to run setup" if databases are configured AND no setup is in progress
        if (this.state.databases_configured && !this.selectedWorkloads) {
            document.getElementById('setup-progress').innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> Ready to run setup
                </div>
            `;
        }
    }
    
    async runSetup() {
        const selectedWorkloads = Array.from(document.querySelectorAll('#workload-selection input:checked'))
            .map(input => input.value);
        
        if (selectedWorkloads.length === 0) {
            this.showAlert('warning', 'Please select at least one workload');
            return;
        }
        
        const button = document.getElementById('run-setup');
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running Setup...';
        
        try {
            const response = await fetch('/api/setup/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workloads: selectedWorkloads })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert('info', 'Setup started. Check progress below.');
                this.updateSetupProgressDisplay(selectedWorkloads);
            } else {
                this.showAlert('danger', `Failed to start setup: ${result.error}`);
                button.disabled = false;
                button.innerHTML = '<i class="fas fa-wrench"></i> Run Setup';
            }
        } catch (error) {
            this.showAlert('danger', `Error starting setup: ${error.message}`);
            button.disabled = false;
            button.innerHTML = '<i class="fas fa-wrench"></i> Run Setup';
        }
    }
    
    updateSetupProgressDisplay(workloads) {
        const progressDiv = document.getElementById('setup-progress');
        // Don't add header here - it's already in the HTML template
        let html = '';

        // Store the selected workloads for tracking
        this.selectedWorkloads = workloads;

        // Initialize setup status for all selected workloads
        if (!this.state.setup_status) this.state.setup_status = {};

        workloads.forEach((workload, index) => {
            // First workload starts immediately, others are pending
            const initialStatus = index === 0 ? 'running' : 'pending';

            html += `
                <div class="setup-item mb-2 p-2 border rounded" id="setup-${workload}">
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="fw-bold">${workload.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</span>
                        <span class="setup-status ${initialStatus}">
                            ${this.getStatusIcon(initialStatus)} ${this.getStatusText(initialStatus)}
                        </span>
                    </div>
                </div>
            `;
        });

        progressDiv.innerHTML = html;
    }

    getStatusIcon(status) {
        switch(status) {
            case 'pending': return '<i class="fas fa-clock"></i>';
            case 'running': return '<i class="fas fa-spinner fa-spin"></i>';
            case 'completed': return '<i class="fas fa-check"></i>';
            case 'failed': return '<i class="fas fa-times"></i>';
            default: return '<i class="fas fa-question"></i>';
        }
    }

    getStatusText(status) {
        switch(status) {
            case 'pending': return 'Pending';
            case 'running': return 'Running';
            case 'completed': return 'Completed';
            case 'failed': return 'Failed';
            default: return 'Unknown';
        }
    }
    
    updateSetupStarted(data) {
        const setupItem = document.getElementById(`setup-${data.workload}`);
        if (setupItem) {
            const statusSpan = setupItem.querySelector('.setup-status');
            statusSpan.className = 'setup-status running';
            statusSpan.innerHTML = `${this.getStatusIcon('running')} ${this.getStatusText('running')}`;
        }
    }

    updateSetupProgress(data) {
        const setupItem = document.getElementById(`setup-${data.workload}`);
        if (setupItem) {
            const statusSpan = setupItem.querySelector('.setup-status');
            const newStatus = data.success ? 'completed' : 'failed';
            statusSpan.className = `setup-status ${newStatus}`;
            statusSpan.innerHTML = `${this.getStatusIcon(newStatus)} ${this.getStatusText(newStatus)}`;
        }

        // Update state
        if (!this.state.setup_status) this.state.setup_status = {};
        this.state.setup_status[data.workload] = data.success;

        // If setup completed successfully, add to current session completed workloads
        if (data.success) {
            this.currentSessionCompletedWorkloads.add(data.workload);
        }

        // Update benchmark controls immediately when this workload's setup completes
        this.updateBenchmarkControls();

        // Check if all setups are complete (either success or failure)
        if (this.selectedWorkloads) {
            const processedWorkloads = this.selectedWorkloads.filter(w =>
                this.state.setup_status.hasOwnProperty(w)
            );

            if (processedWorkloads.length === this.selectedWorkloads.length) {
                // All workloads have been processed
                document.getElementById('run-setup').disabled = false;
                document.getElementById('run-setup').innerHTML = '<i class="fas fa-wrench"></i> Run Setup';

                // Clear selectedWorkloads so updateSetupButton can show "Ready to run setup" again
                this.selectedWorkloads = null;
            }
        }
    }
    
    updateSetupStatus() {
        // This will be called from status updates
        // Only update benchmark controls if there's no active setup batch running
        if (Object.keys(this.state.setup_status).length > 0 && !this.selectedWorkloads) {
            this.updateBenchmarkControls();
        }
    }
    
    updateBenchmarkControls() {
        const controlsDiv = document.getElementById('benchmark-controls');

        // Only show controls for workloads that completed setup in the current session
        // This prevents showing controls for workloads from previous sessions
        const currentSessionWorkloads = Array.from(this.currentSessionCompletedWorkloads).filter(
            workload => this.state.setup_status[workload] === true
        );

        if (currentSessionWorkloads.length === 0) {
            controlsDiv.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> Complete setup first to enable benchmarks
                </div>
            `;
            return;
        }
        
        let html = '<div class="row">';

        currentSessionWorkloads.forEach(workload => {
            const isRunning = this.state.running_benchmarks[workload]?.status === 'running';
            const currentRate = this.state.running_benchmarks[workload]?.cycle_rate || 10;
            
            html += `
                <div class="col-md-6 mb-3">
                    <div class="benchmark-card ${isRunning ? 'running' : 'stopped'}">
                        <h6>${workload.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}</h6>
                        <div class="cycle-rate-control mb-2">
                            <label class="form-label">Cycle Rate:</label>
                            <input type="number" class="form-control cycle-rate-input" 
                                   id="rate-${workload}" value="${currentRate}" min="1" max="10000">
                            <button class="btn btn-sm btn-secondary" onclick="app.updateCycleRate('${workload}')">
                                <i class="fas fa-sync"></i> Update
                            </button>
                        </div>
                        <div>
                            ${isRunning ? 
                                `<button class="btn btn-danger btn-sm" onclick="app.stopBenchmark('${workload}')">
                                    <i class="fas fa-stop"></i> Stop
                                </button>` :
                                `<button class="btn btn-success btn-sm" onclick="app.startBenchmark('${workload}')">
                                    <i class="fas fa-play"></i> Start
                                </button>`
                            }
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        controlsDiv.innerHTML = html;
    }
    
    async startBenchmark(workload) {
        const cycleRate = parseInt(document.getElementById(`rate-${workload}`).value);

        try {
            const response = await fetch('/api/benchmarks/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workload, cycle_rate: cycleRate })
            });

            const result = await response.json();

            if (result.success) {
                this.showAlert('success', `Started benchmark: ${workload}`);
                // Immediately update local state to reflect the change
                this.state.running_benchmarks[workload] = {
                    status: 'running',
                    pid: result.pid,
                    cycle_rate: cycleRate,
                    phase: 'run',
                    runtime_seconds: 0
                };

                // Initialize local runtime tracking immediately for smooth updates
                this.localRuntimeTracking[workload] = {
                    backendRuntimeSeconds: 0,
                    lastUpdateTime: Date.now()
                };

                this.updateBenchmarkControls();
                this.updateRunningBenchmarks();
            } else {
                this.showAlert('danger', `Failed to start benchmark: ${result.error}`);
            }
        } catch (error) {
            this.showAlert('danger', `Error starting benchmark: ${error.message}`);
        }
    }
    
    async stopBenchmark(workload) {
        try {
            const response = await fetch('/api/benchmarks/stop', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workload })
            });

            const result = await response.json();

            if (result.success) {
                this.showAlert('success', `Stopped benchmark: ${workload}`);
                // Immediately update local state to reflect the change
                delete this.state.running_benchmarks[workload];

                // Clean up local runtime tracking
                delete this.localRuntimeTracking[workload];

                this.updateBenchmarkControls();
                this.updateRunningBenchmarks();
            } else {
                this.showAlert('danger', `Failed to stop benchmark: ${result.error}`);
            }
        } catch (error) {
            this.showAlert('danger', `Error stopping benchmark: ${error.message}`);
        }
    }
    
    async updateCycleRate(workload) {
        const newRate = parseInt(document.getElementById(`rate-${workload}`).value);
        
        try {
            const response = await fetch('/api/benchmarks/update-rate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ workload, cycle_rate: newRate })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showAlert('success', `Updated cycle rate for ${workload} to ${newRate}`);
            } else {
                this.showAlert('danger', `Failed to update cycle rate: ${result.error}`);
            }
        } catch (error) {
            this.showAlert('danger', `Error updating cycle rate: ${error.message}`);
        }
    }
    
    updateRunningBenchmarks() {
        const benchmarksDiv = document.getElementById('running-benchmarks');
        const runningBenchmarks = Object.keys(this.state.running_benchmarks).filter(
            workload => this.state.running_benchmarks[workload].status === 'running'
        );

        if (runningBenchmarks.length === 0) {
            benchmarksDiv.innerHTML = `
                <div class="alert alert-info">
                    <i class="fas fa-info-circle"></i> No benchmarks running
                </div>
            `;
            return;
        }

        let html = '<div class="row">';

        runningBenchmarks.forEach(workload => {
            const benchmark = this.state.running_benchmarks[workload];

            // Calculate current runtime using local tracking for smooth updates
            let runtime = Math.floor(benchmark.runtime_seconds || 0);

            if (this.localRuntimeTracking[workload]) {
                const tracking = this.localRuntimeTracking[workload];
                const currentTime = Date.now();
                const elapsedSinceUpdate = (currentTime - tracking.lastUpdateTime) / 1000;
                runtime = Math.floor(tracking.backendRuntimeSeconds + elapsedSinceUpdate);
            }

            const hours = Math.floor(runtime / 3600);
            const minutes = Math.floor((runtime % 3600) / 60);
            const seconds = runtime % 60;
            const runtimeStr = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

            html += `
                <div class="col-md-6 mb-3">
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">
                                <i class="fas fa-play-circle status-running"></i>
                                ${workload.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            </h6>
                            <p class="card-text">
                                <small class="text-muted">
                                    PID: ${benchmark.pid} |
                                    Cycle Rate: ${benchmark.cycle_rate} |
                                    Runtime: ${runtimeStr}
                                </small>
                            </p>
                        </div>
                    </div>
                </div>
            `;
        });

        html += '</div>';
        benchmarksDiv.innerHTML = html;
    }
    
    showAlert(type, message) {
        // Create alert element
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; max-width: 400px;';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(alertDiv);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentNode) {
                alertDiv.parentNode.removeChild(alertDiv);
            }
        }, 5000);
    }

    startRuntimeTimer() {
        // Update runtime display every second for smooth real-time updates
        setInterval(() => {
            const runningBenchmarks = Object.keys(this.state.running_benchmarks).filter(
                workload => this.state.running_benchmarks[workload].status === 'running'
            );

            // Always update if there are running benchmarks to ensure smooth runtime display
            if (runningBenchmarks.length > 0) {
                this.updateRunningBenchmarks();
            }
        }, 1000);
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DashboardApp();
});
