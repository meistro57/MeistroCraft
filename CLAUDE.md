# MeistroCraft IDE - Technical Documentation for Claude

## Overview
MeistroCraft is a comprehensive AI-powered development orchestrator that operates in multiple modes:

1. **🌐 Browser IDE**: Modern web-based interface with VS Code-style editing, real-time AI assistance, and session management
2. **⚡ Command Line Interface**: Split terminal UI for interactive coding sessions with token tracking
3. **🤖 Orchestration Engine**: Multi-agent system combining GPT-4 strategic planning with Claude Code CLI execution
4. **🐙 GitHub Integration**: Complete workflow automation with PR/issue management and CI/CD pipeline integration
5. **🧠 Self-Optimization**: Automatic performance analysis and intelligent code refinement

## Architecture

### Core Components

#### 🌐 Web IDE Components

1. **Backend (FastAPI)** - `web_server.py`
   - WebSocket handlers for real-time communication
   - File system API with security restrictions (projects folder only)
   - Integration with existing MeistroCraft AI backend
   - Session management with project folder sandboxing
   - Auto-startup scripts with cross-platform support

2. **Frontend (Vanilla JS)** - `static/js/ide.js`
   - Monaco Editor integration for code editing
   - Tab management system for multiple files
   - WebSocket client for AI communication
   - File explorer with tree navigation

3. **UI Template** - `templates/ide.html`
   - CSS Grid layout with resizable panels
   - Dark theme VS Code-style interface
   - Status bar with token tracking

#### ⚡ Command Line Components

4. **Main Orchestrator** - `main.py`
   - Multi-agent coordination between GPT-4 and Claude
   - Session management and persistence
   - Token tracking and cost management
   - GitHub integration and workflow automation

5. **Interactive UI** - `interactive_ui.py`
   - Split terminal interface with Rich library
   - Real-time token display and status monitoring
   - Command palette and keyboard shortcuts

6. **GitHub Integration** - `github_client.py`, `github_workflows.py`
   - Complete GitHub API integration
   - Automated PR/issue creation
   - CI/CD pipeline monitoring
   - Repository health analysis

7. **Self-Optimization** - `self_optimizer.py`
   - Performance pattern recognition
   - Automatic code refinement suggestions
   - Persistent learning system

## Key Features

### File Management
- **Security**: All file operations restricted to `projects/` directory
- **Tree Navigation**: Hierarchical file explorer in sidebar
- **Tab System**: Multiple file editing with close/modified indicators
- **New File Creation**: Plus tab with language-specific templates

### AI Integration
- **Context Awareness**: AI receives current file context (path, language, content preview)
- **Streaming Responses**: Real-time response chunks via WebSocket
- **Backend Integration**: Uses existing MeistroCraft task generation (GPT-4) + execution (Claude)
- **Session Management**: Each web session maps to a MeistroCraft session with isolated project folder

### UI Layout (CSS Grid)
```css
grid-template-areas: 
    "sidebar editor chat"
    "sidebar terminal chat";
grid-template-columns: 300px 1fr 300px;
grid-template-rows: 1fr 200px;
```

### Resizable Panels
- **Handles**: Invisible dividers between panels with hover/drag states
- **Constraints**: Min/max sizes to prevent UI collapse
- **Editor Integration**: Monaco Editor automatically relayouts on resize

## File Structure

```
/home/mark/claude-coder/ai_coding_agent/
├── web_server.py              # FastAPI backend
├── templates/
│   └── ide.html              # Main UI template
├── static/
│   └── js/
│       └── ide.js            # Frontend JavaScript
├── projects/                 # Sandboxed user projects
├── config/                   # AI API configurations
└── main.py                   # Core MeistroCraft backend
```

## WebSocket Message Types

### Client → Server
- `chat`: AI assistance request with file context
- `command`: Terminal command execution
- `file_operation`: File read/write/list operations
- `get_tasks`: Request task queue status

### Server → Client
- `chat_response_chunk`: Streaming AI response
- `chat_response_complete`: End of AI response with token count
- `command_response`: Terminal command output
- `file_response`: File operation results

## Tab Management System

### Tab Data Structure
```javascript
{
    id: "unique-tab-id",
    title: "filename.js",
    icon: "📄",
    content: "file content",
    isFile: true,
    filePath: "/path/to/file",
    modified: false,
    language: "javascript"
}
```

### Key Methods
- `createTab()`: Create new tab with content
- `switchTab()`: Change active tab and update Monaco Editor
- `closeTab()`: Remove tab with unsaved changes warning
- `markTabModified()`: Visual indicator for unsaved changes

## AI Context System

When user sends chat message, frontend automatically includes:
```javascript
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
```

Backend enhances the message with file context before sending to AI.

## Session Management

1. **Web Session Creation**: Unique ID generated on page load
2. **MeistroCraft Session Mapping**: Web session maps to backend session
3. **Project Folder**: Each session gets isolated folder in `projects/`
4. **GitHub Integration**: Sessions automatically integrate with GitHub workflows
5. **Cleanup**: Folders removed when sessions deleted

## GitHub Integration (Phase 1 & 2 Complete)

### Automated Workflow Integration
- **Pull Request Creation**: Successful MeistroCraft tasks automatically create PRs
- **Issue Tracking**: Failed tasks automatically create GitHub issues
- **Smart Branch Naming**: Session-based branches (`meistrocraft/{session-id}/{action}-{filename}`)
- **Repository Health**: Workflow analysis and optimization recommendations

### Available GitHub Commands
```bash
# Repository operations
python main.py --github repos                   # List repositories
python main.py --github create my-repo          # Create repository
python main.py --github fork owner/repo         # Fork repository

# Workflow automation
python main.py --github prs owner/repo          # List pull requests
python main.py --github issues owner/repo       # List issues
python main.py --github workflow owner/repo     # Repository health analysis

# Interactive mode
python main.py --github-interactive             # GitHub shell
```

### Task-to-GitHub Integration
When MeistroCraft executes tasks, the system automatically:
1. **Successful Tasks** → Creates PR with comprehensive description and review checklist
2. **Failed Tasks** → Creates GitHub issue with error details and intelligent labeling
3. **Session Tracking** → Links all GitHub objects to MeistroCraft sessions for traceability

## Security Features

- **Path Traversal Protection**: All file operations validated against projects root
- **Sandboxing**: Each session isolated to its own project folder
- **Command Timeout**: Terminal commands limited to 30 seconds
- **File Size Limits**: 10MB max file size for safety

## Monaco Editor Integration

- **Language Detection**: Based on file extension
- **Theme**: VS Code dark theme
- **Auto-layout**: Responds to panel resizing
- **Change Detection**: Marks tabs as modified on edit

## Preview System

- **Markdown Rendering**: Real-time preview with syntax highlighting
- **HTML Display**: Live preview in iframe
- **Toggle Mode**: Split-screen or full editor view
- **Language Support**: Auto-detection based on file extension

## Debugging Common Issues

### Resizable Windows Not Working
1. Check if resize handles are positioned correctly in CSS
2. Verify event listeners are attached in `initializeResize()`
3. Ensure grid template updates are applied to correct element
4. Check browser console for JavaScript errors

### AI Context Not Working
1. Verify `getActiveTabContext()` returns valid data
2. Check WebSocket message includes context field
3. Ensure backend enhances content with file info

### File Operations Failing
1. Check if path is within projects directory
2. Verify file permissions and existence
3. Check for proper error handling in WebSocket responses

## Starting MeistroCraft

### 🌐 Web IDE Mode (Browser Interface)

```bash
# Automated startup (recommended)
python3 start_ide.py

# Or platform-specific scripts
./start_ide.sh     # Linux/macOS
start_ide.bat      # Windows

# Manual startup
python3 web_server.py

# Access at http://localhost:8000
```

### ⚡ Command Line Mode (CLI Interface)

```bash
# Basic example
./meistrocraft

# Single request
./meistrocraft --request "Create a calculator app"

# Interactive mode with split terminal
./meistrocraft --interactive

# GitHub operations
python main.py --github repos
python main.py --github workflow owner/repo

# Performance optimization
python main.py --optimize analyze
python main.py --performance benchmark
```

## Configuration

- **API Keys**: Set in `config/config.json`
- **Models**: GPT-4 for task generation, Claude for execution
- **Limits**: Token tracking and cost monitoring built-in

## Performance Notes

- **WebSocket Streaming**: 5ms delays for smooth chat scrolling
- **Monaco Layout**: Automatic resize on panel changes
- **File Loading**: Lazy loading for large directory trees
- **Memory Management**: Tab cleanup prevents memory leaks

This documentation provides the essential understanding needed to work with, debug, and extend the MeistroCraft IDE system.