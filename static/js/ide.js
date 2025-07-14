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
        
        // Add debugging function
        window.debugTabs = () => {
            console.log('Open tabs:', Array.from(this.openTabs.keys()));
            console.log('Active tab:', this.activeTab);
            console.log('Tab elements:', document.querySelectorAll('.editor-tab[data-tab]'));
        };
        
        // Initialize notification system
        this.initNotificationSystem();
        
        // Start Winamp-style UI animations
        this.startUIAnimations();
        
        // Load API configuration status
        this.loadAPIConfig();
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
            
            // Initialize welcome tab (register existing HTML tab)
            const welcomeContent = `# Welcome to MeistroCraft IDE
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
`;
            
            // Register the existing welcome tab instead of creating a new one
            this.openTabs.set('welcome', {
                id: 'welcome',
                title: 'Welcome',
                icon: '📝',
                content: welcomeContent,
                isFile: false,
                filePath: null,
                modified: false,
                language: 'markdown'
            });
            
            // Set welcome as active tab
            this.activeTab = 'welcome';
            
            // Update editor with welcome content
            if (this.editor) {
                this.editor.setValue(welcomeContent);
                monaco.editor.setModelLanguage(this.editor.getModel(), 'markdown');
            }
            
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
                // Show AI processing indicator
                this.showAIProcessing(true);
                this.showChatTyping(true);
                
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
                // Hide AI processing indicators
                this.showAIProcessing(false);
                this.showChatTyping(false);
                
                // Finalize AI response
                this.currentAIMessage = null;
                this.currentAIResponseContent = null;
                // Update token count if available
                if (message.total_tokens) {
                    this.updateTokenCount(message.total_tokens, message.cost);
                    this.requestCount++;
                    this.sessionTokens += message.total_tokens;
                    this.sessionCost += message.cost;
                    
                    // Update progress bar
                    this.updateCostProgress();
                    
                    // Show notification
                    // Token usage info logged silently
                    console.log(`Tokens used: ${message.total_tokens} (Cost: $${message.cost?.toFixed(4) || '0.0000'})`);
                }
                
                // Refresh task queue to show any new tasks
                setTimeout(() => {
                    this.refreshTasks();
                }, 1000);
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
        
        // Load initial task queue
        setTimeout(() => {
            this.refreshTasks();
            
            // Set up periodic task refresh every 30 seconds
            setInterval(() => {
                this.refreshTasks();
            }, 30000);
        }, 2000); // Wait for websocket connection to be established
        
        // Setup existing welcome tab functionality
        this.setupExistingTabs();
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
            <span class="tab-close">&times;</span>
        `;
        
        // Add click handler for the tab (but not close button)
        tabElement.addEventListener('click', (e) => {
            if (!e.target.classList.contains('tab-close')) {
                this.switchTab(id);
            }
        });
        
        // Add specific click handler for close button
        const closeButton = tabElement.querySelector('.tab-close');
        closeButton.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent tab switch
            this.closeTab(id);
        });
        
        // Add to tab list
        const tabList = document.getElementById('tabList');
        tabList.appendChild(tabElement);
        
        // Switch to new tab
        this.switchTab(id);
        
        return tab;
    }
    
    switchTab(tabId) {
        console.log(`Switching to tab: ${tabId}`, this.openTabs.has(tabId));
        
        if (!this.openTabs.has(tabId)) {
            console.warn(`Tab ${tabId} not found in openTabs:`, Array.from(this.openTabs.keys()));
            return;
        }
        
        // Update UI
        document.querySelectorAll('.editor-tab').forEach(tab => {
            tab.classList.remove('active');
        });
        
        const targetTab = document.querySelector(`[data-tab="${tabId}"]`);
        if (targetTab) {
            targetTab.classList.add('active');
            console.log(`Tab UI updated for: ${tabId}`);
        } else {
            console.warn(`Tab element not found for: ${tabId}`);
        }
        
        // Update editor content
        const tab = this.openTabs.get(tabId);
        this.activeTab = tabId;
        
        if (this.editor && tab) {
            this.editor.setValue(tab.content || '');
            monaco.editor.setModelLanguage(this.editor.getModel(), tab.language || 'plaintext');
            console.log(`Editor updated with content for: ${tabId}`);
        } else {
            console.warn(`Editor or tab content not available for: ${tabId}`);
        }
        
        // Update preview if enabled
        if (this.previewMode) {
            this.updatePreview();
        }
    }
    
    closeTab(tabId) {
        console.log(`Closing tab: ${tabId}`);
        
        if (this.openTabs.size <= 1) {
            console.log('Cannot close last tab');
            return; // Keep at least one tab
        }
        
        const tab = this.openTabs.get(tabId);
        if (!tab) {
            console.warn(`Tab ${tabId} not found for closing`);
            return;
        }
        
        if (tab.modified) {
            if (!confirm(`"${tab.title}" has unsaved changes. Close anyway?`)) {
                return;
            }
        }
        
        // Remove from tabs
        this.openTabs.delete(tabId);
        console.log(`Removed tab ${tabId} from openTabs`);
        
        // Remove tab element
        const tabElement = document.querySelector(`[data-tab="${tabId}"]`);
        if (tabElement) {
            tabElement.remove();
            console.log(`Removed tab element for ${tabId}`);
        }
        
        // Switch to another tab if this was active
        if (this.activeTab === tabId) {
            const remainingTabs = Array.from(this.openTabs.keys());
            console.log(`Remaining tabs:`, remainingTabs);
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
        // Open preview in new popup window instead of inline
        this.openPreviewWindow();
    }
    
    openPreviewWindow() {
        if (!this.activeTab) {
            alert('No file is currently open to preview');
            return;
        }
        
        const tab = this.openTabs.get(this.activeTab);
        if (!tab) return;
        
        const content = tab.content;
        const fileName = tab.title;
        const filePath = tab.filePath || '';
        
        // Detect preview type
        const previewType = this.detectPreviewType(filePath, content);
        
        // Generate preview content
        let previewHTML = '';
        switch (previewType) {
            case 'markdown':
                previewHTML = this.renderMarkdown(content);
                break;
            case 'html':
                previewHTML = content;
                break;
            case 'text':
            default:
                previewHTML = `<pre style="white-space: pre-wrap; font-family: 'Consolas', monospace; margin: 0;">${this.escapeHtml(content)}</pre>`;
                break;
        }
        
        // Create popup window with scrolling capability
        const previewWindow = window.open('', '_blank', 'width=800,height=600,scrollbars=yes,resizable=yes,location=no,menubar=no,toolbar=no');
        
        if (!previewWindow) {
            alert('Please allow popups for this site to open the preview window');
            return;
        }
        
        // Write the complete HTML document to the popup
        previewWindow.document.write(`
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Preview: ${fileName}</title>
                <style>
                    body {
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        background: #1e1e1e;
                        color: #d4d4d4;
                        margin: 0;
                        padding: 20px;
                        line-height: 1.6;
                        overflow-x: auto;
                        overflow-y: auto;
                    }
                    
                    h1, h2, h3, h4, h5, h6 {
                        color: #ffffff;
                        margin-top: 1.5em;
                        margin-bottom: 0.5em;
                    }
                    
                    h1 { border-bottom: 2px solid #007acc; padding-bottom: 0.3em; }
                    h2 { border-bottom: 1px solid #3e3e42; padding-bottom: 0.3em; }
                    
                    code {
                        background: #2d2d30;
                        padding: 2px 6px;
                        border-radius: 3px;
                        font-family: 'Consolas', 'Monaco', monospace;
                        color: #ce9178;
                    }
                    
                    pre {
                        background: #2d2d30;
                        padding: 16px;
                        border-radius: 6px;
                        overflow-x: auto;
                        border: 1px solid #3e3e42;
                        font-family: 'Consolas', 'Monaco', monospace;
                    }
                    
                    pre code {
                        background: none;
                        padding: 0;
                    }
                    
                    blockquote {
                        border-left: 4px solid #007acc;
                        margin: 0;
                        padding-left: 16px;
                        color: #a6a6a6;
                    }
                    
                    table {
                        border-collapse: collapse;
                        width: 100%;
                        margin: 1em 0;
                    }
                    
                    th, td {
                        border: 1px solid #3e3e42;
                        padding: 8px 12px;
                        text-align: left;
                    }
                    
                    th {
                        background: #2d2d30;
                        font-weight: bold;
                    }
                    
                    a {
                        color: #007acc;
                        text-decoration: none;
                    }
                    
                    a:hover {
                        text-decoration: underline;
                    }
                    
                    .preview-header {
                        position: sticky;
                        top: 0;
                        background: #2d2d30;
                        padding: 10px 20px;
                        margin: -20px -20px 20px -20px;
                        border-bottom: 1px solid #3e3e42;
                        font-weight: bold;
                        color: #ffffff;
                        z-index: 1000;
                    }
                    
                    .preview-content {
                        max-width: none;
                        word-wrap: break-word;
                        overflow-wrap: break-word;
                    }
                    
                    /* Scrollbar styling for webkit browsers */
                    ::-webkit-scrollbar {
                        width: 12px;
                        height: 12px;
                    }
                    
                    ::-webkit-scrollbar-track {
                        background: #2d2d30;
                    }
                    
                    ::-webkit-scrollbar-thumb {
                        background: #007acc;
                        border-radius: 6px;
                    }
                    
                    ::-webkit-scrollbar-thumb:hover {
                        background: #0086d3;
                    }
                </style>
            </head>
            <body>
                <div class="preview-header">
                    📄 ${fileName} - Live Preview
                </div>
                <div class="preview-content">
                    ${previewHTML}
                </div>
                
                <script>
                    // Auto-refresh functionality (optional)
                    let lastContent = ${JSON.stringify(content)};
                    
                    // Focus the window
                    window.focus();
                    
                    // Handle window close
                    window.addEventListener('beforeunload', function() {
                        // Cleanup if needed
                    });
                </script>
            </body>
            </html>
        `);
        
        previewWindow.document.close();
        
        // Store reference for potential updates
        this.previewWindow = previewWindow;
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
    
    setupExistingTabs() {
        // Setup event listeners for existing tabs in HTML
        const existingTabs = document.querySelectorAll('.editor-tab[data-tab]');
        existingTabs.forEach(tabElement => {
            const tabId = tabElement.getAttribute('data-tab');
            
            // Add click handler for tab switching
            tabElement.addEventListener('click', (e) => {
                if (!e.target.classList.contains('tab-close')) {
                    this.switchTab(tabId);
                }
            });
            
            // Add click handler for close button
            const closeButton = tabElement.querySelector('.tab-close');
            if (closeButton) {
                closeButton.addEventListener('click', (e) => {
                    e.stopPropagation(); // Prevent tab switch
                    this.closeTab(tabId);
                });
            }
        });
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
                    
                    // Show file activity
                    this.addFileActivity(path, 'opened');
                }
            } else if (operation === 'write' || operation === 'create') {
                // Show file creation/modification activity
                this.addFileActivity(path, operation === 'create' ? 'created' : 'modified');
                this.showNotification('success', `File ${operation === 'create' ? 'created' : 'modified'}: ${path}`);
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
        
        if (tasks.length === 0) {
            taskList.innerHTML = `
                <div class="task-item empty-state">
                    <span class="task-icon">💤</span>
                    <span class="task-name">No recent tasks</span>
                    <span class="task-time">Start a conversation to see tasks here</span>
                </div>
            `;
            return;
        }
        
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
            
            // Refresh settings UI when settings tab is opened
            this.updateSettingsUI();
            
            // Check API status when settings tab is opened
            this.checkInitialAPIStatus();
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
            githubKey: '',
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
        const terminalContainer = document.querySelector('.terminal-container');
        const terminalOutput = document.getElementById('terminalOutput');
        const terminalInput = document.getElementById('terminalInput');
        
        if (terminalContainer) {
            terminalContainer.style.fontFamily = this.settings.terminalFont;
            terminalContainer.style.fontSize = this.settings.terminalFontSize + 'px';
        }
        if (terminalOutput) {
            terminalOutput.style.fontFamily = this.settings.terminalFont;
            terminalOutput.style.fontSize = this.settings.terminalFontSize + 'px';
        }
        if (terminalInput) {
            terminalInput.style.fontFamily = this.settings.terminalFont;
            terminalInput.style.fontSize = this.settings.terminalFontSize + 'px';
        }
        
        // Update UI elements
        this.updateSettingsUI();
    }
    
    updateSettingsUI() {
        // Update all form elements with current settings
        const openaiKeyField = document.getElementById('openaiKey');
        const anthropicKeyField = document.getElementById('anthropicKey');
        const githubKeyField = document.getElementById('githubKey');
        const defaultModelField = document.getElementById('defaultModel');
        
        if (openaiKeyField) openaiKeyField.value = this.settings.openaiKey || '';
        if (anthropicKeyField) anthropicKeyField.value = this.settings.anthropicKey || '';
        if (githubKeyField) githubKeyField.value = this.settings.githubKey || '';
        if (defaultModelField) defaultModelField.value = this.settings.defaultModel || 'gpt-4';
        
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
            // Apply font size change immediately
            this.settings.fontSize = parseInt(e.target.value);
            if (this.editor) {
                this.editor.updateOptions({
                    fontSize: this.settings.fontSize
                });
            }
        });
        
        document.getElementById('terminalFontSize').addEventListener('input', (e) => {
            document.getElementById('terminalFontSizeValue').textContent = e.target.value + 'px';
            // Apply terminal font size change immediately
            this.settings.terminalFontSize = parseInt(e.target.value);
            const terminalContainer = document.querySelector('.terminal-container');
            const terminalOutput = document.getElementById('terminalOutput');
            const terminalInput = document.getElementById('terminalInput');
            
            if (terminalContainer) {
                terminalContainer.style.fontSize = this.settings.terminalFontSize + 'px';
            }
            if (terminalOutput) {
                terminalOutput.style.fontSize = this.settings.terminalFontSize + 'px';
            }
            if (terminalInput) {
                terminalInput.style.fontSize = this.settings.terminalFontSize + 'px';
            }
        });
    }
    
    async saveSettings() {
        // Collect all settings from UI
        this.settings = {
            openaiKey: document.getElementById('openaiKey').value,
            anthropicKey: document.getElementById('anthropicKey').value,
            githubKey: document.getElementById('githubKey').value,
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
        
        // Save API configuration to backend if any API keys are provided
        const apiConfig = {};
        if (this.settings.openaiKey && this.settings.openaiKey.trim() !== '') {
            apiConfig.openai_api_key = this.settings.openaiKey;
        }
        if (this.settings.anthropicKey && this.settings.anthropicKey.trim() !== '') {
            apiConfig.anthropic_api_key = this.settings.anthropicKey;
        }
        if (this.settings.githubKey && this.settings.githubKey.trim() !== '') {
            apiConfig.github_api_key = this.settings.githubKey;
        }
        if (this.settings.defaultModel) {
            if (this.settings.defaultModel.startsWith('gpt-')) {
                apiConfig.openai_model = this.settings.defaultModel;
            } else if (this.settings.defaultModel.startsWith('claude-')) {
                apiConfig.claude_model = this.settings.defaultModel;
            }
        }
        
        // Save API config to backend if we have any API keys
        if (Object.keys(apiConfig).length > 0) {
            try {
                const response = await fetch('/api/config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(apiConfig)
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                const result = await response.json();
                console.log('API configuration saved:', result);
            } catch (error) {
                console.error('Error saving API configuration:', error);
                this.addChatMessage('system', `Error saving API configuration: ${error.message}`);
                return; // Don't show success if API config failed
            }
        }
        
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
        // Notifications disabled - generic popups removed
        return;
        
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
    
    // Winamp-style UI Enhancement Methods
    showAIProcessing(show) {
        const indicator = document.getElementById('aiStatusIndicator');
        if (indicator) {
            indicator.style.display = show ? 'block' : 'none';
        }
    }
    
    showChatTyping(show) {
        // Remove existing typing indicator
        const existing = document.querySelector('.chat-typing');
        if (existing) {
            existing.remove();
        }
        
        if (show) {
            const chatMessages = document.getElementById('chatMessages');
            const typingDiv = document.createElement('div');
            typingDiv.className = 'chat-typing';
            typingDiv.innerHTML = `
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <span style="margin-left: 8px; color: #00ff00;">AI is thinking...</span>
            `;
            chatMessages.appendChild(typingDiv);
            
            // Auto-scroll
            setTimeout(() => {
                chatMessages.scrollTop = chatMessages.scrollHeight;
            }, 10);
        }
    }
    
    updateCostProgress() {
        const progressBar = document.getElementById('costProgress');
        const dailyLimit = this.settings?.dailyLimit || 5.0;
        const percentage = Math.min(100, (this.sessionCost / dailyLimit) * 100);
        
        if (progressBar) {
            progressBar.style.width = `${percentage}%`;
            
            // Change color based on usage
            if (percentage > 80) {
                progressBar.style.background = 'linear-gradient(90deg, #ff0000, #ff8800)';
            } else if (percentage > 60) {
                progressBar.style.background = 'linear-gradient(90deg, #ffff00, #ff8800)';
            } else {
                progressBar.style.background = 'linear-gradient(90deg, #00ff00, #ffff00, #ff00ff)';
            }
        }
    }
    
    // Enhanced file tree with activity indicators
    addFileActivity(filePath, activityType) {
        const fileItems = document.querySelectorAll('.file-tree li');
        fileItems.forEach(item => {
            if (item.getAttribute('data-path')?.includes(filePath)) {
                // Add activity indicator
                if (!item.querySelector('.notification-badge')) {
                    const badge = document.createElement('span');
                    badge.className = 'notification-badge';
                    badge.textContent = activityType === 'modified' ? '●' : '+';
                    badge.style.position = 'relative';
                    badge.style.top = 'auto';
                    badge.style.right = 'auto';
                    badge.style.marginLeft = '5px';
                    item.appendChild(badge);
                    
                    // Remove after 3 seconds
                    setTimeout(() => {
                        if (badge.parentNode) {
                            badge.parentNode.removeChild(badge);
                        }
                    }, 3000);
                }
            }
        });
    }
    
    // Simulate CPU usage (for visual effect)
    simulateCPUActivity() {
        const cpuBars = document.querySelectorAll('.cpu-bar');
        cpuBars.forEach((bar, index) => {
            const height = Math.random() * 100;
            const delay = Math.random() * 0.5;
            bar.style.height = `${height}%`;
            bar.style.animationDelay = `${delay}s`;
        });
    }
    
    // Start continuous UI animations
    startUIAnimations() {
        // Simulate CPU activity every 2 seconds
        this.cpuInterval = setInterval(() => {
            this.simulateCPUActivity();
        }, 2000);
        
        // Random activity bursts
        this.activityInterval = setInterval(() => {
            if (Math.random() > 0.7) {
                this.showRandomActivity();
            }
        }, 5000);
    }
    
    showRandomActivity() {
        const activities = [
            'File indexing...',
            'Memory optimization...',
            'Cache refresh...',
            'Syntax analysis...',
            'Background compilation...'
        ];
        
        const activity = activities[Math.floor(Math.random() * activities.length)];
        this.showNotification('info', activity, 2000);
    }
    
    // Enhanced token display with effects
    updateTokenCount(tokens, cost) {
        // Update token and cost display with animation
        const tokenElement = document.getElementById('tokenCount');
        const costElement = document.getElementById('costAmount');
        
        if (tokenElement) {
            const currentTokens = parseInt(tokenElement.textContent) || 0;
            const newTokens = currentTokens + tokens;
            
            // Animate count up
            this.animateNumber(tokenElement, currentTokens, newTokens);
        }
        
        if (costElement && cost) {
            const currentCost = parseFloat(costElement.textContent) || 0;
            const newCost = currentCost + cost;
            
            // Animate cost up
            this.animateNumber(costElement, currentCost, newCost, 3);
        }
    }
    
    animateNumber(element, start, end, decimals = 0) {
        const duration = 1000; // 1 second
        const startTime = Date.now();
        
        const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            const current = start + (end - start) * progress;
            element.textContent = decimals > 0 ? current.toFixed(decimals) : Math.floor(current);
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        animate();
    }
    
    // API Configuration Management
    async testAPIKey(provider) {
        const statusElement = document.getElementById(`${provider}Status`);
        const indicatorElement = statusElement.querySelector('.status-indicator');
        const textElement = statusElement.querySelector('.status-text');
        const testButton = document.querySelector(`button[onclick="testAPIKey('${provider}')"]`);
        
        // Set testing state
        indicatorElement.className = 'status-indicator status-testing';
        textElement.textContent = 'Testing...';
        testButton.disabled = true;
        
        try {
            const apiKey = document.getElementById(`${provider}Key`).value;
            
            if (!apiKey || apiKey.trim() === '') {
                throw new Error('API key is empty');
            }
            
            // Send test request to backend
            const response = await fetch('/api/test-api-key', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    provider: provider,
                    api_key: apiKey
                })
            });
            
            if (!response.ok) {
                // Handle HTTP error responses
                let errorMessage = `HTTP ${response.status}`;
                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || errorMessage;
                } catch (e) {
                    // If we can't parse JSON, use status text
                    errorMessage = response.statusText || errorMessage;
                }
                throw new Error(errorMessage);
            }
            
            const result = await response.json();
            
            if (result.status === 'valid') {
                indicatorElement.className = 'status-indicator status-valid';
                textElement.textContent = 'Valid';
                this.showNotification('success', `${provider} API key is valid!`);
            } else {
                indicatorElement.className = 'status-indicator status-invalid';
                textElement.textContent = 'Invalid';
                const errorMessage = result.message || 'Unknown error';
                this.showNotification('error', `${provider} API key is invalid: ${errorMessage}`);
            }
        } catch (error) {
            indicatorElement.className = 'status-indicator status-invalid';
            textElement.textContent = 'Error';
            this.showNotification('error', `Error testing ${provider} API key: ${error.message}`);
        } finally {
            testButton.disabled = false;
        }
    }
    
    async checkAllAPIKeys() {
        await Promise.all([
            this.testAPIKey('openai'),
            this.testAPIKey('anthropic'),
            this.testAPIKey('github')
        ]);
    }
    
    async loadAPIConfig() {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                
                // Update OpenAI status
                if (config.openai.configured) {
                    this.updateAPIStatus('openai', 'valid', `Configured (${config.openai.model})`);
                    document.getElementById('openaiKey').placeholder = 'sk-...(configured)';
                } else {
                    this.updateAPIStatus('openai', 'invalid', 'Not Configured');
                    document.getElementById('openaiKey').placeholder = 'sk-...';
                }
                
                // Update Anthropic status
                if (config.anthropic.configured) {
                    this.updateAPIStatus('anthropic', 'valid', `Configured (${config.anthropic.model})`);
                    document.getElementById('anthropicKey').placeholder = 'sk-ant-...(configured)';
                } else {
                    this.updateAPIStatus('anthropic', 'invalid', 'Not Configured');
                    document.getElementById('anthropicKey').placeholder = 'sk-ant-...';
                }
                
                this.showNotification('info', 'API configuration loaded');
            } else {
                throw new Error('Failed to load configuration');
            }
        } catch (error) {
            console.error('Error loading API config:', error);
            this.updateAPIStatus('openai', 'unknown', 'Error');
            this.updateAPIStatus('anthropic', 'unknown', 'Error');
            this.showNotification('error', 'Failed to load API configuration');
        }
    }
    
    updateAPIStatus(provider, status, text) {
        const statusElement = document.getElementById(`${provider}Status`);
        if (statusElement) {
            const indicatorElement = statusElement.querySelector('.status-indicator');
            const textElement = statusElement.querySelector('.status-text');
            
            if (indicatorElement) {
                indicatorElement.className = `status-indicator status-${status}`;
            }
            if (textElement) {
                textElement.textContent = text;
            }
        }
    }
    
    async loadConfigFromBackend() {
        try {
            const response = await fetch('/api/config');
            if (response.ok) {
                const config = await response.json();
                
                // Update API key fields based on the actual API response format
                if (config.openai?.configured) {
                    document.getElementById('openaiKey').placeholder = 'sk-...(configured)';
                    this.updateAPIStatus('openai', 'valid', 'Configured');
                    // Update default model if available
                    if (config.openai.model) {
                        document.getElementById('defaultModel').value = config.openai.model;
                    }
                    // Clear the input since it's already configured
                    document.getElementById('openaiKey').value = '';
                } else {
                    document.getElementById('openaiKey').placeholder = 'sk-...';
                    this.updateAPIStatus('openai', 'invalid', 'Not Set');
                }
                
                if (config.anthropic?.configured) {
                    document.getElementById('anthropicKey').placeholder = 'sk-ant-...(configured)';
                    this.updateAPIStatus('anthropic', 'valid', 'Configured');
                    // Clear the input since it's already configured
                    document.getElementById('anthropicKey').value = '';
                } else {
                    document.getElementById('anthropicKey').placeholder = 'sk-ant-...';
                    this.updateAPIStatus('anthropic', 'invalid', 'Not Set');
                }
                
                if (config.github?.configured) {
                    document.getElementById('githubKey').placeholder = 'ghp_...(configured)';
                    this.updateAPIStatus('github', 'valid', 'Configured');
                    // Clear the input since it's already configured
                    document.getElementById('githubKey').value = '';
                } else {
                    document.getElementById('githubKey').placeholder = 'ghp_...';
                    this.updateAPIStatus('github', 'invalid', 'Not Set');
                }
                
                console.log('Configuration loaded:', config);
            } else {
                throw new Error('Failed to load backend configuration');
            }
        } catch (error) {
            console.error('Error loading backend config:', error);
            // Set default status when loading fails
            this.updateAPIStatus('openai', 'unknown', 'Unknown');
            this.updateAPIStatus('anthropic', 'unknown', 'Unknown');
            this.updateAPIStatus('github', 'unknown', 'Unknown');
        }
    }
    
    updateAPIStatus(provider, status, text) {
        const statusElement = document.getElementById(`${provider}Status`);
        const indicatorElement = statusElement.querySelector('.status-indicator');
        const textElement = statusElement.querySelector('.status-text');
        
        indicatorElement.className = `status-indicator status-${status}`;
        textElement.textContent = text;
    }
    
    // Check API status on settings load
    async checkInitialAPIStatus() {
        // Check if keys are already configured
        await this.loadConfigFromBackend();
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

// Tab switching functionality is no longer needed since tasks and terminal are separate containers

// Refresh tasks function
function refreshTasks() {
    console.log('Refreshing tasks...');
    // TODO: Implement actual task refresh via WebSocket/API
    if (window.ide) {
        window.ide.refreshTasks();
    }
}

// Tab functionality removed - tasks and terminal are now separate containers

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

function closeTab(tabId) {
    if (window.ide) {
        window.ide.closeTab(tabId);
    }
}

function switchTab(tabId) {
    if (window.ide) {
        window.ide.switchTab(tabId);
    }
}

function togglePreview() {
    if (window.ide) {
        window.ide.togglePreview();
    }
}

function testAPIKey(provider) {
    if (window.ide) {
        window.ide.testAPIKey(provider);
    }
}

function checkAllAPIKeys() {
    if (window.ide) {
        window.ide.checkAllAPIKeys();
    }
}

function loadConfigFromBackend() {
    if (window.ide) {
        window.ide.loadConfigFromBackend();
    }
}

// Initialize IDE when page loads
let ide;
document.addEventListener('DOMContentLoaded', () => {
    ide = new MeistroCraftIDE();
    window.ide = ide; // Make globally accessible
    
    // Initialize resize functionality
    // initializeResize(); // Disabled - using simple-resize.js instead
});

// Resize functionality
// Reset layout to defaults
function resetLayout() {
    const ideContainer = document.querySelector('.ide-container');
    if (ideContainer) {
        ideContainer.style.gridTemplateColumns = '300px 1fr 1fr 300px';
        ideContainer.style.gridTemplateRows = '1fr 200px';
        ideContainer.style.gridTemplateAreas = `
            "sidebar editor editor chat"
            "sidebar tasks terminal chat"
        `;
        
        // Reset chat handle position
        const chatHandle = document.getElementById('resizeChat');
        if (chatHandle) {
            chatHandle.style.right = 'calc(300px - 4px)';
        }
        
        console.log('Layout reset to defaults');
        
        // Trigger Monaco editor resize
        if (window.ide && window.ide.editor) {
            window.ide.editor.layout();
        }
    }
}

// Make reset function globally accessible for testing
window.resetLayout = resetLayout;

function initializeResize() {
    const ideContainer = document.querySelector('.ide-container');
    const sidebarHandle = document.getElementById('resizeSidebar');
    const chatHandle = document.getElementById('resizeChat');
    const terminalHandle = document.getElementById('resizeTerminal');
    const tasksHandle = document.getElementById('resizeTasks');
    
    console.log('Initializing resize...', {
        ideContainer,
        sidebarHandle,
        chatHandle,
        terminalHandle,
        tasksHandle
    });
    
    if (!ideContainer || !sidebarHandle || !chatHandle || !terminalHandle || !tasksHandle) {
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
        
        console.log('Chat resize start:', {
            startPos,
            cols,
            lastCol: cols[cols.length - 1],
            startSize
        });
        
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
    
    // Tasks resize (split between tasks and terminal)
    tasksHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'tasks';
        startPos = e.clientX;
        // Get current grid template and calculate tasks width
        const cols = window.getComputedStyle(ideContainer).gridTemplateColumns.split(' ');
        const middleSection = cols[1]; // Should be "1fr"
        startSize = ideContainer.offsetWidth - 300 - 300; // Total width minus sidebars
        tasksHandle.classList.add('dragging');
        document.body.style.cursor = 'col-resize';
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
            const chatSize = currentCols[3] || '300px';  // Chat is at index 3 in 4-column layout
            ideContainer.style.gridTemplateColumns = `${newSize}px 1fr 1fr ${chatSize}`;
            // Ensure grid areas are explicitly set to maintain layout
            ideContainer.style.gridTemplateAreas = `
                "sidebar editor editor chat"
                "sidebar tasks terminal chat"
            `;
        } else if (currentHandle === 'chat') {
            const delta = startPos - e.clientX;
            const newSize = Math.max(200, Math.min(600, startSize + delta));
            // Get current sidebar size to maintain it
            const currentCols = window.getComputedStyle(ideContainer).gridTemplateColumns.split(' ');
            const sidebarSize = currentCols[0] || '300px';
            
            console.log('Chat resize:', {
                delta,
                newSize,
                sidebarSize,
                currentCols,
                newTemplate: `${sidebarSize} 1fr 1fr ${newSize}px`
            });
            
            ideContainer.style.gridTemplateColumns = `${sidebarSize} 1fr 1fr ${newSize}px`;
            // Ensure grid areas are explicitly set to maintain layout
            ideContainer.style.gridTemplateAreas = `
                "sidebar editor editor chat"
                "sidebar tasks terminal chat"
            `;
            
            // Update the chat resize handle position
            const chatHandle = document.getElementById('resizeChat');
            if (chatHandle) {
                chatHandle.style.right = `calc(${newSize}px - 4px)`;
            }
            
            // Force layout recalculation
            ideContainer.offsetHeight;
            
            console.log('Applied grid template:', ideContainer.style.gridTemplateColumns);
        } else if (currentHandle === 'terminal') {
            const delta = startPos - e.clientY;
            const newSize = Math.max(100, Math.min(400, startSize + delta));
            ideContainer.style.gridTemplateRows = `1fr ${newSize}px`;
        } else if (currentHandle === 'tasks') {
            const delta = e.clientX - startPos;
            const totalBottomWidth = ideContainer.offsetWidth - 300 - 300; // Minus sidebars
            const newTasksWidth = Math.max(200, Math.min(totalBottomWidth - 200, startSize / 2 + delta));
            const newTerminalWidth = totalBottomWidth - newTasksWidth;
            
            // Update grid template to split the middle area
            const sidebarWidth = 300;
            const chatWidth = 300;
            ideContainer.style.gridTemplateColumns = `${sidebarWidth}px ${newTasksWidth}px ${newTerminalWidth}px ${chatWidth}px`;
            ideContainer.style.gridTemplateAreas = `
                "sidebar editor editor chat"
                "sidebar tasks terminal chat"
            `;
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
            tasksHandle.classList.remove('dragging');
        }
    });
}