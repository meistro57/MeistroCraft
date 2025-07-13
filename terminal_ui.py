#!/usr/bin/env python3
"""
Terminal UI for MeistroCraft
Provides a split terminal interface similar to Claude Code CLI with separate panes for:
- User input
- AI responses  
- System status and token tracking
- Session information
"""

import os
import sys
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from queue import Queue, Empty

try:
    from rich.console import Console, Group
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich.table import Table
    from rich.live import Live
    from rich.prompt import Prompt
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich.columns import Columns
    from rich.align import Align
    from rich.padding import Padding
except ImportError:
    print("Rich library not found. Install with: pip install rich")
    sys.exit(1)

@dataclass
class StatusInfo:
    """Status information for the UI."""
    session_id: Optional[str] = None
    session_name: Optional[str] = None
    task_count: int = 0
    current_task: Optional[str] = None
    total_tokens_today: int = 0
    total_cost_today: float = 0.0
    openai_tokens_today: int = 0
    anthropic_tokens_today: int = 0
    last_request_tokens: int = 0
    last_request_cost: float = 0.0
    api_status: Dict[str, str] = None
    memory_entries: int = 0
    memory_size_mb: float = 0.0
    memory_limit_mb: float = 512.0
    background_tasks_running: int = 0
    background_tasks_queued: int = 0
    background_tasks_total: int = 0
    
    def __post_init__(self):
        if self.api_status is None:
            self.api_status = {"openai": "ready", "anthropic": "ready"}

class MeistroCraftUI:
    """Main terminal UI manager for MeistroCraft."""
    
    def __init__(self, token_tracker=None):
        self.console = Console()
        self.token_tracker = token_tracker
        self.status = StatusInfo()
        self.message_queue = Queue()
        self.input_queue = Queue()
        self.running = False
        self.live = None
        
        # Message history
        self.conversation_history = []
        self.system_messages = []
        
        # UI state
        self.show_help = False
        self.current_input = ""
        
    def create_layout(self) -> Layout:
        """Create the main split terminal layout."""
        layout = Layout()
        
        # Split into header, main content, and footer
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="main", minimum_size=10),
            Layout(name="footer", size=2)
        )
        
        # Split main content into left (conversation) and right (status)
        layout["main"].split_row(
            Layout(name="conversation", ratio=2),
            Layout(name="status", ratio=1)
        )
        
        # Split conversation into input and output
        layout["conversation"].split_column(
            Layout(name="output", minimum_size=5),
            Layout(name="input", size=4)
        )
        
        return layout
    
    def create_header(self) -> Panel:
        """Create the header panel with app title and quick info."""
        title_text = Text("🎯 MeistroCraft", style="bold magenta")
        subtitle_text = Text("GPT-4 Orchestrator with Claude Code CLI", style="dim")
        
        if self.status.session_id:
            session_text = Text(f" | Session: {self.status.session_id[:8]}...", style="cyan")
            title_text.append(session_text)
        
        header_content = Group(
            Align.center(title_text),
            Align.center(subtitle_text)
        )
        
        return Panel(header_content, style="blue")
    
    def create_footer(self) -> Panel:
        """Create the footer with keyboard shortcuts."""
        shortcuts = [
            "Ctrl+C: Exit",
            "Ctrl+H: Toggle Help",
            "Ctrl+L: Clear Output",
            "Tab: Next Pane"
        ]
        
        footer_text = Text(" | ".join(shortcuts), style="dim")
        return Panel(Align.center(footer_text), style="blue")
    
    def create_conversation_output(self) -> Panel:
        """Create the conversation output panel."""
        if not self.conversation_history:
            content = Text("Welcome to MeistroCraft! Start by typing a request below.", style="dim italic")
            return Panel(Align.center(content), title="💬 Conversation", border_style="green")
        
        # Show last few conversation entries
        conversation_lines = []
        for entry in self.conversation_history[-10:]:  # Show last 10 entries
            timestamp = entry.get("timestamp", "")
            speaker = entry.get("speaker", "")
            message = entry.get("message", "")
            
            if speaker == "user":
                conversation_lines.append(Text(f"[{timestamp}] 👤 You:", style="cyan bold"))
                conversation_lines.append(Text(f"  {message}", style="white"))
            elif speaker == "system":
                conversation_lines.append(Text(f"[{timestamp}] 🎯 GPT-4:", style="yellow bold"))
                conversation_lines.append(Text(f"  {message}", style="yellow"))
            elif speaker == "claude":
                conversation_lines.append(Text(f"[{timestamp}] 🤖 Claude:", style="green bold"))
                conversation_lines.append(Text(f"  {message}", style="green"))
            elif speaker == "error":
                conversation_lines.append(Text(f"[{timestamp}] ❌ Error:", style="red bold"))
                conversation_lines.append(Text(f"  {message}", style="red"))
            
            conversation_lines.append(Text(""))  # Empty line
        
        content = Group(*conversation_lines)
        return Panel(content, title="💬 Conversation", border_style="green")
    
    def create_input_panel(self) -> Panel:
        """Create the input panel."""
        if self.status.current_task:
            title = f"✏️  Input (Working on: {self.status.current_task[:30]}...)"
            border_style = "yellow"
        else:
            title = "✏️  Input"
            border_style = "blue"
        
        input_text = Text(f"> {self.current_input}", style="white")
        if not self.current_input and not self.status.current_task:
            placeholder = Text("Type your request here (e.g., 'Create a Python calculator')", style="dim")
            content = Group(placeholder, input_text)
        else:
            content = input_text
        
        return Panel(content, title=title, border_style=border_style)
    
    def create_status_panel(self) -> Panel:
        """Create the status information panel."""
        status_content = []
        
        # Session information
        if self.status.session_id:
            status_content.append(Text("📋 Session Info", style="bold cyan"))
            status_content.append(Text(f"ID: {self.status.session_id[:8]}...", style="white"))
            status_content.append(Text(f"Tasks: {self.status.task_count}", style="white"))
            status_content.append(Text(""))
        
        # Token usage today
        status_content.append(Text("🔢 Token Usage (Today)", style="bold magenta"))
        status_content.append(Text(f"Total: {self.status.total_tokens_today:,}", style="white"))
        status_content.append(Text(f"OpenAI: {self.status.openai_tokens_today:,}", style="blue"))
        status_content.append(Text(f"Anthropic: {self.status.anthropic_tokens_today:,}", style="green"))
        status_content.append(Text(f"Cost: ${self.status.total_cost_today:.4f}", style="yellow"))
        status_content.append(Text(""))
        
        # Last request info
        if self.status.last_request_tokens > 0:
            status_content.append(Text("⚡ Last Request", style="bold yellow"))
            status_content.append(Text(f"Tokens: {self.status.last_request_tokens:,}", style="white"))
            status_content.append(Text(f"Cost: ${self.status.last_request_cost:.4f}", style="white"))
            status_content.append(Text(""))
        
        # Memory usage
        status_content.append(Text("💾 Memory Status", style="bold green"))
        memory_usage_percent = (self.status.memory_size_mb / self.status.memory_limit_mb) * 100 if self.status.memory_limit_mb > 0 else 0
        
        if self.status.memory_size_mb >= self.status.memory_limit_mb:
            memory_indicator = "🚨"
            memory_style = "red"
        elif memory_usage_percent >= 80:
            memory_indicator = "⚠️"
            memory_style = "yellow"
        else:
            memory_indicator = "💾"
            memory_style = "white"
        
        status_content.append(Text(f"Entries: {self.status.memory_entries:,}", style="white"))
        status_content.append(Text(f"Size: {memory_indicator} {self.status.memory_size_mb:.1f}MB / {self.status.memory_limit_mb:.0f}MB", style=memory_style))
        if memory_usage_percent > 0:
            status_content.append(Text(f"Usage: {memory_usage_percent:.1f}%", style=memory_style))
        status_content.append(Text(""))
        
        # Background Tasks
        if self.status.background_tasks_total > 0:
            status_content.append(Text("🔄 Background Tasks", style="bold yellow"))
            status_content.append(Text(f"Running: {self.status.background_tasks_running}", style="white"))
            status_content.append(Text(f"Queued: {self.status.background_tasks_queued}", style="white"))
            status_content.append(Text(f"Total: {self.status.background_tasks_total}", style="white"))
            status_content.append(Text(""))
        
        # API Status
        status_content.append(Text("🌐 API Status", style="bold blue"))
        openai_status = "🟢" if self.status.api_status["openai"] == "ready" else "🔴"
        anthropic_status = "🟢" if self.status.api_status["anthropic"] == "ready" else "🔴"
        status_content.append(Text(f"OpenAI: {openai_status} {self.status.api_status['openai']}", style="white"))
        status_content.append(Text(f"Anthropic: {anthropic_status} {self.status.api_status['anthropic']}", style="white"))
        
        # Current time
        current_time = datetime.now().strftime("%H:%M:%S")
        status_content.append(Text(""))
        status_content.append(Text(f"🕒 {current_time}", style="dim"))
        
        content = Group(*status_content)
        return Panel(content, title="📊 Status", border_style="magenta")
    
    def create_help_panel(self) -> Panel:
        """Create help panel overlay."""
        help_content = [
            Text("🎯 MeistroCraft Help", style="bold cyan"),
            Text(""),
            Text("Commands:", style="bold"),
            Text("  /help          - Show this help"),
            Text("  /sessions      - List all sessions"),
            Text("  /context       - Show session context"),
            Text("  /tokens        - Show token usage"),
            Text("  /memory        - Show memory status"),
            Text("  /memory-report - Export memory report"),
            Text("  /memory-clean  - Clean up old memories"),
            Text("  /workspaces    - List all workspaces"),
            Text("  /workspace     - Show current workspace status"),
            Text("  /complete      - Complete current workspace"),
            Text("  /abandon       - Abandon current workspace"),
            Text("  /tasks         - Show background tasks"),
            Text("  /queue         - Show task queue status"),
            Text("  /bg <task>     - Queue task for background execution"),
            Text("  /cancel <id>   - Cancel background task"),
            Text("  /priority <id> <level> - Set task priority (low/medium/high/urgent)"),
            Text("  /auto-accept <level>   - Set auto-accept level (none/safe/trusted/aggressive)"),
            Text("  /auto-status   - Show auto-accept configuration"),
            Text("  /cleanup-sessions      - Clean up old session files"),
            Text("  /repair-sessions       - Repair corrupted session files"),
            Text("  /delete-session <id>   - Delete a specific session"),
            Text("  /test          - Run project tests"),
            Text("  /run           - Run the application"),
            Text("  /build         - Build the project"),
            Text("  /clear         - Clear conversation"),
            Text("  /quit          - Exit application"),
            Text(""),
            Text("Examples:", style="bold"),
            Text("  Create a Python calculator"),
            Text("  Add authentication to my app"),
            Text("  Fix the bug in login.py"),
            Text("  Generate unit tests"),
            Text(""),
            Text("Keyboard Shortcuts:", style="bold"),
            Text("  Ctrl+C        - Exit"),
            Text("  Ctrl+H        - Toggle this help"),
            Text("  Ctrl+L        - Clear output"),
            Text("  Enter         - Send message"),
            Text(""),
            Text("Press Ctrl+H to close this help.")
        ]
        
        content = Group(*help_content)
        return Panel(content, title="❓ Help", border_style="yellow")
    
    def update_layout(self, layout: Layout) -> None:
        """Update all layout panels with current data."""
        layout["header"].update(self.create_header())
        layout["footer"].update(self.create_footer())
        
        if self.show_help:
            # Show help overlay over the main content
            layout["main"].update(self.create_help_panel())
        else:
            layout["output"].update(self.create_conversation_output())
            layout["input"].update(self.create_input_panel())
            layout["status"].update(self.create_status_panel())
    
    def add_message(self, speaker: str, message: str, task_type: Optional[str] = None) -> None:
        """Add a message to the conversation history."""
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "speaker": speaker,
            "message": message,
            "task_type": task_type
        }
        self.conversation_history.append(entry)
        
        # Keep only last 50 messages to prevent memory issues
        if len(self.conversation_history) > 50:
            self.conversation_history = self.conversation_history[-50:]
    
    def update_status(self, **kwargs) -> None:
        """Update status information."""
        for key, value in kwargs.items():
            if hasattr(self.status, key):
                setattr(self.status, key, value)
    
    def update_token_usage(self, provider: str, tokens: int, cost: float) -> None:
        """Update token usage statistics."""
        if provider == "openai":
            self.status.openai_tokens_today += tokens
        elif provider == "anthropic":
            self.status.anthropic_tokens_today += tokens
        
        self.status.total_tokens_today += tokens
        self.status.total_cost_today += cost
        self.status.last_request_tokens = tokens
        self.status.last_request_cost = cost
    
    def show_progress(self, task_description: str) -> None:
        """Show progress indicator for long-running tasks."""
        self.update_status(current_task=task_description)
        self.add_message("system", f"🔄 {task_description}...")
    
    def hide_progress(self) -> None:
        """Hide progress indicator."""
        self.update_status(current_task=None)
    
    def get_user_input(self, prompt: str = "> ") -> str:
        """Get user input through the UI."""
        # This will be handled by the main input loop
        return ""
    
    def display_error(self, error_message: str) -> None:
        """Display an error message."""
        self.add_message("error", error_message)
    
    def display_success(self, success_message: str) -> None:
        """Display a success message."""
        self.add_message("system", f"✅ {success_message}")
    
    def clear_conversation(self) -> None:
        """Clear the conversation history."""
        self.conversation_history = []
        self.add_message("system", "Conversation cleared.")
    
    def toggle_help(self) -> None:
        """Toggle help panel visibility."""
        self.show_help = not self.show_help
    
    def run_ui(self, input_callback: Callable[[str], None]) -> None:
        """Run the main UI loop."""
        self.running = True
        layout = self.create_layout()
        
        try:
            with Live(layout, console=self.console, refresh_per_second=10, screen=True) as live:
                self.live = live
                
                # Show welcome message
                self.add_message("system", "Welcome to MeistroCraft! Type your request below or use /help for commands.")
                
                while self.running:
                    try:
                        # Update the display
                        self.update_layout(layout)
                        live.update(layout)
                        
                        # Handle user input (this would need to be non-blocking)
                        # For now, we'll use a simple input mechanism
                        # In a full implementation, we'd use async input handling
                        time.sleep(0.1)
                        
                    except KeyboardInterrupt:
                        self.stop()
                        break
                    
        except Exception as e:
            self.console.print(f"UI Error: {e}", style="red")
            self.stop()
    
    def stop(self) -> None:
        """Stop the UI."""
        self.running = False
        if self.live:
            self.live.stop()

class AsyncInput:
    """Handles asynchronous input for the UI."""
    
    def __init__(self, ui: MeistroCraftUI, input_callback: Callable[[str], None]):
        self.ui = ui
        self.input_callback = input_callback
        self.input_thread = None
        self.running = False
    
    def start(self) -> None:
        """Start the input handling thread."""
        self.running = True
        self.input_thread = threading.Thread(target=self._input_loop, daemon=True)
        self.input_thread.start()
    
    def stop(self) -> None:
        """Stop the input handling."""
        self.running = False
        if self.input_thread:
            self.input_thread.join(timeout=1.0)
    
    def _input_loop(self) -> None:
        """Main input handling loop."""
        try:
            while self.running:
                try:
                    # Get input from user
                    user_input = input()
                    
                    if not self.running:
                        break
                    
                    # Handle special commands
                    if user_input.startswith('/'):
                        self._handle_command(user_input)
                    else:
                        # Send to callback for processing
                        if user_input.strip():
                            self.input_callback(user_input.strip())
                
                except EOFError:
                    break
                except KeyboardInterrupt:
                    self.ui.stop()
                    break
                    
        except Exception as e:
            self.ui.display_error(f"Input error: {e}")
    
    def _handle_command(self, command: str) -> None:
        """Handle special UI commands."""
        cmd = command.lower().strip()
        
        if cmd == '/help':
            self.ui.toggle_help()
        elif cmd == '/clear':
            self.ui.clear_conversation()
        elif cmd == '/quit' or cmd == '/exit':
            self.ui.stop()
        elif cmd == '/tokens':
            if self.ui.token_tracker:
                # Show token usage
                summary = self.ui.token_tracker.get_usage_summary()
                self.ui.add_message("system", f"Token usage: {summary.total_tokens:,} tokens (${summary.total_cost_usd:.4f})")
            else:
                self.ui.add_message("system", "Token tracking not available.")
        elif cmd == '/sessions':
            # Send command back to main handler for proper processing
            self.input_callback(command)
        elif cmd == '/context':
            # Send command back to main handler for proper processing
            self.input_callback(command)
        elif cmd.startswith('/cleanup-sessions'):
            self.input_callback(command)
        elif cmd.startswith('/repair-sessions'):
            self.input_callback(command)
        elif cmd.startswith('/delete-session'):
            self.input_callback(command)
        elif cmd.startswith('/test'):
            self.input_callback(command)
        elif cmd.startswith('/run'):
            self.input_callback(command)
        elif cmd.startswith('/build'):
            self.input_callback(command)
        else:
            self.ui.add_message("system", f"Unknown command: {command}. Type /help for available commands.")

def create_ui_manager(token_tracker=None) -> MeistroCraftUI:
    """Factory function to create UI manager."""
    return MeistroCraftUI(token_tracker)