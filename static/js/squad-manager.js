/**
 * Claude-Squad Manager Component
 * Handles multi-agent AI development sessions
 */

class SquadManager {
    constructor(ide) {
        this.ide = ide;
        this.squadSessions = new Map();
        this.agentTypes = [
            { value: 'claude-code', label: 'Claude Code', icon: '🤖' },
            { value: 'codex', label: 'OpenAI Codex', icon: '⚡' },
            { value: 'gemini', label: 'Google Gemini', icon: '💎' },
            { value: 'aider', label: 'Aider', icon: '🔧' },
            { value: 'auto', label: 'Auto-Select', icon: '🎯' }
        ];
        this.squadInstalled = false;
        
        this.init();
    }
    
    init() {
        this.createManagerHTML();
        this.setupEventListeners();
        this.checkSquadStatus();
    }
    
    createManagerHTML() {
        const managerHTML = `
            <div id="squadManager" class="squad-manager-overlay">
                <div class="squad-manager-container">
                    <div class="squad-manager-header">
                        <h2 class="squad-manager-title">🤖 Claude-Squad Manager</h2>
                        <button class="squad-manager-close" onclick="squadManager.close()">&times;</button>
                    </div>
                    
                    <!-- Squad Status Section -->
                    <div class="squad-status-section" id="squadStatusSection">
                        <div class="squad-status-info">
                            <div class="status-indicator" id="squadStatusIndicator">❓</div>
                            <div class="status-text">
                                <h3 id="squadStatusTitle">Checking Claude-Squad...</h3>
                                <p id="squadStatusMessage">Please wait while we check the installation status.</p>
                            </div>
                        </div>
                        
                        <div class="squad-actions" id="squadActions">
                            <button class="squad-btn squad-btn-primary" id="squadInstallBtn" onclick="squadManager.installSquad()" style="display: none;">
                                📦 Install Claude-Squad
                            </button>
                            <button class="squad-btn squad-btn-secondary" id="squadRefreshBtn" onclick="squadManager.checkSquadStatus()">
                                🔄 Refresh Status
                            </button>
                        </div>
                    </div>
                    
                    <!-- Squad Sessions Section -->
                    <div class="squad-sessions-section" id="squadSessionsSection" style="display: none;">
                        <div class="section-header">
                            <h3>Active Squad Sessions</h3>
                            <button class="squad-btn squad-btn-primary" onclick="squadManager.showCreateSessionDialog()">
                                ➕ New Session
                            </button>
                        </div>
                        
                        <div class="squad-sessions-list" id="squadSessionsList">
                            <!-- Sessions will be populated here -->
                        </div>
                        
                        <div class="empty-sessions" id="emptySessions">
                            <div class="empty-sessions-icon">🤖</div>
                            <div class="empty-sessions-title">No Active Sessions</div>
                            <div class="empty-sessions-description">
                                Create your first multi-agent session to start collaborative development.
                            </div>
                            <button class="squad-btn squad-btn-primary" onclick="squadManager.showCreateSessionDialog()">
                                🚀 Create Session
                            </button>
                        </div>
                    </div>
                    
                    <!-- Create Session Dialog -->
                    <div class="squad-dialog" id="createSessionDialog" style="display: none;">
                        <div class="squad-dialog-content">
                            <div class="squad-dialog-header">
                                <h3>Create New Squad Session</h3>
                                <button class="squad-dialog-close" onclick="squadManager.hideCreateSessionDialog()">&times;</button>
                            </div>
                            
                            <div class="squad-dialog-body">
                                <div class="form-group">
                                    <label for="sessionProjectPath">Project Path</label>
                                    <select id="sessionProjectPath">
                                        <option value="">Select a project...</option>
                                    </select>
                                </div>
                                
                                <div class="form-group">
                                    <label for="sessionAgentType">AI Agent Type</label>
                                    <select id="sessionAgentType">
                                        ${this.agentTypes.map(agent => 
                                            `<option value="${agent.value}">${agent.icon} ${agent.label}</option>`
                                        ).join('')}
                                    </select>
                                </div>
                                
                                <div class="form-group">
                                    <label for="sessionName">Session Name (Optional)</label>
                                    <input type="text" id="sessionName" placeholder="Auto-generated if empty">
                                </div>
                                
                                <div class="form-group checkbox">
                                    <input type="checkbox" id="sessionAutoAccept">
                                    <label for="sessionAutoAccept">Auto-accept AI suggestions</label>
                                </div>
                            </div>
                            
                            <div class="squad-dialog-footer">
                                <button class="squad-btn squad-btn-secondary" onclick="squadManager.hideCreateSessionDialog()">
                                    Cancel
                                </button>
                                <button class="squad-btn squad-btn-primary" onclick="squadManager.createSession()">
                                    🚀 Create Session
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', managerHTML);
    }
    
    setupEventListeners() {
        // WebSocket message handling for squad responses
        if (this.ide && this.ide.ws) {
            this.originalMessageHandler = this.ide.handleWebSocketMessage.bind(this.ide);
            this.ide.handleWebSocketMessage = (message) => {
                if (message.type === 'squad_response') {
                    this.handleSquadResponse(message);
                } else {
                    this.originalMessageHandler(message);
                }
            };
        }
    }
    
    handleSquadResponse(message) {
        const { operation, data } = message;
        
        switch (operation) {
            case 'status':
                this.updateSquadStatus(data);
                break;
            case 'list_sessions':
                this.updateSessionsList(data.sessions);
                break;
            case 'create_session':
                if (data.success) {
                    this.hideCreateSessionDialog();
                    this.loadSessions();
                    this.showNotification('success', `Squad session created: ${data.session.id}`);
                } else {
                    this.showNotification('error', `Failed to create session: ${data.error}`);
                }
                break;
            case 'execute_start':
                this.showNotification('info', `Executing command in session ${data.squad_session_id}`);
                break;
            case 'execute_complete':
                const result = data.result;
                if (result.success) {
                    this.showNotification('success', 'Command executed successfully');
                    if (result.stdout) {
                        console.log('Squad Output:', result.stdout);
                    }
                } else {
                    this.showNotification('error', `Command failed: ${result.error || result.stderr}`);
                }
                break;
            default:
                if (data.error) {
                    this.showNotification('error', data.error);
                }
        }
    }
    
    async checkSquadStatus() {
        try {
            // Send squad status request via WebSocket
            this.ide.sendWebSocketMessage({
                type: 'squad_command',
                operation: 'status'
            });
        } catch (error) {
            console.error('Failed to check squad status:', error);
            this.updateSquadStatus({
                installed: false,
                errors: ['Failed to check status: ' + error.message]
            });
        }
    }
    
    updateSquadStatus(status) {
        const indicator = document.getElementById('squadStatusIndicator');
        const title = document.getElementById('squadStatusTitle');
        const message = document.getElementById('squadStatusMessage');
        const installBtn = document.getElementById('squadInstallBtn');
        const sessionsSection = document.getElementById('squadSessionsSection');
        
        this.squadInstalled = status.installed;
        
        if (status.installed) {
            indicator.textContent = '✅';
            indicator.className = 'status-indicator status-success';
            title.textContent = 'Claude-Squad Ready';
            message.textContent = `Version: ${status.version || 'Unknown'}`;
            installBtn.style.display = 'none';
            sessionsSection.style.display = 'block';
            
            // Load existing sessions
            this.loadSessions();
            this.loadProjects();
        } else {
            indicator.textContent = '❌';
            indicator.className = 'status-indicator status-error';
            title.textContent = 'Claude-Squad Not Available';
            
            if (status.errors && status.errors.length > 0) {
                message.textContent = status.errors.join('; ');
            } else {
                message.textContent = 'Claude-Squad is not installed or configured properly.';
            }
            
            installBtn.style.display = 'block';
            sessionsSection.style.display = 'none';
        }
    }
    
    async installSquad() {
        const installBtn = document.getElementById('squadInstallBtn');
        const originalText = installBtn.textContent;
        
        try {
            installBtn.textContent = '📦 Installing...';
            installBtn.disabled = true;
            
            const response = await fetch('/api/squad/install', {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('success', 'Claude-Squad installed successfully!');
                await this.checkSquadStatus();
            } else {
                this.showNotification('error', `Installation failed: ${result.error}`);
            }
        } catch (error) {
            console.error('Installation error:', error);
            this.showNotification('error', `Installation failed: ${error.message}`);
        } finally {
            installBtn.textContent = originalText;
            installBtn.disabled = false;
        }
    }
    
    loadSessions() {
        if (!this.squadInstalled) return;
        
        this.ide.sendWebSocketMessage({
            type: 'squad_command',
            operation: 'list_sessions'
        });
    }
    
    updateSessionsList(sessions) {
        const sessionsList = document.getElementById('squadSessionsList');
        const emptySessions = document.getElementById('emptySessions');
        
        if (sessions.length === 0) {
            sessionsList.style.display = 'none';
            emptySessions.style.display = 'block';
            return;
        }
        
        sessionsList.style.display = 'block';
        emptySessions.style.display = 'none';
        
        sessionsList.innerHTML = sessions.map(session => this.createSessionCard(session)).join('');
        
        // Update internal sessions map
        sessions.forEach(session => {
            this.squadSessions.set(session.id, session);
        });
    }
    
    createSessionCard(session) {
        const agentInfo = this.agentTypes.find(a => a.value === session.agent_type) || 
                         { icon: '🤖', label: session.agent_type };
        
        return `
            <div class="squad-session-card" data-session-id="${session.id}">
                <div class="session-header">
                    <div class="session-info">
                        <span class="session-agent">${agentInfo.icon} ${agentInfo.label}</span>
                        <span class="session-id">${session.id}</span>
                    </div>
                    <div class="session-status status-${session.status}">${session.status}</div>
                </div>
                
                <div class="session-details">
                    <div class="session-project">📁 ${this.getProjectName(session.project_path)}</div>
                    <div class="session-created">🕒 ${this.formatDate(session.created_at)}</div>
                </div>
                
                <div class="session-actions">
                    <button class="squad-btn squad-btn-small" onclick="squadManager.executeInSession('${session.id}')">
                        ⚡ Execute
                    </button>
                    <button class="squad-btn squad-btn-small" onclick="squadManager.openSessionTerminal('${session.id}')">
                        💻 Terminal
                    </button>
                    <button class="squad-btn squad-btn-small squad-btn-danger" onclick="squadManager.terminateSession('${session.id}')">
                        🗑️ Terminate
                    </button>
                </div>
            </div>
        `;
    }
    
    async loadProjects() {
        try {
            const response = await fetch('/api/projects');
            const projects = await response.json();
            
            const projectSelect = document.getElementById('sessionProjectPath');
            projectSelect.innerHTML = '<option value="">Select a project...</option>';
            
            projects.forEach(project => {
                const option = document.createElement('option');
                option.value = project.path;
                option.textContent = project.name;
                projectSelect.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }
    
    showCreateSessionDialog() {
        if (!this.squadInstalled) {
            this.showNotification('error', 'Claude-Squad must be installed first');
            return;
        }
        
        this.loadProjects();
        document.getElementById('createSessionDialog').style.display = 'block';
    }
    
    hideCreateSessionDialog() {
        document.getElementById('createSessionDialog').style.display = 'none';
        
        // Reset form
        document.getElementById('sessionProjectPath').value = '';
        document.getElementById('sessionAgentType').value = 'claude-code';
        document.getElementById('sessionName').value = '';
        document.getElementById('sessionAutoAccept').checked = false;
    }
    
    createSession() {
        const projectPath = document.getElementById('sessionProjectPath').value;
        const agentType = document.getElementById('sessionAgentType').value;
        const sessionName = document.getElementById('sessionName').value;
        const autoAccept = document.getElementById('sessionAutoAccept').checked;
        
        if (!projectPath) {
            this.showNotification('error', 'Please select a project');
            return;
        }
        
        this.ide.sendWebSocketMessage({
            type: 'squad_command',
            operation: 'create_session',
            project_path: projectPath,
            agent_type: agentType,
            session_name: sessionName || undefined,
            auto_accept: autoAccept
        });
    }
    
    executeInSession(sessionId) {
        const command = prompt('Enter command to execute:', 'help');
        if (!command) return;
        
        this.ide.sendWebSocketMessage({
            type: 'squad_command',
            operation: 'execute',
            squad_session_id: sessionId,
            command: command
        });
    }
    
    openSessionTerminal(sessionId) {
        // For now, just show a message - in the future could open tmux session
        this.showNotification('info', `Session ${sessionId} terminal access would open tmux session`);
    }
    
    async terminateSession(sessionId) {
        if (!confirm(`Terminate squad session ${sessionId}?`)) return;
        
        try {
            const response = await fetch(`/api/squad/sessions/${sessionId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showNotification('success', `Session ${sessionId} terminated`);
                this.squadSessions.delete(sessionId);
                this.loadSessions();
            } else {
                this.showNotification('error', 'Failed to terminate session');
            }
        } catch (error) {
            console.error('Failed to terminate session:', error);
            this.showNotification('error', `Failed to terminate session: ${error.message}`);
        }
    }
    
    // Utility methods
    getProjectName(projectPath) {
        return projectPath.split('/').pop() || projectPath;
    }
    
    formatDate(dateString) {
        if (!dateString) return 'Unknown';
        try {
            return new Date(dateString).toLocaleString();
        } catch {
            return dateString;
        }
    }
    
    showNotification(type, message) {
        // Notifications disabled - generic popups removed
        return;
    }
    
    show() {
        document.getElementById('squadManager').classList.add('show');
        this.checkSquadStatus();
    }
    
    close() {
        document.getElementById('squadManager').classList.remove('show');
    }
}

// Global instance
let squadManager = null;

// Global functions for HTML onclick handlers
function showSquadManager() {
    if (!squadManager && window.ide) {
        squadManager = new SquadManager(window.ide);
        window.squadManager = squadManager;
    }
    if (squadManager) {
        squadManager.show();
    }
}

function closeSquadManager() {
    if (squadManager) {
        squadManager.close();
    }
}

// Make functions globally accessible
window.showSquadManager = showSquadManager;
window.closeSquadManager = closeSquadManager;