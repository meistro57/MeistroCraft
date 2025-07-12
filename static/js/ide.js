/**
 * MeistroCraft IDE JavaScript Client
 * Handles Monaco Editor, WebSocket communication, and UI interactions
 */

class MeistroCraftIDE {
    constructor() {
        this.ws = null;
        this.editor = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.sessionStartTime = Date.now();
        this.requestCount = 0;
        this.sessionTokens = 0;
        this.sessionCost = 0;
        
        // Tab management
        this.openTabs = new Map();
        this.activeTab = null;
        this.tabCounter = 0;
        this.previewMode = false;
        
        this.init();
    }
    
    async init() {
        // Generate session ID
        this.sessionId = `web-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        document.getElementById('sessionId').textContent = this.sessionId;
        document.getElementById('currentSessionId').textContent = this.sessionId;
        
        // Initialize Monaco Editor
        await this.initEditor();
        
        // Initialize WebSocket connection
        this.initWebSocket();
        
        // Set up event listeners
        this.setupEventListeners();
        
        console.log('MeistroCraft IDE initialized');
        
        // Make IDE globally accessible for project wizard and manager
        window.ide = this;
        
        // Initialize notification system
        this.initNotificationSystem();
    }
    
    async initEditor() {
        require.config({ paths: { vs: 'https://unpkg.com/monaco-editor@0.44.0/min/vs' } });
        
        require(['vs/editor/editor.main'], () => {
            this.editor = monaco.editor.create(document.getElementById('editor'), {
                value: `# Welcome to MeistroCraft IDE
# Start coding with AI assistance!

def hello_world():
    """A simple function to get started."""
    print("Hello, MeistroCraft!")
    return "Ready to code!"

if __name__ == "__main__":
    hello_world()
`,
                language: 'python',
                theme: 'vs-dark',
                automaticLayout: true,
                fontSize: 14,
                minimap: { enabled: true },
                scrollBeyondLastLine: false,
                wordWrap: 'on'
            });
            
            // Set up editor event listeners
            this.editor.onDidChangeModelContent(() => {
                // Auto-save or sync changes
                this.handleCodeChange();
            });
            
            // Initialize welcome tab
            this.createTab('welcome', 'Welcome', '📝', `# Welcome to MeistroCraft IDE
## Getting Started

Welcome to the MeistroCraft IDE! This is a powerful browser-based development environment with AI assistance.

### Features:
- **AI-Powered Coding**: Chat with GPT-4 and Claude to generate code, fix bugs, and get explanations
- **Project Management**: Isolated project folders for each session
- **Live Preview**: View Markdown and HTML files in real-time
- **File Explorer**: Navigate your project files easily
- **Terminal Integration**: Run commands and see background tasks

### Quick Start:
1. Use the chat interface to describe what you want to build
2. Watch as AI creates files and code for you
3. Use the file explorer to browse your project
4. Toggle preview mode to see rendered content

Start by typing a request in the chat like:
- "Create a Python calculator"
- "Build a simple HTML webpage"
- "Write a React component"

Happy coding! 🚀
`, false);
            
            console.log('Monaco Editor initialized');
        });
    }
    
    initWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.updateConnectionStatus(true);
            this.reconnectAttempts = 0;
        };
        
        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleWebSocketMessage(message);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.updateConnectionStatus(false);
            this.attemptReconnect();
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.updateConnectionStatus(false);
        };
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.initWebSocket();
            }, 2000 * this.reconnectAttempts); // Exponential backoff
        } else {
            console.error('Max reconnection attempts reached');
            this.addChatMessage('system', 'Connection lost. Please refresh the page.');
        }
    }
    
    updateConnectionStatus(connected) {
        const statusElement = document.getElementById('connectionStatus');
        const textElement = document.getElementById('connectionText');
        
        if (connected) {
            statusElement.className = 'connection-status connected';
            textElement.textContent = 'Connected';
        } else {
            statusElement.className = 'connection-status disconnected';
            textElement.textContent = 'Disconnected';
        }
    }
    
    handleWebSocketMessage(message) {
        const { type, content, timestamp } = message;
        
        switch (type) {
            case 'connection':
                console.log('Connection confirmed:', message);
                break;
                
            case 'chat_response_start':
                // Start new AI response
                this.currentAIMessage = document.createElement('div');
                this.currentAIMessage.className = 'message ai';
                this.currentAIMessage.innerHTML = '<strong>MeistroCraft AI:</strong> ';
                this.currentAIResponseContent = document.createElement('span');
                this.currentAIMessage.appendChild(this.currentAIResponseContent);
                document.getElementById('chatMessages').appendChild(this.currentAIMessage);
                break;
                
            case 'chat_response_chunk':
                // Append chunk to current response
                if (this.currentAIResponseContent) {
                    this.currentAIResponseContent.textContent += message.chunk;
                    // Auto-scroll to bottom with debouncing for better performance
                    const chatMessages = document.getElementById('chatMessages');
                    if (chatMessages) {
                        setTimeout(() => {
                            chatMessages.scrollTop = chatMessages.scrollHeight;
                        }, 5);
                    }
                }
                break;
                
            case 'chat_response_complete':
                // Finalize AI response
                this.currentAIMessage = null;
                this.currentAIResponseContent = null;
                // Update token count if available
                if (message.total_tokens) {
                    this.updateTokenCount(message.total_tokens, message.cost);
                    this.requestCount++;
                    this.sessionTokens += message.total_tokens;
                    this.sessionCost += message.cost;
                }
                break;
                
            case 'chat_response':
                // Fallback for non-streaming responses
                this.addChatMessage('ai', content);
                break;
                
            case 'command_response':
                this.addTerminalOutput(message.output);
                break;
                
            case 'file_response':
                this.handleFileResponse(message);
                break;
                
            case 'task_queue_response':
                this.updateTaskQueue(message.tasks);
                break;
                
            case 'error':
                console.error('Server error:', message.error);
                this.addChatMessage('system', `Error: ${message.error}`);
                break;
                
            default:
                console.log('Unknown message type:', message);
        }
    }
    
    setupEventListeners() {
        // File tree clicks - use event delegation
        const fileTree = document.getElementById('fileTree');
        fileTree.addEventListener('click', (e) => {
            const clickedElement = e.target.closest('li');
            if (clickedElement) {
                const path = clickedElement.getAttribute('data-path');
                const type = clickedElement.getAttribute('data-type');
                
                if (type === 'directory') {
                    // Load directory contents
                    this.loadFileTree(path);
                } else if (type === 'file') {
                    // Load file content
                    this.loadFileContent(path);
                }
            }
        });
        
        // Load initial file tree
        this.loadFileTree();
        
        // Set up sidebar tab switching
        this.setupSidebarTabs();
        
        // Load sessions
        this.loadSessions();
        
        // Set up token tracking modal
        this.setupTokenTracking();
        
        // Start session timer
        this.startSessionTimer();
        
        // Load settings
        this.loadSettings();
        
        // Setup tab event listeners
        this.setupTabListeners();
    }
    
    // Tab Management Methods
    createTab(id, title, icon, content, isFile = false, filePath = null) {
        // Create tab data
        const tab = {
            id: id,
            title: title,
            icon: icon,
            content: content,
            isFile: isFile,
            filePath: filePath,
            modified: false,
            language: this.detectLanguage(filePath || title)
        };
        
        this.openTabs.set(id, tab);
        
        // Create tab element
        const tabElement = document.createElement('div');
        tabElement.className = 'editor-tab';
        tabElement.setAttribute('data-tab', id);
        tabElement.innerHTML = `
            <span class="tab-icon">${icon}</span>
            <span class="tab-title">${title}</span>
            <span class="tab-close" onclick="closeTab('${id}')">&times;</span>
        `;
        
        // Add click handler
        tabElement.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab-close')) {
                this.switchTab(id);
            }
        });
        
        // Add to tab list
        const tabList = document.getElementById('tabList');
        tabList.appendChild(tabElement);
        
        // Switch to new tab
        this.switchTab(id);
        
        return tab;
    }
    
    switchTab(tabId) {
        if (!this.openTabs.has(tabId)) return;
        
        // Update UI
        document.querySelectorAll('.editor-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabId}"]`).classList.add('active');
        
        // Update editor content
        const tab = this.openTabs.get(tabId);
        this.activeTab = tabId;
        
        if (this.editor) {
            this.editor.setValue(tab.content);
            monaco.editor.setModelLanguage(this.editor.getModel(), tab.language);
        }
        
        // Update preview if enabled
        if (this.previewMode) {
            this.updatePreview();
        }
    }
    
    closeTab(tabId) {
        if (this.openTabs.size <= 1) return; // Keep at least one tab
        
        const tab = this.openTabs.get(tabId);
        if (tab && tab.modified) {
            if (!confirm(`"${tab.title}" has unsaved changes. Close anyway?`)) {
                return;
            }
        }
        
        // Remove from tabs
        this.openTabs.delete(tabId);
        
        // Remove tab element
        const tabElement = document.querySelector(`[data-tab="${tabId}"]`);
        if (tabElement) {
            tabElement.remove();
        }
        
        // Switch to another tab if this was active
        if (this.activeTab === tabId) {
            const remainingTabs = Array.from(this.openTabs.keys());
            if (remainingTabs.length > 0) {
                this.switchTab(remainingTabs[0]);
            }
        }
    }
    
    markTabModified(tabId, modified = true) {
        const tab = this.openTabs.get(tabId);
        if (tab) {
            tab.modified = modified;
            const tabElement = document.querySelector(`[data-tab="${tabId}"]`);
            if (tabElement) {
                if (modified) {
                    tabElement.classList.add('modified');
                } else {
                    tabElement.classList.remove('modified');
                }
            }
        }
    }
    
    createNewFile() {
        // Prompt user for filename
        const fileName = prompt('Enter filename:', 'untitled.txt');
        if (!fileName || fileName.trim() === '') return;
        
        const trimmedName = fileName.trim();
        const tabId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        
        // Determine file icon and language
        const fileIcon = this.getFileIcon(trimmedName);
        const language = this.detectLanguage(trimmedName);
        
        // Create new tab with empty content
        const content = this.getNewFileTemplate(language);
        this.createTab(tabId, trimmedName, fileIcon, content, true, null);
        
        // Mark as modified since it's a new unsaved file
        this.markTabModified(tabId, true);
    }
    
    getNewFileTemplate(language) {
        // Return template content based on file type
        const templates = {
            'javascript': '// New JavaScript file\n\n',
            'typescript': '// New TypeScript file\n\n',
            'python': '# New Python file\n\n',
            'html': '<!DOCTYPE html>\n<html>\n<head>\n    <title>New HTML File</title>\n</head>\n<body>\n    \n</body>\n</html>\n',
            'css': '/* New CSS file */\n\n',
            'json': '{\n    \n}\n',
            'markdown': '# New Markdown File\n\n',
            'yaml': '# New YAML file\n\n',
            'sql': '-- New SQL file\n\n'
        };
        
        return templates[language] || '';
    }
    
    togglePreview() {
        this.previewMode = !this.previewMode;
        const previewPane = document.getElementById('previewPane');
        const previewToggle = document.getElementById('previewToggle');
        
        if (this.previewMode) {
            previewPane.style.display = 'flex';
            previewToggle.classList.add('active');
            this.updatePreview();
        } else {
            previewPane.style.display = 'none';
            previewToggle.classList.remove('active');
        }
    }
    
    updatePreview() {
        if (!this.activeTab) return;
        
        const tab = this.openTabs.get(this.activeTab);
        const previewContent = document.getElementById('previewContent');
        const previewMode = document.getElementById('previewMode').value;
        
        if (!tab) return;
        
        let content = tab.content;
        let detectedType = previewMode === 'auto' ? this.detectPreviewType(tab.filePath, content) : previewMode;
        
        switch (detectedType) {
            case 'markdown':
                previewContent.innerHTML = this.renderMarkdown(content);
                break;
            case 'html':
                previewContent.innerHTML = content;
                break;
            case 'text':
            default:
                previewContent.innerHTML = `<pre style="white-space: pre-wrap; font-family: 'Consolas', monospace; margin: 0;">${this.escapeHtml(content)}</pre>`;
                break;
        }
    }
    
    detectLanguage(filePath) {
        if (!filePath) return 'markdown';
        
        const extension = filePath.split('.').pop().toLowerCase();
        const languageMap = {
            'py': 'python',
            'js': 'javascript',
            'ts': 'typescript',
            'tsx': 'typescript',
            'jsx': 'javascript',
            'html': 'html',
            'htm': 'html',
            'css': 'css',
            'scss': 'scss',
            'sass': 'sass',
            'json': 'json',
            'md': 'markdown',
            'markdown': 'markdown',
            'txt': 'plaintext',
            'xml': 'xml',
            'yml': 'yaml',
            'yaml': 'yaml',
            'sh': 'shell',
            'bash': 'shell',
            'sql': 'sql',
            'php': 'php',
            'java': 'java',
            'c': 'c',
            'cpp': 'cpp',
            'cs': 'csharp',
            'go': 'go',
            'rs': 'rust',
            'rb': 'ruby'
        };
        
        return languageMap[extension] || 'plaintext';
    }
    
    detectPreviewType(filePath, content) {
        if (!filePath) {
            // Auto-detect based on content
            if (content.includes('<html') || content.includes('<!DOCTYPE')) return 'html';
            if (content.includes('#') || content.includes('*') || content.includes('[')) return 'markdown';
            return 'text';
        }
        
        const extension = filePath.split('.').pop().toLowerCase();
        if (['html', 'htm'].includes(extension)) return 'html';
        if (['md', 'markdown'].includes(extension)) return 'markdown';
        return 'text';
    }
    
    renderMarkdown(content) {
        // Simple markdown renderer - in production you'd use a library like marked.js
        let html = content
            .replace(/^### (.*$)/gim, '<h3>$1</h3>')
            .replace(/^## (.*$)/gim, '<h2>$1</h2>')
            .replace(/^# (.*$)/gim, '<h1>$1</h1>')
            .replace(/^\> (.*$)/gim, '<blockquote>$1</blockquote>')
            .replace(/\*\*(.*)\*\*/gim, '<strong>$1</strong>')
            .replace(/\*(.*)\*/gim, '<em>$1</em>')
            .replace(/!\[([^\]]*)\]\(([^\)]*)\)/gim, '<img alt="$1" src="$2" />')
            .replace(/\[([^\]]*)\]\(([^\)]*)\)/gim, '<a href="$2">$1</a>')
            .replace(/\n$/gim, '<br />')
            .replace(/^\- (.*$)/gim, '<li>$1</li>')
            .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
            .replace(/`([^`]*)`/gim, '<code>$1</code>');
        
        // Handle code blocks
        html = html.replace(/```([^`]*)```/gims, '<pre><code>$1</code></pre>');
        
        // Handle line breaks
        html = html.replace(/\n/gim, '<br>');
        
        return html;
    }
    
    escapeHtml(text) {
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }
    
    setupTabListeners() {
        // Preview mode change handler
        document.getElementById('previewMode').addEventListener('change', () => {
            if (this.previewMode) {
                this.updatePreview();
            }
        });
        
        // Editor content change handler
        if (this.editor) {
            this.editor.onDidChangeModelContent(() => {
                if (this.activeTab) {
                    const currentContent = this.editor.getValue();
                    const tab = this.openTabs.get(this.activeTab);
                    if (tab && currentContent !== tab.content) {
                        tab.content = currentContent;
                        this.markTabModified(this.activeTab, true);
                        
                        // Update preview in real-time
                        if (this.previewMode) {
                            clearTimeout(this.previewUpdateTimeout);
                            this.previewUpdateTimeout = setTimeout(() => {
                                this.updatePreview();
                            }, 300);
                        }
                    }
                }
            });
        }
    }
    
    handleCodeChange() {
        // Debounce auto-save
        clearTimeout(this.saveTimeout);
        this.saveTimeout = setTimeout(() => {
            const content = this.editor.getValue();
            // TODO: Send file save request via WebSocket
            console.log('Code changed, auto-saving...');
        }, 1000);
    }
    
    
    async loadFileContent(filePath) {
        try {
            // Ensure the file path is relative to projects
            let safePath = filePath;
            if (!safePath.startsWith('projects/')) {
                safePath = `projects/${safePath}`;
            }
            
            const response = await fetch(`/api/files/content?path=${encodeURIComponent(safePath)}`);
            if (response.ok) {
                const data = await response.json();
                
                // Create a new tab for this file
                const fileName = filePath.split('/').pop();
                const fileIcon = this.getFileIcon(fileName);
                const tabId = filePath; // Use file path as unique tab ID
                
                // Check if tab already exists
                if (this.openTabs.has(tabId)) {
                    this.switchTab(tabId);
                    return;
                }
                
                // Create new tab
                this.createTab(tabId, fileName, fileIcon, data.content, true, filePath);
                
                // Store current file path
                this.currentFilePath = filePath;
                
                // Show file name in status
                this.addChatMessage('system', `Opened: ${filePath.replace('projects/', '')}`);
            } else {
                const error = await response.json();
                this.addChatMessage('system', `Failed to load file: ${error.detail}`);
            }
        } catch (error) {
            console.error('Error loading file:', error);
            this.addChatMessage('system', `Error loading file: ${error.message}`);
        }
    }
    
    getFileIcon(fileName) {
        const extension = fileName.split('.').pop().toLowerCase();
        const iconMap = {
            'py': '🐍',
            'js': '🟨',
            'ts': '🔷',
            'tsx': '⚛️',
            'jsx': '⚛️',
            'html': '🌐',
            'htm': '🌐',
            'css': '🎨',
            'scss': '🎨',
            'sass': '🎨',
            'json': '📋',
            'md': '📝',
            'markdown': '📝',
            'txt': '📄',
            'xml': '📑',
            'yml': '⚙️',
            'yaml': '⚙️',
            'sh': '💻',
            'bash': '💻',
            'sql': '🗃️',
            'php': '🐘',
            'java': '☕',
            'c': '🔧',
            'cpp': '🔧',
            'cs': '🔹',
            'go': '🐹',
            'rs': '🦀',
            'rb': '💎',
            'pdf': '📕',
            'png': '🖼️',
            'jpg': '🖼️',
            'jpeg': '🖼️',
            'gif': '🖼️',
            'svg': '🖼️'
        };
        
        return iconMap[extension] || '📄';
    }
    
    handleFileResponse(message) {
        const { operation, path, data, status, error } = message;
        
        if (status === 'success') {
            if (operation === 'read') {
                // Load file content into editor
                if (this.editor) {
                    this.editor.setValue(data || `// Content of ${path}\n// File loading placeholder`);
                    // Set language based on file extension
                    const extension = path.split('.').pop();
                    const languageMap = {
                        'py': 'python',
                        'js': 'javascript',
                        'ts': 'typescript',
                        'html': 'html',
                        'css': 'css',
                        'json': 'json',
                        'md': 'markdown',
                        'txt': 'plaintext'
                    };
                    const language = languageMap[extension] || 'plaintext';
                    monaco.editor.setModelLanguage(this.editor.getModel(), language);
                }
            } else if (operation === 'list') {
                // Update file tree
                this.updateFileTree(data, path);
            }
        } else {
            console.error(`File operation failed: ${error}`);
            this.addChatMessage('system', `File operation failed: ${error}`);
        }
    }
    
    async loadFileTree(path = 'projects') {
        // Load file tree via REST API (restricted to projects folder)
        try {
            const response = await fetch(`/api/files?path=${encodeURIComponent(path)}`);
            if (response.ok) {
                const data = await response.json();
                this.updateFileTree(data.items, data.path);
            } else {
                console.error('Failed to load file tree');
                // Show empty projects message if no files
                this.showEmptyProjectsMessage();
            }
        } catch (error) {
            console.error('Error loading file tree:', error);
            this.showEmptyProjectsMessage();
        }
    }
    
    updateFileTree(items, currentPath) {
        const fileTree = document.getElementById('fileTree');
        fileTree.innerHTML = '';
        
        // Handle empty projects folder
        if (!items || items.length === 0) {
            this.showEmptyProjectsMessage();
            return;
        }
        
        // Add parent directory link if not at projects root
        const projectsRoot = 'projects';
        if (currentPath && currentPath !== projectsRoot && !currentPath.endsWith('projects')) {
            const parentItem = document.createElement('li');
            parentItem.innerHTML = '📁 ..';
            parentItem.style.cursor = 'pointer';
            parentItem.style.color = '#888';
            
            // Calculate parent path
            const pathParts = currentPath.replace(/^projects\//, '').split('/');
            pathParts.pop(); // Remove current directory
            const parentPath = pathParts.length > 0 ? `projects/${pathParts.join('/')}` : 'projects';
            
            parentItem.setAttribute('data-path', parentPath);
            parentItem.setAttribute('data-type', 'directory');
            fileTree.appendChild(parentItem);
        }
        
        // Add current directory items
        items.forEach(item => {
            const listItem = document.createElement('li');
            const icon = item.type === 'directory' ? '📁' : '📄';
            listItem.innerHTML = `${icon} ${item.name}`;
            listItem.style.cursor = 'pointer';
            
            // Make paths relative to projects folder for display
            let displayPath = item.path;
            if (displayPath.includes('projects/')) {
                displayPath = displayPath.substring(displayPath.indexOf('projects/'));
            }
            
            listItem.setAttribute('data-path', displayPath);
            listItem.setAttribute('data-type', item.type);
            
            if (item.type === 'file') {
                listItem.style.color = '#d4d4d4';
            } else {
                listItem.style.color = '#ffd700';
            }
            
            fileTree.appendChild(listItem);
        });
    }
    
    showEmptyProjectsMessage() {
        const fileTree = document.getElementById('fileTree');
        fileTree.innerHTML = `
            <li style="color: #888; font-style: italic; text-align: center; padding: 20px;">
                📂 No projects yet<br>
                <small>Start a new session to create your first project</small>
            </li>
        `;
    }
    
    sendWebSocketMessage(message) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(message));
        } else {
            console.error('WebSocket not connected');
            this.addChatMessage('system', 'Not connected to server. Please check your connection.');
        }
    }
    
    addChatMessage(sender, content) {
        const messagesContainer = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        
        messageDiv.className = `message ${sender}`;
        
        let prefix = '';
        if (sender === 'ai') prefix = '<strong>MeistroCraft AI:</strong> ';
        else if (sender === 'user') prefix = '<strong>You:</strong> ';
        else if (sender === 'system') prefix = '<strong>System:</strong> ';
        
        messageDiv.innerHTML = `${prefix}${content}`;
        messagesContainer.appendChild(messageDiv);
        
        // Ensure auto-scroll to bottom
        setTimeout(() => {
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }, 10);
    }
    
    addTerminalOutput(output) {
        const terminalOutput = document.getElementById('terminalOutput');
        if (!terminalOutput) return;
        
        // Add output with proper newline handling
        if (terminalOutput.textContent.trim() === '') {
            terminalOutput.textContent = output;
        } else {
            terminalOutput.textContent += '\n' + output;
        }
        
        // Force auto-scroll to bottom with a small delay to ensure content is rendered
        setTimeout(() => {
            terminalOutput.scrollTop = terminalOutput.scrollHeight;
        }, 10);
    }
    
    updateTokenCount(tokens, cost) {
        // Update token and cost display
        const tokenElement = document.getElementById('tokenCount');
        const costElement = document.getElementById('costAmount');
        
        if (tokenElement) {
            const currentTokens = parseInt(tokenElement.textContent) || 0;
            tokenElement.textContent = currentTokens + tokens;
        }
        
        if (costElement && cost) {
            const currentCost = parseFloat(costElement.textContent) || 0;
            costElement.textContent = (currentCost + cost).toFixed(3);
        }
    }
    
    refreshTasks() {
        // Request task queue status from server
        this.sendWebSocketMessage({
            type: 'get_tasks'
        });
    }
    
    getActiveTabContext() {
        // Get information about the currently active tab/file for AI context
        if (!this.activeTab || !this.openTabs.has(this.activeTab)) {
            return null;
        }
        
        const tab = this.openTabs.get(this.activeTab);
        const context = {
            tab_id: tab.id,
            tab_title: tab.title,
            language: tab.language,
            is_file: tab.isFile,
            file_path: tab.filePath,
            content_preview: null
        };
        
        // Add content preview for file tabs (first 500 characters)
        if (tab.isFile && this.editor && this.activeTab === tab.id) {
            const content = this.editor.getValue();
            if (content && content.length > 0) {
                context.content_preview = content.substring(0, 500);
                if (content.length > 500) {
                    context.content_preview += "...[truncated]";
                }
            }
        }
        
        return context;
    }
    
    updateTaskQueue(tasks) {
        const taskList = document.getElementById('taskList');
        if (!taskList) return;
        
        taskList.innerHTML = '';
        
        tasks.forEach(task => {
            const taskItem = document.createElement('div');
            taskItem.className = `task-item ${task.status}`;
            
            const icon = this.getTaskIcon(task.status);
            const timeText = this.formatTaskTime(task);
            
            taskItem.innerHTML = `
                <span class="task-icon">${icon}</span>
                <span class="task-name">${task.name}</span>
                <span class="task-time">${timeText}</span>
            `;
            
            taskList.appendChild(taskItem);
        });
    }
    
    getTaskIcon(status) {
        switch (status) {
            case 'completed': return '✓';
            case 'running': return '⏳';
            case 'pending': return '📋';
            case 'failed': return '❌';
            default: return '📋';
        }
    }
    
    formatTaskTime(task) {
        if (task.status === 'running') return 'Running...';
        if (task.status === 'pending') return 'Queued';
        if (task.completed_at) {
            const now = new Date();
            const completed = new Date(task.completed_at);
            const diffMs = now - completed;
            const diffMins = Math.floor(diffMs / 60000);
            if (diffMins < 1) return 'Just now';
            if (diffMins < 60) return `${diffMins} min ago`;
            return `${Math.floor(diffMins / 60)} hr ago`;
        }
        return '';
    }
    
    setupSidebarTabs() {
        const tabs = document.querySelectorAll('.sidebar-tab');
        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.getAttribute('data-tab');
                this.switchSidebarTab(tabName);
            });
        });
    }
    
    switchSidebarTab(tabName) {
        // Update tab appearance
        document.querySelectorAll('.sidebar-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Show/hide content
        if (tabName === 'explorer') {
            document.getElementById('explorerTab').style.display = 'block';
            document.getElementById('sessionsTab').style.display = 'none';
            document.getElementById('settingsTab').style.display = 'none';
        } else if (tabName === 'sessions') {
            document.getElementById('explorerTab').style.display = 'none';
            document.getElementById('sessionsTab').style.display = 'block';
            document.getElementById('settingsTab').style.display = 'none';
        } else if (tabName === 'settings') {
            document.getElementById('explorerTab').style.display = 'none';
            document.getElementById('sessionsTab').style.display = 'none';
            document.getElementById('settingsTab').style.display = 'block';
        }
    }
    
    async loadSessions() {
        try {
            const response = await fetch('/api/sessions');
            if (response.ok) {
                const data = await response.json();
                this.updateSessionsList(data.sessions);
            } else {
                console.error('Failed to load sessions');
            }
        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    }
    
    updateSessionsList(sessions) {
        const sessionList = document.getElementById('sessionList');
        if (!sessionList) return;
        
        sessionList.innerHTML = '';
        
        sessions.forEach(session => {
            const sessionItem = document.createElement('div');
            sessionItem.className = 'session-item';
            
            const timeAgo = this.formatTimeAgo(new Date(session.last_accessed));
            
            sessionItem.innerHTML = `
                <span class="session-icon">💾</span>
                <div class="session-details">
                    <div class="session-name">${session.name}</div>
                    <div class="session-time">${timeAgo}</div>
                </div>
                <button class="btn-tiny" onclick="window.ide.loadSession('${session.id}')">Load</button>
            `;
            
            sessionList.appendChild(sessionItem);
        });
    }
    
    formatTimeAgo(date) {
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);
        
        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins} min ago`;
        if (diffHours < 24) return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
        return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    }
    
    async saveCurrentSession() {
        const sessionName = prompt('Enter session name:', 'Unnamed Session');
        if (!sessionName) return;
        
        try {
            const response = await fetch(`/api/sessions/${this.sessionId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    name: sessionName
                })
            });
            
            if (response.ok) {
                document.getElementById('currentSessionName').textContent = sessionName;
                this.addChatMessage('system', `Session saved as "${sessionName}"`);
                this.loadSessions(); // Refresh sessions list
            } else {
                this.addChatMessage('system', 'Failed to save session');
            }
        } catch (error) {
            console.error('Error saving session:', error);
            this.addChatMessage('system', 'Error saving session');
        }
    }
    
    async loadSession(sessionId) {
        try {
            const response = await fetch(`/api/sessions/${sessionId}`);
            if (response.ok) {
                // In real implementation, would restore session state
                this.addChatMessage('system', `Loading session ${sessionId}...`);
                window.location.reload(); // Simple reload for demo
            } else {
                this.addChatMessage('system', 'Failed to load session');
            }
        } catch (error) {
            console.error('Error loading session:', error);
            this.addChatMessage('system', 'Error loading session');
        }
    }
    
    async createNewSession() {
        try {
            const response = await fetch('/api/sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    config: {}
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                this.addChatMessage('system', `New session created: ${data.session_id}`);
                window.location.reload(); // Simple reload for demo
            } else {
                this.addChatMessage('system', 'Failed to create new session');
            }
        } catch (error) {
            console.error('Error creating session:', error);
            this.addChatMessage('system', 'Error creating new session');
        }
    }
    
    setupTokenTracking() {
        // Add click handlers for status bar items
        document.querySelectorAll('.status-item').forEach((item, index) => {
            if (index >= 2 && index <= 4) { // Token, cost, and API status items
                item.addEventListener('click', () => {
                    this.showTokenModal();
                });
            }
        });
    }
    
    showTokenModal() {
        // Update modal with current data
        this.updateTokenModal();
        document.getElementById('tokenModal').style.display = 'block';
    }
    
    updateTokenModal() {
        // Update session stats
        const duration = this.formatDuration(Date.now() - this.sessionStartTime);
        document.getElementById('sessionDuration').textContent = duration;
        document.getElementById('sessionRequests').textContent = this.requestCount;
        document.getElementById('sessionTokens').textContent = this.sessionTokens.toLocaleString();
        document.getElementById('sessionCost').textContent = `$${this.sessionCost.toFixed(4)}`;
    }
    
    formatDuration(ms) {
        const minutes = Math.floor(ms / 60000);
        const seconds = Math.floor((ms % 60000) / 1000);
        if (minutes === 0) return `${seconds} seconds`;
        return `${minutes} minute${minutes !== 1 ? 's' : ''} ${seconds} seconds`;
    }
    
    startSessionTimer() {
        setInterval(() => {
            const elapsed = Date.now() - this.sessionStartTime;
            const minutes = Math.floor(elapsed / 60000);
            const seconds = Math.floor((elapsed % 60000) / 1000);
            const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
            document.getElementById('sessionTime').textContent = timeString;
        }, 1000);
    }
    
    loadSettings() {
        // Load settings from localStorage
        const settings = JSON.parse(localStorage.getItem('meistrocraft-settings') || '{}');
        
        // Apply default settings and load from storage
        this.settings = {
            // API Configuration
            openaiKey: '',
            anthropicKey: '',
            defaultModel: 'gpt-4',
            
            // Editor Settings
            editorTheme: 'vs-dark',
            fontSize: 14,
            tabSize: 4,
            wordWrap: true,
            minimap: true,
            
            // Usage Limits
            dailyLimit: 5.00,
            monthlyLimit: 50.00,
            lowBalanceAlerts: true,
            
            // Terminal Settings
            terminalFont: 'Consolas, Monaco, monospace',
            terminalFontSize: 12,
            terminalSound: false,
            
            // Auto-save & Backup
            autoSave: true,
            autoSaveDelay: 5,
            sessionBackup: true,
            
            ...settings
        };
        
        // Apply settings to UI
        this.applySettings();
        
        // Set up settings UI event listeners
        this.setupSettingsListeners();
    }
    
    applySettings() {
        // Apply editor settings
        if (this.editor) {
            monaco.editor.setTheme(this.settings.editorTheme);
            this.editor.updateOptions({
                fontSize: this.settings.fontSize,
                tabSize: this.settings.tabSize,
                wordWrap: this.settings.wordWrap ? 'on' : 'off',
                minimap: { enabled: this.settings.minimap }
            });
        }
        
        // Apply terminal settings
        const terminalOutput = document.getElementById('terminalOutput');
        if (terminalOutput) {
            terminalOutput.style.fontFamily = this.settings.terminalFont;
            terminalOutput.style.fontSize = this.settings.terminalFontSize + 'px';
        }
        
        // Update UI elements
        this.updateSettingsUI();
    }
    
    updateSettingsUI() {
        // Update all form elements with current settings
        document.getElementById('openaiKey').value = this.settings.openaiKey;
        document.getElementById('anthropicKey').value = this.settings.anthropicKey;
        document.getElementById('defaultModel').value = this.settings.defaultModel;
        
        document.getElementById('editorTheme').value = this.settings.editorTheme;
        document.getElementById('fontSize').value = this.settings.fontSize;
        document.getElementById('fontSizeValue').textContent = this.settings.fontSize + 'px';
        document.getElementById('tabSize').value = this.settings.tabSize;
        document.getElementById('wordWrap').checked = this.settings.wordWrap;
        document.getElementById('minimap').checked = this.settings.minimap;
        
        document.getElementById('dailyLimit').value = this.settings.dailyLimit;
        document.getElementById('monthlyLimit').value = this.settings.monthlyLimit;
        document.getElementById('lowBalanceAlerts').checked = this.settings.lowBalanceAlerts;
        
        document.getElementById('terminalFont').value = this.settings.terminalFont;
        document.getElementById('terminalFontSize').value = this.settings.terminalFontSize;
        document.getElementById('terminalFontSizeValue').textContent = this.settings.terminalFontSize + 'px';
        document.getElementById('terminalSound').checked = this.settings.terminalSound;
        
        document.getElementById('autoSave').checked = this.settings.autoSave;
        document.getElementById('autoSaveDelay').value = this.settings.autoSaveDelay;
        document.getElementById('sessionBackup').checked = this.settings.sessionBackup;
    }
    
    setupSettingsListeners() {
        // Font size sliders
        document.getElementById('fontSize').addEventListener('input', (e) => {
            document.getElementById('fontSizeValue').textContent = e.target.value + 'px';
        });
        
        document.getElementById('terminalFontSize').addEventListener('input', (e) => {
            document.getElementById('terminalFontSizeValue').textContent = e.target.value + 'px';
        });
    }
    
    saveSettings() {
        // Collect all settings from UI
        this.settings = {
            openaiKey: document.getElementById('openaiKey').value,
            anthropicKey: document.getElementById('anthropicKey').value,
            defaultModel: document.getElementById('defaultModel').value,
            
            editorTheme: document.getElementById('editorTheme').value,
            fontSize: parseInt(document.getElementById('fontSize').value),
            tabSize: parseInt(document.getElementById('tabSize').value),
            wordWrap: document.getElementById('wordWrap').checked,
            minimap: document.getElementById('minimap').checked,
            
            dailyLimit: parseFloat(document.getElementById('dailyLimit').value),
            monthlyLimit: parseFloat(document.getElementById('monthlyLimit').value),
            lowBalanceAlerts: document.getElementById('lowBalanceAlerts').checked,
            
            terminalFont: document.getElementById('terminalFont').value,
            terminalFontSize: parseInt(document.getElementById('terminalFontSize').value),
            terminalSound: document.getElementById('terminalSound').checked,
            
            autoSave: document.getElementById('autoSave').checked,
            autoSaveDelay: parseInt(document.getElementById('autoSaveDelay').value),
            sessionBackup: document.getElementById('sessionBackup').checked
        };
        
        // Save to localStorage
        localStorage.setItem('meistrocraft-settings', JSON.stringify(this.settings));
        
        // Apply settings immediately
        this.applySettings();
        
        // Show success message
        this.addChatMessage('system', 'Settings saved successfully!');
    }
    
    resetSettings() {
        if (confirm('Reset all settings to defaults? This cannot be undone.')) {
            localStorage.removeItem('meistrocraft-settings');
            this.loadSettings();
            this.addChatMessage('system', 'Settings reset to defaults.');
        }
    }
    
    exportSettings() {
        const settingsBlob = new Blob([JSON.stringify(this.settings, null, 2)], {
            type: 'application/json'
        });
        const url = URL.createObjectURL(settingsBlob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'meistrocraft-settings.json';
        a.click();
        URL.revokeObjectURL(url);
        
        this.addChatMessage('system', 'Settings exported successfully!');
    }
    
    importSettings() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.json';
        input.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (event) => {
                    try {
                        const importedSettings = JSON.parse(event.target.result);
                        this.settings = { ...this.settings, ...importedSettings };
                        localStorage.setItem('meistrocraft-settings', JSON.stringify(this.settings));
                        this.applySettings();
                        this.addChatMessage('system', 'Settings imported successfully!');
                    } catch (error) {
                        this.addChatMessage('system', 'Error importing settings: Invalid JSON file');
                    }
                };
                reader.readAsText(file);
            }
        };
        input.click();
    }
    
    initNotificationSystem() {
        // Create notification container if it doesn't exist
        if (!document.getElementById('notificationContainer')) {
            const container = document.createElement('div');
            container.id = 'notificationContainer';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                max-width: 400px;
                pointer-events: none;
            `;
            document.body.appendChild(container);
        }
    }
    
    showNotification(type, message, duration = 5000) {
        const container = document.getElementById('notificationContainer');
        if (!container) return;
        
        const notification = document.createElement('div');
        notification.style.cssText = `
            background: ${this.getNotificationColor(type)};
            color: white;
            padding: 12px 16px;
            border-radius: 6px;
            margin-bottom: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            pointer-events: auto;
            cursor: pointer;
            transition: all 0.3s ease;
            transform: translateX(100%);
            opacity: 0;
            font-size: 14px;
            line-height: 1.4;
            border-left: 4px solid rgba(255, 255, 255, 0.3);
        `;
        
        notification.innerHTML = `
            <div style="display: flex; align-items: flex-start; gap: 8px;">
                <span style="font-size: 16px;">${this.getNotificationIcon(type)}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600; margin-bottom: 2px;">${this.getNotificationTitle(type)}</div>
                    <div>${message}</div>
                </div>
                <button style="background: none; border: none; color: rgba(255, 255, 255, 0.8); cursor: pointer; font-size: 18px; padding: 0; line-height: 1;">&times;</button>
            </div>
        `;
        
        // Add click to close
        notification.addEventListener('click', () => {
            this.removeNotification(notification);
        });
        
        container.appendChild(notification);
        
        // Animate in
        setTimeout(() => {
            notification.style.transform = 'translateX(0)';
            notification.style.opacity = '1';
        }, 10);
        
        // Auto-remove after duration
        if (duration > 0) {
            setTimeout(() => {
                this.removeNotification(notification);
            }, duration);
        }
        
        return notification;
    }
    
    removeNotification(notification) {
        if (!notification || !notification.parentNode) return;
        
        notification.style.transform = 'translateX(100%)';
        notification.style.opacity = '0';
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 300);
    }
    
    getNotificationColor(type) {
        const colors = {
            success: '#28a745',
            error: '#dc3545',
            warning: '#ffc107',
            info: '#007acc'
        };
        return colors[type] || colors.info;
    }
    
    getNotificationIcon(type) {
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        return icons[type] || icons.info;
    }
    
    getNotificationTitle(type) {
        const titles = {
            success: 'Success',
            error: 'Error',
            warning: 'Warning',
            info: 'Information'
        };
        return titles[type] || titles.info;
    }
    
    // Method to load files from a specific project path
    async loadFiles(projectPath) {
        try {
            const response = await fetch(`/api/files?path=${encodeURIComponent(projectPath)}`);
            if (response.ok) {
                const data = await response.json();
                this.populateFileTree(data.items);
                this.showNotification('success', `Loaded project: ${projectPath}`);
            } else {
                throw new Error('Failed to load project files');
            }
        } catch (error) {
            console.error('Failed to load project files:', error);
            this.showNotification('error', 'Failed to load project files');
        }
    }
}

// Chat input handler
function handleChatInput(event) {
    if (event.key === 'Enter') {
        const input = event.target;
        const message = input.value.trim();
        
        if (message) {
            // Add user message to chat
            ide.addChatMessage('user', message);
            
            // Send to AI via WebSocket with active tab context
            const activeTabContext = ide.getActiveTabContext();
            ide.sendWebSocketMessage({
                type: 'chat',
                content: message,
                context: activeTabContext
            });
            
            input.value = '';
        }
    }
}

// Terminal input handler
function handleTerminalInput(event) {
    if (event.key === 'Enter') {
        const input = event.target;
        const command = input.value.trim();
        
        if (command) {
            // Add command to terminal output
            ide.addTerminalOutput(`$ ${command}`);
            
            // Send command via WebSocket
            ide.sendWebSocketMessage({
                type: 'command',
                command: command
            });
            
            input.value = '';
        }
    }
}

// Tab switching functionality
function switchTab(tabName) {
    const tabs = document.querySelectorAll('.tab');
    const terminalOutput = document.getElementById('terminalOutput');
    const taskQueue = document.getElementById('taskQueue');
    
    tabs.forEach(tab => tab.classList.remove('active'));
    
    if (tabName === 'terminal') {
        document.querySelector('.tab:nth-child(2)').classList.add('active');
        terminalOutput.style.display = 'block';
        taskQueue.style.display = 'none';
    } else if (tabName === 'tasks') {
        document.querySelector('.tab:nth-child(1)').classList.add('active');
        terminalOutput.style.display = 'none';
        taskQueue.style.display = 'block';
    }
}

// Refresh tasks function
function refreshTasks() {
    console.log('Refreshing tasks...');
    // TODO: Implement actual task refresh via WebSocket/API
    if (window.ide) {
        window.ide.refreshTasks();
    }
}

// Add tab click listeners
document.addEventListener('DOMContentLoaded', () => {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => {
            if (index === 0) switchTab('tasks');
            if (index === 1) switchTab('terminal');
        });
    });
    
    // Initialize in tasks view
    switchTab('tasks');
});

// Global functions for HTML onclick handlers
function createNewSession() {
    if (window.ide) {
        window.ide.createNewSession();
    }
}

function saveCurrentSession() {
    if (window.ide) {
        window.ide.saveCurrentSession();
    }
}

function loadSession(sessionId) {
    if (window.ide) {
        window.ide.loadSession(sessionId);
    }
}

function closeTokenModal() {
    document.getElementById('tokenModal').style.display = 'none';
}

function saveSettings() {
    if (window.ide) {
        window.ide.saveSettings();
    }
}

function resetSettings() {
    if (window.ide) {
        window.ide.resetSettings();
    }
}

function exportSettings() {
    if (window.ide) {
        window.ide.exportSettings();
    }
}

function importSettings() {
    if (window.ide) {
        window.ide.importSettings();
    }
}

function newFile() {
    if (window.ide) {
        window.ide.createNewFile();
    }
}

// Initialize IDE when page loads
let ide;
document.addEventListener('DOMContentLoaded', () => {
    ide = new MeistroCraftIDE();
    window.ide = ide; // Make globally accessible
    
    // Initialize resize functionality
    initializeResize();
});

// Resize functionality
function initializeResize() {
    const ideContainer = document.querySelector('.ide-container');
    const sidebarHandle = document.getElementById('resizeSidebar');
    const chatHandle = document.getElementById('resizeChat');
    const terminalHandle = document.getElementById('resizeTerminal');
    
    console.log('Initializing resize...', {
        ideContainer,
        sidebarHandle,
        chatHandle,
        terminalHandle
    });
    
    if (!ideContainer || !sidebarHandle || !chatHandle || !terminalHandle) {
        console.error('Resize elements not found');
        return;
    }
    
    let isResizing = false;
    let currentHandle = null;
    let startPos = 0;
    let startSize = 0;
    
    // Sidebar resize
    sidebarHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'sidebar';
        startPos = e.clientX;
        const cols = window.getComputedStyle(ideContainer).gridTemplateColumns.split(' ');
        startSize = parseInt(cols[0].replace('px', ''));
        sidebarHandle.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.classList.add('resizing');
        e.preventDefault();
    });
    
    // Chat panel resize
    chatHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'chat';
        startPos = e.clientX;
        const cols = window.getComputedStyle(ideContainer).gridTemplateColumns.split(' ');
        startSize = parseInt(cols[cols.length - 1].replace('px', ''));
        chatHandle.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
        document.body.classList.add('resizing');
        e.preventDefault();
    });
    
    // Terminal resize
    terminalHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'terminal';
        startPos = e.clientY;
        const rows = window.getComputedStyle(ideContainer).gridTemplateRows.split(' ');
        startSize = parseInt(rows[rows.length - 1].replace('px', ''));
        terminalHandle.classList.add('dragging');
        document.body.style.cursor = 'row-resize';
        document.body.classList.add('resizing');
        e.preventDefault();
    });
    
    // Mouse move handler
    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        
        if (currentHandle === 'sidebar') {
            const delta = e.clientX - startPos;
            const newSize = Math.max(200, Math.min(600, startSize + delta));
            // Get current chat panel size to maintain it
            const currentCols = window.getComputedStyle(ideContainer).gridTemplateColumns.split(' ');
            const chatSize = currentCols[2] || '300px';
            ideContainer.style.gridTemplateColumns = `${newSize}px 1fr ${chatSize}`;
        } else if (currentHandle === 'chat') {
            const delta = startPos - e.clientX;
            const newSize = Math.max(200, Math.min(600, startSize + delta));
            // Get current sidebar size to maintain it
            const currentCols = window.getComputedStyle(ideContainer).gridTemplateColumns.split(' ');
            const sidebarSize = currentCols[0] || '300px';
            ideContainer.style.gridTemplateColumns = `${sidebarSize} 1fr ${newSize}px`;
        } else if (currentHandle === 'terminal') {
            const delta = startPos - e.clientY;
            const newSize = Math.max(100, Math.min(400, startSize + delta));
            ideContainer.style.gridTemplateRows = `1fr ${newSize}px`;
        }
        
        // Trigger Monaco editor resize
        if (window.ide && window.ide.editor) {
            window.ide.editor.layout();
        }
    });
    
    // Mouse up handler
    document.addEventListener('mouseup', () => {
        if (isResizing) {
            isResizing = false;
            currentHandle = null;
            document.body.style.cursor = '';
            document.body.classList.remove('resizing');
            
            // Remove dragging class from all handles
            sidebarHandle.classList.remove('dragging');
            chatHandle.classList.remove('dragging');
            terminalHandle.classList.remove('dragging');
        }
    });
}