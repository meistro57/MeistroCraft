# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

MeistroCraft is a multi-agent AI development orchestrator with dual interfaces:

### 🌐 Web IDE Mode (Primary Interface)
- **Backend**: FastAPI server (`web_server.py`) with WebSocket handlers
- **Frontend**: Vanilla JavaScript (`static/js/ide.js`) with Monaco Editor
- **Template**: Jinja2 HTML template (`templates/ide.html`) with CSS Grid layout

### ⚡ CLI Mode (Command Line Interface)
- **Main Orchestrator**: `main.py` - coordinates GPT-4 planning + Claude execution
- **Interactive UI**: `interactive_ui.py` - split terminal with Rich library
- **Session Management**: Persistent sessions with context preservation

## Key Development Commands

### Starting the Application
```bash
# Recommended: Auto-setup with venv
python3 start_ide.py

# Alternative startup scripts
./start_ide.sh      # Linux/macOS
start_ide.bat       # Windows

# Manual web server (requires venv activation)
python3 web_server.py
```

### Development Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/macOS
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Testing
```bash
# Run specific test suites
python3 test_github_integration.py        # GitHub API integration
python3 test_github_optimization.py       # Performance optimization
python3 test_phase3_cicd.py               # CI/CD pipeline features
python3 test_naming.py                    # AI naming agent
```

## Core Architecture Patterns

### 1. Dual-Agent System
The system uses **GPT-4 for strategic planning** and **Claude for code execution**:

```python
# Task generation (GPT-4)
task = generate_task_with_gpt4(user_request, config, project_folder, token_tracker, session_id)

# Task execution (Claude CLI)
result = run_claude_task(task, config, session_id, session_manager, project_folder, token_tracker)
```

### 2. WebSocket Communication Pattern
Real-time communication between browser and server:

```javascript
// Frontend sends context-aware messages
{
    type: 'chat',
    content: "user message",
    context: {
        tab_id: "current-tab-id",
        tab_title: "filename.js",
        language: "javascript",
        is_file: true,
        file_path: "/path/to/file",
        content_preview: "first 500 chars..."
    }
}

// Backend streams responses
{
    type: "chat_response_chunk",
    session_id: "session-id",
    timestamp: "2025-07-14T...",
    chunk: "response text"
}

// Canvas preview updates
{
    type: "canvas_preview_update",
    tab_id: "tab-id",
    preview_type: "canvas",
    content: "canvas code",
    timestamp: "2025-07-14T..."
}
```

### 3. Session Management Architecture
Each web session maps to an isolated MeistroCraft session:

```python
# Session isolation pattern
class WebSessionManager:
    def __init__(self):
        self.sessions: Dict[str, str] = {}  # web_session_id -> meistrocraft_session_id
        self.websockets: Dict[str, WebSocket] = {}
        
    async def create_session(self, session_id: str) -> str:
        # Creates isolated project folder in projects/
        # Returns MeistroCraft session ID
```

### 4. Security Model
All file operations are restricted to the `projects/` directory:

```python
# Security validation pattern
projects_root = Path("projects").resolve()
requested_path = (projects_root / user_path).resolve()

# Ensure path is within projects directory
try:
    requested_path.relative_to(projects_root)
except ValueError:
    raise HTTPException(status_code=403, detail="Access denied")
```

## Key Integration Points

### Monaco Editor Integration
The IDE uses Monaco Editor with automatic language detection:

```javascript
// Editor initialization pattern
this.editor = monaco.editor.create(document.getElementById('editor'), {
    value: content,
    language: detectLanguage(fileName),
    theme: 'vs-dark',
    automaticLayout: true
});

// Context preservation
this.editor.onDidChangeModelContent(() => {
    this.handleCodeChange();
    this.markTabModified();
});
```

### Canvas Preview Integration
The IDE includes sophisticated canvas preview capabilities for graphics programming:

```javascript
// Canvas preview detection pattern
getPreviewType(content, filePath) {
    // Auto-detect canvas code
    if (content.includes('<canvas') || (content.includes('canvas') && content.includes('getContext'))) {
        return 'canvas';
    }
    // ... other preview types
}

// Canvas rendering pattern
renderCanvasPreview(container, content, fileName) {
    const canvasId = `canvas-preview-${Date.now()}`;
    
    // Create canvas environment
    const canvasHTML = `
        <canvas id="${canvasId}" width="800" height="600"></canvas>
        <div class="canvas-controls">
            <button onclick="window.ide.refreshCanvasPreview('${canvasId}')">🔄 Refresh</button>
            <button onclick="window.ide.clearCanvas('${canvasId}')">🗑️ Clear</button>
        </div>
    `;
    
    container.innerHTML = canvasHTML;
    
    // Execute canvas code safely
    this.executeCanvasCode(content, canvasId);
}

// Safe canvas code execution
executeCanvasCode(code, canvasId) {
    try {
        const canvas = document.getElementById(canvasId);
        const ctx = canvas.getContext('2d');
        
        // Sandboxed execution
        const wrappedCode = `
            (function() {
                const canvas = document.getElementById('${canvasId}');
                const ctx = canvas ? canvas.getContext('2d') : null;
                if (!ctx) return;
                
                ${code}
            })();
        `;
        
        eval(wrappedCode);
    } catch (error) {
        // Error handling with canvas feedback
        this.displayCanvasError(canvasId, error);
    }
}
```

#### Canvas Preview Features
- **Live Rendering**: Code executes in real-time as you edit
- **Interactive Controls**: Refresh and clear buttons for canvas manipulation
- **Smart Detection**: Automatically detects canvas code in HTML and JavaScript
- **Error Handling**: Safe execution with visual error feedback
- **Multiple Formats**: Supports both standalone JavaScript and HTML with canvas

### GitHub Integration
Comprehensive GitHub API integration with automatic workflow creation:

```python
# GitHub workflow pattern
# Successful tasks → Create PRs
# Failed tasks → Create GitHub issues
# Branch naming: meistrocraft/{session-id}/{action}-{filename}

# Available commands:
python main.py --github repos                   # List repositories
python main.py --github workflow owner/repo     # Analyze repository health
python main.py --github-interactive             # Interactive GitHub shell
```

### AI Naming Agent
Creative project naming using GPT-4:

```python
# Instead of "create_a_binary_calculator_usi"
# Generates: "bin-calc", "sky-cast", "task-flow"
project_name = generate_creative_project_name(description)
```

## Configuration Management

### Primary Config: `config/config.json`
```json
{
  "openai_api_key": "sk-your-openai-key",
  "anthropic_api_key": "sk-ant-your-anthropic-key",
  "github_api_key": "ghp-your-github-token",
  "openai_model": "gpt-4-0613",
  "claude_model": "claude-sonnet-4-20250514",
  "allowed_tools": ["Read", "Write", "Bash", "Edit", "Glob", "Grep"],
  "permission_mode": "acceptEdits",
  "max_turns": 5,
  "token_limits": {
    "daily_token_limit": 100000,
    "daily_cost_limit_usd": 50.0
  }
}
```

### Environment Variables (Production)
```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"
export GITHUB_API_KEY="your-github-token"
```

## File Structure Understanding

### Critical Files
- `main.py` - Core orchestrator with dual-agent coordination
- `web_server.py` - FastAPI backend with WebSocket handlers
- `static/js/ide.js` - Frontend JavaScript with Monaco Editor
- `templates/ide.html` - Main UI template with CSS Grid layout
- `interactive_ui.py` - CLI interface with Rich library

### Key Directories
- `projects/` - Sandboxed user projects (security boundary)
- `config/` - Configuration files and API keys
- `sessions/` - Persistent session storage
- `static/` - Web assets (JS, CSS, images)
- `templates/` - Jinja2 HTML templates

## Development Patterns

### Adding New WebSocket Handlers
```python
# Pattern for new message types in web_server.py
async def handle_websocket_message(websocket: WebSocket, session_id: str, message: Dict[str, Any]):
    message_type = message.get("type")
    
    if message_type == "new_message_type":
        # Always ensure session initialization
        meistrocraft_session_id = await session_manager.create_session(session_id)
        
        try:
            # Handler logic here
            response = {"type": "response_type", "data": result}
        except Exception as e:
            response = {"type": "error", "error": str(e)}
        
        await websocket.send_text(json.dumps(response))
```

### Adding New Frontend Features
```javascript
// Pattern for new IDE features
class MeistroCraftIDE {
    initNewFeature() {
        // Feature initialization
    }
    
    handleNewFeature(data) {
        // Send to backend via WebSocket
        this.ws.send(JSON.stringify({
            type: 'new_feature',
            data: data,
            context: this.getActiveTabContext()
        }));
    }
}
```

### Token Tracking Integration
```python
# Pattern for new API integrations
if token_tracker and response.get("usage"):
    usage = TokenUsage.from_response(response, model, session_id, "operation_type")
    token_tracker.track_usage(usage)
```

## Testing Patterns

### Integration Testing
```python
# Pattern for testing GitHub integration
def test_github_operation():
    client = create_github_client(config)
    result = client.some_operation()
    assert result.get("success") == True
```

### Performance Testing
```python
# Pattern for performance benchmarks
def benchmark_operation():
    start_time = time.time()
    result = perform_operation()
    execution_time = time.time() - start_time
    assert execution_time < expected_threshold
```

## Self-Optimization System

The system includes intelligent self-optimization:

```python
# Commands for optimization
python main.py --optimize analyze               # Analyze performance
python main.py --optimize apply                # Apply optimizations
python main.py --optimize history              # View optimization history
```

## Debugging and Logging

### Comprehensive Logging
The system includes detailed logging for AI interactions:

```python
# Logging pattern for AI operations
print(f"🤖 [GPT-4] Processing user request: {request[:200]}...")
print(f"🔮 [Claude] Executing task: {task['action']}")
print(f"📊 [Session] Total tokens: {total_tokens}, Cost: ${cost:.4f}")
```

### Common Debug Commands
```bash
# Check system status
python main.py --github status
python main.py --token-usage
python main.py --sessions

# Performance monitoring
python main.py --performance benchmark
```

This architecture emphasizes security through sandboxing, real-time communication via WebSockets, and dual-agent AI coordination for optimal code generation and execution.