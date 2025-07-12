# Changelog

All notable changes to MeistroCraft will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2025-07-12

### 🚀 Major Features Added

#### Split Terminal Interface
- **Modern UI**: Implemented split terminal interface similar to Claude Code CLI
- **Real-time Display**: Live conversation panel with color-coded messages
- **Status Panel**: Real-time token usage, session info, and API status monitoring
- **Interactive Input**: Live input panel with command suggestions and feedback
- **Keyboard Navigation**: Full keyboard shortcut support (Ctrl+C, Ctrl+H, Ctrl+L)

#### Enterprise Token Tracking System
- **Real-time Monitoring**: Live token and cost tracking for OpenAI and Anthropic APIs
- **Usage Analytics**: Comprehensive statistics with 7/30/90-day reporting
- **Cost Management**: Automatic cost calculations with current API pricing
- **Smart Limits**: Configurable daily/monthly token and cost limits with warnings
- **Export Reports**: CSV export functionality for accounting and analysis
- **Session Tracking**: Per-session usage breakdown and top consumers analysis

#### Enhanced Command System
- **UI Commands**: `/help`, `/tokens`, `/sessions`, `/context`, `/status`, `/clear`, `/quit`
- **Token Management**: `--token-usage`, `--set-token-limits`, `--export-usage` commands
- **Graceful Fallbacks**: Automatic fallback to basic mode when Rich UI unavailable

### 🛠️ Technical Improvements

#### Architecture Enhancements
- **Modular Design**: Separated UI components into dedicated modules
- **Async Input Handling**: Non-blocking input with platform-specific optimizations
- **Thread Management**: Proper threading for responsive UI updates
- **Error Recovery**: Robust error handling with automatic fallbacks

#### Cross-Platform Compatibility
- **Unix/Linux**: Full raw input support with character-by-character handling
- **Windows**: Line-based input fallback with full functionality
- **Terminal Detection**: Automatic detection and appropriate input handling

#### Security & Configuration
- **Environment Variables**: Support for `.env` files and environment-based configuration
- **Template Files**: `config.template.json` and `env.template` for easy setup
- **Sensitive Data Protection**: Enhanced .gitignore for API keys and usage data

### 📁 New Files Added

#### Core Components
- `terminal_ui.py` - Split terminal interface implementation
- `async_input.py` - Cross-platform async input handling
- `interactive_ui.py` - Complete interactive session management
- `token_tracker.py` - Enterprise token tracking and cost management

#### Configuration Templates
- `config/config.template.json` - Configuration template with token limits
- `env.template` - Environment variables template
- `requirements.txt` - Python dependencies list

#### Documentation
- Updated `README.md` with comprehensive documentation
- New sections for UI, token tracking, keyboard shortcuts
- Enhanced troubleshooting guide

### 🔧 Configuration Changes

#### New Configuration Options
```json
{
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

### 📊 Usage Analytics Features

#### Real-time Metrics
- Live token counting during API calls
- Immediate cost calculation and display
- Running totals for daily/monthly usage
- API status monitoring

#### Reporting & Export
- Detailed usage summaries by time period
- Provider-specific breakdowns (OpenAI vs Anthropic)
- Session-based analysis with top consumers
- CSV export for external analysis

### ⌨️ User Experience Improvements

#### Keyboard Shortcuts
- `Ctrl+C`: Exit application
- `Ctrl+H`: Toggle help overlay
- `Ctrl+L`: Clear conversation
- `Enter`: Send message/command
- `Tab`: Focus next panel

#### Visual Enhancements
- Color-coded conversation (User: cyan, GPT-4: yellow, Claude: green, Errors: red)
- Progress indicators for long-running tasks
- Status badges for API availability
- Real-time token usage display

### 🔄 Breaking Changes

#### Command Interface
- Interactive mode now defaults to split terminal UI
- Basic mode requires explicit fallback or missing Rich library
- New command-line arguments for token management

#### Dependencies
- **New Required**: `rich>=13.0.0` for split terminal interface
- **Existing**: `openai>=1.0.0` for GPT-4 integration

### 🐛 Bug Fixes

#### Session Management
- Fixed session ID resolution for short IDs
- Improved session context handling
- Better error messages for invalid sessions

#### API Integration
- Enhanced error handling for API failures
- Improved token usage parsing from Claude CLI
- Better retry logic for failed requests

### 📈 Performance Optimizations

#### Memory Management
- Efficient conversation history management (last 50 messages)
- Automatic log cleanup with configurable retention
- Optimized UI refresh rates (4 FPS for smooth experience)

#### Resource Usage
- Background processing for API calls
- Non-blocking input handling
- Efficient token usage storage (JSONL format)

### 🔒 Security Enhancements

#### Data Protection
- Enhanced .gitignore for sensitive data
- Template-based configuration to prevent key leakage
- Secure environment variable handling

#### Access Control
- Maintained existing tool permission system
- Enhanced session isolation
- Improved audit logging

### 📋 GitHub Integration Roadmap

Added comprehensive 5-phase roadmap for GitHub API integration:

#### Phase 1 (Q1 2025): Foundation & Core Operations
- GitHub authentication and configuration
- Repository management (create, clone, fork)
- Basic file operations via API

#### Phase 2 (Q2 2025): Development Workflow Automation
- Automated pull request management
- Issue integration and tracking
- Smart branch management
- Code review automation

#### Phase 3 (Q3 2025): CI/CD & Testing Integration
- GitHub Actions integration
- Build and deployment automation
- Test management and reporting

#### Phase 4 (Q4 2025): Team Collaboration & Social Coding
- Enhanced code review features
- Project management integration
- Team communication tools

#### Phase 5 (Q1 2026): Advanced Analytics & Security
- Repository analytics and metrics
- Security integration
- Release management automation

### 🔮 Future Enhancements

#### Planned Features
- Visual Studio Code extension
- Docker container support
- Multi-language support (Java, C++, Go, Rust)
- Database integration
- Cloud deployment automation
- Team collaboration features
- Plugin system for custom validators

### 📦 Installation Updates

#### New Installation Steps
```bash
# Install Python dependencies
pip install openai rich

# Copy configuration templates
cp config/config.template.json config/config.json
cp env.template .env
```

#### Backwards Compatibility
- Existing configurations remain functional
- Automatic fallback to basic mode
- Graceful handling of missing dependencies

---

## [1.0.0] - 2025-07-11

### Initial Release
- GPT-4 orchestrator with Claude Code CLI integration
- Basic interactive mode
- Session management
- Project organization
- Multi-turn conversations
- Code validation and testing
- Configuration management

---

For more details about any release, please refer to the [README.md](README.md) documentation.