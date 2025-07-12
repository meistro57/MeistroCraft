# MeistroCraft - GPT-4 Orchestrator with Claude Code CLI

> **A Complete Multi-Agent System for Autonomous Code Generation**

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![Node.js 18+](https://img.shields.io/badge/node.js-18+-green.svg)](https://nodejs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A sophisticated multi-agent system that combines GPT-4's strategic planning capabilities with Claude Code CLI's advanced coding expertise to create an autonomous code generation and modification platform. Features a modern split terminal interface with real-time token tracking, comprehensive session management, and enterprise-grade usage monitoring.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Split Terminal Interface](#split-terminal-interface)
- [Token Tracking & Cost Management](#token-tracking--cost-management)
- [Usage Modes](#usage-modes)
- [Session Management](#session-management)
- [Configuration](#configuration)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [API Reference](#api-reference)
- [Examples](#examples)
- [Advanced Features](#advanced-features)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

This system implements a cutting-edge multi-agent architecture where:

- **🧠 GPT-4 Orchestrator**: Analyzes user requests, breaks them into actionable tasks, and provides strategic planning
- **⚡ Claude Code CLI Agent**: Executes coding tasks with direct file system access and advanced code generation capabilities
- **🔄 Python Orchestrator**: Coordinates communication between agents via structured JSON protocols
- **📝 Session Manager**: Maintains conversation context and enables multi-turn interactions
- **🔍 Validation Engine**: Automatically checks code quality, syntax, and functionality

### Key Benefits

- **🚀 Autonomous Operation**: Minimal human intervention required
- **🎯 High Accuracy**: Dual-agent validation ensures quality output
- **📈 Scalable**: Handles simple scripts to complex multi-file projects
- **🔄 Iterative Improvement**: Self-correcting feedback loops
- **💾 Persistent Memory**: Session management for long-term projects

## 🏗️ Architecture

```mermaid
graph TD
    A[User Input] --> B[GPT-4 Orchestrator]
    B --> C[Task Generation]
    C --> D[Python Orchestrator]
    D --> E[Claude Code CLI]
    E --> F[Code Generation]
    F --> G[Validation Engine]
    G --> H{Quality Check}
    H -->|Pass| I[Success]
    H -->|Fail| J[Feedback Loop]
    J --> B
    I --> K[Session Storage]
```

### Process Flow

1. **📥 Input Processing**: User provides natural language request
2. **🎯 Task Planning**: GPT-4 analyzes and creates structured task JSON
3. **⚡ Code Execution**: Claude CLI performs the actual coding work
4. **✅ Validation**: Automated syntax checking and quality assessment
5. **🔄 Feedback Loop**: Self-correction if issues are detected
6. **💾 Session Storage**: Context preservation for future interactions

## ✨ Features

### Core Capabilities
- **📝 Code Generation**: Create files, functions, classes, and entire applications
- **🔧 Code Modification**: Edit existing code with surgical precision
- **📖 Code Analysis**: Explain algorithms, debug issues, and optimize performance
- **🧪 Testing**: Generate and run tests automatically
- **📚 Documentation**: Create comprehensive documentation and comments

### Advanced Features
- **🖥️ Split Terminal Interface**: Modern UI with separate panes for input, output, and status
- **🔢 Real-Time Token Tracking**: Live monitoring of API usage and costs
- **🧠 Multi-Turn Conversations**: Maintain context across multiple interactions
- **🔄 Session Management**: Resume previous work sessions seamlessly
- **⚡ Real-Time Validation**: Immediate feedback on code quality
- **🎯 Smart Error Handling**: Automatic retry and self-correction
- **🛡️ Security Controls**: Granular permission management
- **📊 Usage Analytics**: Detailed token usage reports and cost analysis
- **⌨️ Keyboard Shortcuts**: Efficient navigation and control

## 🚀 Installation

### Prerequisites

1. **Node.js 18+** (for Claude Code CLI)
   ```bash
   # Check version
   node --version
   
   # Install if needed (Ubuntu/Debian)
   curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
   sudo apt-get install -y nodejs
   ```

2. **Python 3.7+** (for the orchestrator)
   ```bash
   # Check version
   python3 --version
   
   # Install if needed (Ubuntu/Debian)
   sudo apt update
   sudo apt install python3 python3-pip python3-venv
   ```

3. **API Keys**
   - [Anthropic API Key](https://console.anthropic.com/) (required)
   - [OpenAI API Key](https://platform.openai.com/) (required for GPT-4 features)

### Step-by-Step Installation

1. **Install Claude Code CLI**
   ```bash
   npm install -g @anthropic-ai/claude-code
   ```

2. **Verify Claude Installation**
   ```bash
   claude --version
   claude doctor
   ```

3. **Clone and Setup Python Environment**
   ```bash
   # Navigate to the project
   cd meistrocraft
   
   # Create virtual environment
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   
   # Install dependencies
   pip install openai
   ```

4. **Install Python Dependencies**
   ```bash
   # Install required packages
   pip install openai rich
   ```

5. **Configure API Keys**
   ```bash
   # Copy template and edit with your keys
   cp config/config.template.json config/config.json
   # OR use environment variables (recommended)
   cp env.template .env
   # Edit .env with your API keys
   ```

   **Example configuration:**
   ```json
   {
     "openai_api_key": "sk-your-openai-key-here",
     "anthropic_api_key": "sk-ant-your-anthropic-key-here",
     "openai_model": "gpt-4-0613",
     "claude_model": "claude-sonnet-4-20250514",
     "allowed_tools": ["Read", "Write", "Bash(npm run test)"],
     "permission_mode": "acceptEdits",
     "max_turns": 5,
     "token_limits": {
       "daily_token_limit": 100000,
       "daily_cost_limit_usd": 50.0
     }
   }
   ```

## 🎮 Quick Start

### Basic Example (No GPT-4 Required)

```bash
# Run the built-in example
./meistrocraft
```

This executes the example task and creates a "Hello, World!" Python script.

### Single Request Mode

```bash
# Generate code from natural language
./meistrocraft --request "Create a Python class for managing a library book inventory"
```

### Interactive Mode (Full Features)

```bash
# Start interactive session
./meistrocraft --interactive
```

Example interaction:
```
👤 Your request: Create a REST API for user management
🎯 GPT-4 generated task: create_file - Create a Flask REST API...
✅ Claude completed the task!
📝 Response: Created user_api.py with Flask REST API endpoints...

👤 Your request: Add authentication middleware
🎯 GPT-4 generated task: modify_file - Add JWT authentication...
✅ Claude completed the task!
```

## 🖥️ Split Terminal Interface

MeistroCraft features a modern split terminal interface similar to Claude Code CLI, providing real-time feedback and organized workspace management.

### Interface Layout

```
┌─────────────────────────────────────────────────────────────┐
│               🎯 MeistroCraft - Session: abc12345            │
│            GPT-4 Orchestrator with Claude Code CLI          │
├─────────────────────────┬───────────────────────────────────┤
│                         │  📊 Status                        │
│    💬 Conversation      │  🆔 Session: abc12345             │
│                         │  📋 Tasks: 5                      │
│  [12:34:56] 👤 You:     │  🔢 Tokens Today: 12,450          │
│    Create a calculator  │     OpenAI: 3,200                 │
│                         │     Anthropic: 9,250              │
│  [12:35:01] 🎯 GPT-4:   │  💰 Cost: $0.0234                 │
│    Task: create_file... │  ⚡ Last: 1,250 tokens            │
│                         │     ($0.0156)                     │
│  [12:35:15] 🤖 Claude:  │  🌐 API Status                    │
│    Created calculator   │     OpenAI: 🟢 ready              │
│    with basic ops...    │     Anthropic: 🟢 ready           │
│                         │  🕒 14:35:42                      │
├─────────────────────────┤                                   │
│  ✏️  Input              │                                   │
│  > Create unit tests    │                                   │
│                         │                                   │
└─────────────────────────┴───────────────────────────────────┤
│  Ctrl+C: Exit | Ctrl+H: Help | Ctrl+L: Clear | Tab: Focus   │
└─────────────────────────────────────────────────────────────┘
```

### Key Features

- **📋 Conversation Panel**: Chat-like interface showing user requests, GPT-4 task generation, and Claude responses
- **📊 Status Panel**: Real-time display of session info, token usage, costs, and API status
- **✏️ Input Panel**: Live input with visual feedback and command suggestions
- **⌨️ Interactive Controls**: Keyboard shortcuts for efficient navigation

### UI Commands

Use these commands in the input panel:

| Command | Description |
|---------|-------------|
| `/help` | Show/hide help overlay |
| `/clear` | Clear conversation history |
| `/tokens` | Show detailed token usage |
| `/sessions` | List available sessions |
| `/context` | Show current session context |
| `/status` | Display detailed status info |
| `/quit` | Exit the application |

## 🔢 Token Tracking & Cost Management

MeistroCraft includes enterprise-grade token tracking and cost management for both OpenAI and Anthropic APIs.

### Real-Time Monitoring

```bash
# Live token display during API calls
🔢 OpenAI Usage: 150 in + 75 out = 225 tokens ($0.0045)
🔢 Claude Usage: 1200 in + 400 out = 1600 tokens ($0.0066)
```

### Usage Analytics

**View Token Statistics:**
```bash
# Show usage for last 7 days (default)
./meistrocraft --token-usage

# Show usage for specific number of days
./meistrocraft --token-usage 30
```

**Sample Output:**
```
📊 OpenAI Usage (Last 7 days):
  Requests: 45
  Tokens: 125,340 in + 67,890 out = 193,230 total
  Cost: $3.8646
  Models: gpt-4-0613

🤖 Anthropic Usage (Last 7 days):
  Requests: 38
  Tokens: 89,450 in + 45,230 out = 134,680 total
  Cost: $2.0202
  Models: claude-sonnet-4-20250514

💰 Total Usage (Last 7 days):
  Total Tokens: 327,910
  Total Cost: $5.8848

🔝 Top Sessions by Usage:
  1. d35f9687... - 45,230 tokens ($0.6789)
  2. b47164aa... - 38,940 tokens ($0.5834)
```

### Usage Limits & Alerts

**Set Usage Limits:**
```bash
./meistrocraft --set-token-limits
```

**Interactive Configuration:**
```
🔧 Token Usage Limits Configuration
Daily token limit (enter for no limit): 100000
Monthly token limit (enter for no limit): 3000000
Daily cost limit USD (enter for no limit): 50.00
Monthly cost limit USD (enter for no limit): 1500.00
✅ Token limits saved successfully!
```

**Automatic Warnings:**
```
⚠️  Daily token usage at 85.2% of limit (85,234/100,000)
⚠️  Daily cost limit exceeded! Used: $52.34, Limit: $50.00
```

### Export & Reporting

**Export Usage Reports:**
```bash
# Export last 30 days to CSV
./meistrocraft --export-usage 30
📄 Usage report exported to: token_usage_report_20250712_143052.csv
```

**CSV Report Includes:**
- Timestamp, Provider, Model
- Session ID, Task Type
- Input/Output/Total Tokens
- Cost in USD

### Token Tracking Features

- **📊 Real-time Display**: Live token counts in split terminal UI
- **💰 Cost Calculation**: Accurate pricing for all models
- **📈 Historical Data**: Detailed usage logs with 90-day retention
- **🚨 Smart Alerts**: Configurable limits with percentage warnings
- **📋 Session Tracking**: Usage breakdown by MeistroCraft sessions
- **📄 Export Options**: CSV reports for accounting and analysis
- **🔧 Automatic Cleanup**: Configurable log rotation and cleanup

## 🎭 Usage Modes

### 1. Example Mode (Default)
```bash
./meistrocraft
```
- Runs predefined example task
- No API keys required for basic functionality
- Good for testing installation

### 2. Single Request Mode
```bash
./meistrocraft --request "Your coding request here"
```
- One-shot code generation
- Creates temporary session for tracking
- Perfect for quick tasks

### 3. Interactive Mode
```bash
./meistrocraft --interactive
```
- Full conversational interface
- Maintains context across requests
- Supports complex multi-step projects

### 4. Session Continuation
```bash
# List all sessions
./meistrocraft --sessions

# Continue specific session
./meistrocraft --continue abc12345
```
- Resume previous work
- Maintains full conversation history
- Perfect for long-term projects

## 💾 Session Management

### Session Features

- **🆔 Unique Session IDs**: Every session gets a UUID for tracking
- **📊 Metadata Tracking**: Creation time, last used, task count
- **📝 Context Preservation**: Previous actions included in new prompts
- **🔍 Session Discovery**: List and search existing sessions
- **📋 Task History**: Complete record of all actions and results

### Session Commands

```bash
# List all sessions
./meistrocraft --sessions

# Start new interactive session
./meistrocraft --interactive

# Continue existing session (full ID)
./meistrocraft --continue d35f9687-14de-45e1-8f82-d9e2f965fee3

# Continue with short ID (first 8 characters)
./meistrocraft --continue d35f9687

# Start interactive session with specific ID
./meistrocraft --interactive --session=d35f9687
```

### Session Structure

```json
{
  "id": "d35f9687-14de-45e1-8f82-d9e2f965fee3",
  "name": "Session d35f9687-14de-45e1-8f82-d9e2f965fee3",
  "created_at": "2025-07-11T23:27:30",
  "last_used": "2025-07-11T23:28:04",
  "task_history": [
    {
      "timestamp": "2025-07-11T23:27:45",
      "task": {
        "action": "create_file",
        "filename": "calculator.py",
        "instruction": "Create a calculator class..."
      },
      "result": {
        "success": true,
        "result": "Created calculator.py with Calculator class...",
        "session_id": "claude-session-uuid"
      }
    }
  ],
  "context": "Previous actions summary..."
}
```

### Interactive Commands

While in interactive mode, use these special commands:

- **`/help`**: Show/hide help overlay
- **`/sessions`**: List all available sessions
- **`/context`**: View current session context
- **`/tokens`**: Show detailed token usage
- **`/status`**: Display system status
- **`/clear`**: Clear conversation history
- **`/quit`**: Exit interactive mode

## ⌨️ Keyboard Shortcuts

### Split Terminal Interface

| Shortcut | Action | Context |
|----------|--------|---------|
| **Ctrl+C** | Exit application | Global |
| **Ctrl+H** | Toggle help overlay | Interactive mode |
| **Ctrl+L** | Clear conversation | Interactive mode |
| **Enter** | Send message/command | Input panel |
| **Backspace** | Delete character | Input panel |
| **Tab** | Focus next panel | Interactive mode |

### Command Line Interface

| Command | Shortcut | Description |
|---------|----------|-------------|
| `./meistrocraft` | Basic | Run with default example |
| `./meistrocraft -i` | Interactive | Start split terminal interface |
| `./meistrocraft --help` | Help | Show all available commands |
| `./meistrocraft --token-usage` | Usage | Display token statistics |

### Navigation Tips

- **Focus Management**: Use Tab to cycle between UI panels
- **Quick Commands**: Start any input with `/` for special commands
- **Session Control**: Use short session IDs (first 8 chars) for convenience
- **Help System**: Press Ctrl+H anytime for contextual help

## ⚙️ Configuration

### Configuration File: `config/config.json`

```json
{
  "openai_api_key": "sk-your-openai-key",
  "anthropic_api_key": "sk-ant-your-anthropic-key",
  "openai_model": "gpt-4-0613",
  "claude_model": "claude-sonnet-4-20250514",
  "allowed_tools": ["Read", "Write", "Bash(npm run test)", "Bash(python -m pytest)"],
  "permission_mode": "acceptEdits",
  "max_turns": 5,
  "token_limits": {
    "daily_token_limit": 100000,
    "monthly_token_limit": 3000000,
    "daily_cost_limit_usd": 50.0,
    "monthly_cost_limit_usd": 1500.0,
    "per_session_token_limit": 10000,
    "warn_at_percentage": 80.0
  },
  "features": {
    "track_tokens": true,
    "auto_cleanup_logs": true,
    "cleanup_days": 90
  }
}
```

### Configuration Options

| Option | Description | Default | Options |
|--------|-------------|---------|---------|
| `openai_api_key` | OpenAI API key for GPT-4 | Required | Your API key |
| `anthropic_api_key` | Anthropic API key for Claude | Required | Your API key |
| `openai_model` | GPT-4 model version | `gpt-4-0613` | `gpt-4-0613`, `gpt-4-1106-preview` |
| `claude_model` | Claude model version | `claude-sonnet-4-20250514` | Latest Claude models |
| `allowed_tools` | Tools Claude can use | `["Read", "Write"]` | See [Tools](#allowed-tools) |
| `permission_mode` | Permission handling | `acceptEdits` | `acceptEdits`, `plan`, `bypassPermissions` |
| `max_turns` | Max internal turns for Claude | `5` | `1-20` |

### Token Limits Configuration

| Option | Description | Default | Example |
|--------|-------------|---------|---------|
| `daily_token_limit` | Max tokens per day | None | `100000` |
| `monthly_token_limit` | Max tokens per month | None | `3000000` |
| `daily_cost_limit_usd` | Max cost per day (USD) | None | `50.0` |
| `monthly_cost_limit_usd` | Max cost per month (USD) | None | `1500.0` |
| `per_session_token_limit` | Max tokens per session | None | `10000` |
| `warn_at_percentage` | Warning threshold | `80.0` | `75.0` |

### Feature Flags

| Option | Description | Default |
|--------|-------------|---------|
| `track_tokens` | Enable token tracking | `true` |
| `auto_cleanup_logs` | Auto-cleanup old logs | `true` |
| `cleanup_days` | Days to retain logs | `90` |

### Allowed Tools

Configure which tools Claude can use:

```json
{
  "allowed_tools": [
    "Read",                    // Read files
    "Write",                   // Write/create files
    "Edit",                    // Edit existing files
    "Bash",                    // Run any bash command
    "Bash(npm run test)",      // Run specific npm test
    "Bash(python -m pytest)", // Run pytest
    "Bash(git status)",        // Run git commands
    "Grep",                    // Search in files
    "Glob"                     // Find files by pattern
  ]
}
```

### Permission Modes

- **`acceptEdits`**: Auto-approve file modifications (recommended)
- **`plan`**: Show what would be done without executing
- **`bypassPermissions`**: Skip all permission checks (use with caution)

## 📋 API Reference

### Task JSON Schema

```typescript
interface Task {
  action: "create_file" | "modify_file" | "explain_code" | "run_tests" | "debug_code" | "refactor_code";
  filename?: string;           // Target file (required for file operations)
  instruction: string;         // Detailed instructions for Claude
  context?: string;           // Additional context (error messages, requirements)
  tools?: string[];           // Override allowed tools for this task
}
```

### GPT-4 Function Schema

The system uses OpenAI function calling for structured task generation:

```json
{
  "name": "invoke_claude_task",
  "description": "Instruct Claude Code CLI to perform a coding task.",
  "parameters": {
    "type": "object",
    "properties": {
      "action": {
        "type": "string",
        "enum": ["create_file", "modify_file", "explain_code", "run_tests", "debug_code", "refactor_code"]
      },
      "filename": {"type": "string"},
      "instruction": {"type": "string"},
      "context": {"type": "string"},
      "tools": {"type": "array", "items": {"type": "string"}}
    },
    "required": ["action", "instruction"]
  }
}
```

### Response Format

```typescript
interface TaskResult {
  success: boolean;
  result?: string;             // Claude's response text
  error?: string;             // Error message if failed
  session_id?: string;        // Claude CLI session ID
  response?: object;          // Full Claude CLI JSON response
}
```

## 💡 Examples

### Basic File Creation

```bash
./meistrocraft --request "Create a Python script that calculates fibonacci numbers"
```

**Generated Output**: `fibonacci.py`
```python
def fibonacci(n):
    if n == 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n - 1) + fibonacci(n - 2)
```

### Web Development

```bash
./meistrocraft --request "Create a Flask web application with user registration and login"
```

**Generated Files**:
- `app.py` - Main Flask application
- `models.py` - User models
- `forms.py` - Login/registration forms
- `templates/` - HTML templates

### Data Processing

```bash
./meistrocraft --request "Create a data processing pipeline that reads CSV files and generates statistics"
```

**Generated Output**: Complete data analysis script with pandas integration.

### API Development

```bash
./meistrocraft --interactive
```

**Multi-turn Conversation**:
```
👤 Create a REST API for a bookstore
✅ Created bookstore_api.py with Flask REST endpoints

👤 Add authentication using JWT tokens
✅ Added JWT authentication middleware

👤 Add database integration with SQLAlchemy
✅ Integrated SQLAlchemy models and database operations

👤 Add input validation and error handling
✅ Added comprehensive validation and error handling
```

### Bug Fixing

```bash
./meistrocraft --request "Fix the bug in my authentication system where users can't log in"
```

**With Context**:
```json
{
  "action": "debug_code",
  "filename": "auth.py",
  "instruction": "Fix login bug - users getting 'invalid credentials' error",
  "context": "Error traceback: AttributeError: 'NoneType' object has no attribute 'check_password'"
}
```

## 🚀 Advanced Features

### Self-Correction System

The system automatically validates generated code and fixes issues:

1. **Syntax Validation**: Checks Python syntax automatically
2. **Logic Validation**: Runs basic tests and checks
3. **Error Recovery**: Automatically attempts to fix detected issues
4. **Iterative Improvement**: Multiple correction attempts if needed

### Custom Validation

Extend validation by modifying `validate_code_output()`:

```python
def custom_validator(result, task):
    # Add your custom validation logic
    if task["action"] == "create_file" and task["filename"].endswith(".py"):
        # Custom Python validation
        pass
    return validation_result
```

### Integration with Testing Frameworks

Configure automatic testing:

```json
{
  "allowed_tools": [
    "Bash(python -m pytest tests/)",
    "Bash(npm test)",
    "Bash(cargo test)"
  ]
}
```

### Continuous Integration

Example workflow for CI/CD integration:

```bash
# Generate code
./meistrocraft --request "Create user authentication module"

# Run tests automatically
./meistrocraft --request "Run all tests and fix any failures"

# Deploy if tests pass
./meistrocraft --request "Deploy to staging environment"
```

## 🛡️ Security

### Permission Management

The system implements multiple security layers:

1. **Tool Restrictions**: Limit what commands Claude can execute
2. **File System Controls**: Restrict file access to project directory
3. **Command Whitelisting**: Only allow specific bash commands
4. **Session Isolation**: Each session runs in isolation

### Recommended Security Settings

```json
{
  "allowed_tools": [
    "Read",
    "Write", 
    "Bash(npm run test)",
    "Bash(python -m pytest)"
  ],
  "permission_mode": "acceptEdits"
}
```

### Production Considerations

1. **🔒 API Key Security**: Store keys in environment variables
2. **📁 Sandboxing**: Run in containerized environment
3. **🔍 Code Review**: Always review generated code before deployment
4. **📝 Audit Logging**: Enable detailed session logging
5. **🚫 Command Restrictions**: Limit dangerous bash commands

### Environment Variables

For production deployment:

```bash
export ANTHROPIC_API_KEY="your-anthropic-key"
export OPENAI_API_KEY="your-openai-key"
export AI_AGENT_ENV="production"
export AI_AGENT_LOG_LEVEL="INFO"
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Claude CLI Not Found
```bash
Error: claude: command not found
```

**Solution**:
```bash
# Reinstall Claude CLI
npm install -g @anthropic-ai/claude-code

# Check PATH
echo $PATH
which claude
```

#### 2. API Key Issues
```bash
Error: Invalid API key
```

**Solution**:
```bash
# Check API key format
echo $ANTHROPIC_API_KEY

# Verify in config.json
cat config/config.json | grep api_key
```

#### 3. Permission Errors
```bash
Error: Permission denied for tool: Bash
```

**Solution**:
```json
{
  "allowed_tools": ["Read", "Write", "Bash"],
  "permission_mode": "acceptEdits"
}
```

#### 4. Rich UI Library Missing
```bash
⚠️  Rich UI not available. Install with: pip install rich
Falling back to basic interactive mode...
```

**Solution**:
```bash
# Install Rich library for split terminal UI
pip install rich

# Or install all dependencies
pip install -r requirements.txt
```

#### 5. Terminal Display Issues
```bash
# Garbled text or layout problems in split terminal
```

**Solution**:
```bash
# Check terminal compatibility
echo $TERM

# Try with different terminal
# Recommended: Terminal.app (macOS), Windows Terminal, gnome-terminal

# Force basic mode if needed
./meistrocraft --interactive --basic-mode
```

#### 6. Token Tracking Not Working
```bash
# No token usage displayed or warnings not showing
```

**Solution**:
```bash
# Check token tracking is enabled
cat config/config.json | grep track_tokens

# Verify token_usage directory exists and is writable
ls -la token_usage/

# Reset token tracking data
rm -rf token_usage/
./meistrocraft --token-usage  # Will recreate
```

#### 7. Session Not Found
```bash
Error: No conversation found with session ID
```

**Solution**:
```bash
# List available sessions
python main.py --sessions

# Use correct session ID
python main.py --continue actual-session-id
```

#### 5. GPT-4 Rate Limits
```bash
Error: Rate limit exceeded
```

**Solution**:
- Wait and retry
- Check OpenAI dashboard for usage
- Consider upgrading OpenAI plan

### Debug Mode

Enable verbose logging:

```python
# In main.py, add to cli_cmd:
cli_cmd += ["--verbose"]
```

### Log Analysis

Session logs are stored in `sessions/` directory:

```bash
# View session details
cat sessions/d35f9687-14de-45e1-8f82-d9e2f965fee3.json | jq .

# Check task history
cat sessions/*.json | jq '.task_history[].result.success'
```

### Performance Optimization

1. **Reduce Context**: Limit session context length
2. **Optimize Prompts**: More specific instructions = better results
3. **Batch Operations**: Group related tasks together
4. **Cache Results**: Reuse successful patterns

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd meistrocraft

# Setup development environment
python3 -m venv dev-env
source dev-env/bin/activate
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install
```

### Code Style

- Follow PEP 8 for Python code
- Use type hints where possible
- Add docstrings for all functions
- Include unit tests for new features

### Submitting Changes

1. Fork the repository
2. Create feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Submit Pull Request

### Testing

```bash
# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=main tests/

# Lint code
flake8 main.py
mypy main.py
```

## 📈 Roadmap

### Upcoming Features

- [ ] **Visual Studio Code Extension**
- [ ] **Docker Container Support** 
- [ ] **Multi-Language Support** (Java, C++, Go, Rust)
- [ ] **Database Integration** (SQL generation and migration)
- [ ] **Cloud Deployment** (AWS, GCP, Azure)
- [ ] **Team Collaboration** (Shared sessions)
- [ ] **Plugin System** (Custom validators and tools)
- [ ] **Web Interface** (Browser-based GUI)

### 🚀 GitHub API Integration Roadmap

#### Phase 1: Foundation & Core Operations (Q1 2025)
**Priority: High** | **Estimated Timeline: 4-6 weeks**

- [ ] **GitHub Authentication & Configuration**
  - OAuth & Personal Access Token support
  - Secure token storage and management
  - User permission validation
  - Organization access control

- [ ] **Repository Management**
  - Create new repositories from MeistroCraft projects
  - Clone existing repositories for modification
  - Fork repositories for contributions
  - Repository metadata management (description, topics, visibility)

- [ ] **Basic File Operations**
  - Read/write files via GitHub API
  - Commit changes with descriptive messages
  - Branch creation and management
  - File history and diff integration

- [ ] **Configuration Integration**
  - Add `github_api_key` to config.json
  - GitHub-specific tool permissions
  - Repository-specific settings

#### Phase 2: Development Workflow Automation (Q2 2025)
**Priority: High** | **Estimated Timeline: 6-8 weeks**

- [ ] **Automated Pull Request Management**
  - Create PRs directly from MeistroCraft sessions
  - Auto-generate PR titles and descriptions
  - Link PRs to related issues
  - Draft/ready state management
  - PR template integration

- [ ] **Issue Integration & Tracking**
  - Create GitHub issues from discovered bugs
  - Link MeistroCraft tasks to existing issues
  - Auto-close issues when fixes are implemented
  - Issue labeling and assignment
  - Bug report generation with context

- [ ] **Smart Branch Management**
  - Feature branch creation from task requests
  - Naming conventions based on task type
  - Branch protection rule compliance
  - Merge conflict detection and resolution

- [ ] **Code Review Automation**
  - AI-powered code review suggestions
  - Automated code quality checks
  - Security vulnerability detection
  - Performance optimization recommendations

#### Phase 3: CI/CD & Testing Integration (Q3 2025)
**Priority: Medium** | **Estimated Timeline: 4-6 weeks**

- [ ] **GitHub Actions Integration**
  - Monitor workflow status
  - Trigger custom workflows
  - Parse build logs and test results
  - Auto-fix failing tests when possible

- [ ] **Build & Deployment Automation**
  - Monitor deployment status
  - Rollback capabilities
  - Environment-specific configurations
  - Release preparation automation

- [ ] **Test Integration & Management**
  - Run tests via GitHub Actions
  - Generate test reports
  - Coverage analysis integration
  - Automated test creation for new features

- [ ] **Status Checks & Quality Gates**
  - Required status check compliance
  - Quality gate enforcement
  - Automated merge when conditions met
  - Notification system for failures

#### Phase 4: Team Collaboration & Social Coding (Q4 2025)
**Priority: Medium** | **Estimated Timeline: 6-8 weeks**

- [ ] **Enhanced Code Review**
  - AI-assisted review comments
  - Code suggestion integration
  - Review request automation
  - Reviewer assignment based on expertise

- [ ] **Project Management Integration**
  - GitHub Projects board integration
  - Task assignment and tracking
  - Sprint planning assistance
  - Progress reporting

- [ ] **Team Communication**
  - Discussion participation
  - Mention and notification handling
  - Team member expertise mapping
  - Collaborative session sharing

- [ ] **Documentation Automation**
  - Auto-generate/update README files
  - API documentation generation
  - Change log maintenance
  - Wiki integration

#### Phase 5: Advanced Analytics & Security (Q1 2026)
**Priority: Low-Medium** | **Estimated Timeline: 4-6 weeks**

- [ ] **Repository Analytics**
  - Code quality metrics
  - Contributor activity analysis
  - Performance trend tracking
  - Technical debt identification

- [ ] **Security Integration**
  - Dependabot alert processing
  - Security advisory monitoring
  - Vulnerability auto-fixing
  - License compliance checking

- [ ] **Release Management**
  - Automated versioning (SemVer)
  - Release note generation
  - Package publishing
  - Change log automation

- [ ] **Advanced Automation**
  - Custom GitHub App development
  - Webhook integration
  - Advanced workflow orchestration
  - Multi-repository operations

### 🎯 GitHub Integration Commands (Planned)

```bash
# Repository operations
./meistrocraft --github --create-repo "my-new-project"
./meistrocraft --github --clone "username/repo"
./meistrocraft --github --fork "upstream/repo"

# Development workflow
./meistrocraft --github --create-pr "Add user authentication"
./meistrocraft --github --create-issue "Bug in login system"
./meistrocraft --github --link-issue 123

# Project management
./meistrocraft --github --sync-project
./meistrocraft --github --update-status
./meistrocraft --github --create-release v1.0.0

# Interactive GitHub mode
./meistrocraft --interactive --github
```

### 📊 Expected Benefits

- **🚀 Faster Development**: Direct integration with GitHub workflows
- **🔄 Seamless CI/CD**: Automated testing and deployment
- **👥 Better Collaboration**: Enhanced team communication and code review
- **📈 Improved Quality**: Automated code analysis and security checks
- **📋 Project Tracking**: Integrated issue and project management
- **🔐 Enhanced Security**: Automated vulnerability detection and fixes

### 🛠️ Technical Implementation Notes

- **GitHub REST API v4** for primary operations
- **GitHub GraphQL API** for complex queries
- **GitHub Apps** for advanced integrations
- **Webhooks** for real-time notifications
- **OAuth 2.0** for secure authentication
- **Rate limiting** and retry mechanisms
- **Parallel processing** for bulk operations

### Performance Improvements

- [ ] **Parallel Processing** for multiple tasks
- [ ] **Smart Caching** for repeated operations
- [ ] **Context Optimization** for faster responses
- [ ] **Model Selection** based on task complexity

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Anthropic** for Claude Code CLI and API
- **OpenAI** for GPT-4 API and function calling
- **Rich Library** for beautiful terminal interfaces
- **AGENTS.md** specification for architecture guidance
- **Open Source Community** for dependencies and inspiration

## 📞 Support

- **📧 Email**: [support@example.com](mailto:support@example.com)
- **💬 Discord**: [Join our community](https://discord.gg/example)
- **🐛 Issues**: [GitHub Issues](https://github.com/example/ai-coding-agent/issues)
- **📖 Documentation**: [Full Documentation](https://docs.example.com)

---

**⭐ Star this repository if you find it helpful!**

*Built with ❤️ by the MeistroCraft team*