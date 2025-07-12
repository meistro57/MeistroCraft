#!/usr/bin/env python3
"""
Interactive UI Mode for MeistroCraft
Provides the split terminal interface for interactive sessions.
"""

import sys
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from task_queue import get_task_queue, TaskPriority, TaskStatus

try:
    from terminal_ui import MeistroCraftUI, create_ui_manager
    from async_input import create_input_handler
except ImportError as e:
    print(f"UI components not available: {e}")
    print("Install required packages: pip install rich")
    sys.exit(1)

class InteractiveSession:
    """Manages an interactive MeistroCraft session with split terminal UI."""
    
    def __init__(self, config: Dict[str, Any], session_manager, token_tracker, session_id: Optional[str] = None, persistent_memory=None):
        self.config = config
        self.session_manager = session_manager
        self.token_tracker = token_tracker
        self.persistent_memory = persistent_memory
        self.session_id = session_id
        self.project_folder = None
        
        # Background task queue
        self.task_queue = get_task_queue()
        self._setup_task_callbacks()
        
        # UI components
        self.ui = create_ui_manager(token_tracker)
        self.input_handler = create_input_handler(self._handle_user_input)
        
        # State
        self.running = False
        self.processing_request = False
        
        # Initialize session
        self._initialize_session()
        
    def _initialize_session(self) -> None:
        """Initialize or continue a session."""
        if self.session_id:
            # Try to load existing session
            session_data = self.session_manager.load_session(self.session_id)
            if not session_data and len(self.session_id) == 8:
                # Try to find by short ID
                full_session_id = self.session_manager.find_session_by_short_id(self.session_id)
                if full_session_id:
                    self.session_id = full_session_id
                    session_data = self.session_manager.load_session(self.session_id)
            
            if session_data:
                self.ui.update_status(
                    session_id=self.session_id,
                    session_name=session_data.get('name', 'Unnamed Session'),
                    task_count=len(session_data.get('task_history', []))
                )
                self.ui.add_message("system", f"Resumed session: {session_data['name']}")
            else:
                self.ui.add_message("error", f"Session {self.session_id} not found. Creating new session.")
                self.session_id = self.session_manager.create_session()
        else:
            # Create new session
            self.session_id = self.session_manager.create_session()
            self.ui.update_status(
                session_id=self.session_id,
                session_name="New Session",
                task_count=0
            )
        
        # Update token usage for today
        self._update_token_display()
        
        # Update memory status display
        self._update_memory_display()
        
        # Update task queue display
        self._update_task_queue_display()
    
    def _update_token_display(self) -> None:
        """Update the token usage display."""
        if not self.token_tracker:
            return
        
        try:
            # Get today's usage
            today = datetime.now().date()
            start_of_day = datetime.combine(today, datetime.min.time())
            
            openai_summary = self.token_tracker.get_usage_summary(start_of_day, None, "openai")
            anthropic_summary = self.token_tracker.get_usage_summary(start_of_day, None, "anthropic")
            
            total_tokens = openai_summary.total_tokens + anthropic_summary.total_tokens
            total_cost = openai_summary.total_cost_usd + anthropic_summary.total_cost_usd
            
            self.ui.update_status(
                total_tokens_today=total_tokens,
                total_cost_today=total_cost,
                openai_tokens_today=openai_summary.total_tokens,
                anthropic_tokens_today=anthropic_summary.total_tokens
            )
        except Exception as e:
            # Don't let token tracking errors break the UI
            pass
    
    def _update_memory_display(self) -> None:
        """Update the memory usage display."""
        if not self.persistent_memory:
            return
        
        try:
            stats = self.persistent_memory.get_stats()
            self.ui.update_status(
                memory_entries=stats.total_entries,
                memory_size_mb=stats.total_size_mb,
                memory_limit_mb=stats.warning_threshold_mb
            )
        except Exception as e:
            # Don't let memory tracking errors break the UI
            pass
    
    def _setup_task_callbacks(self) -> None:
        """Set up callbacks for task queue events."""
        def on_progress(task):
            self.ui.add_message("system", f"📊 Task {task.task_id}: {task.progress_message} ({task.progress*100:.0f}%)")
            
        def on_completion(task):
            if task.status == TaskStatus.COMPLETED:
                self.ui.add_message("system", f"✅ Background task {task.task_id} completed: {task.task_description[:50]}...")
            elif task.status == TaskStatus.FAILED:
                self.ui.add_message("error", f"❌ Background task {task.task_id} failed: {task.error}")
        
        self.task_queue.add_progress_callback(on_progress)
        self.task_queue.add_completion_callback(on_completion)
    
    def _update_task_queue_display(self) -> None:
        """Update task queue status in UI."""
        try:
            queue_status = self.task_queue.get_queue_status()
            self.ui.update_status(
                background_tasks_running=queue_status['running_tasks'],
                background_tasks_queued=queue_status['queue_size'],
                background_tasks_total=queue_status['total_tasks']
            )
        except Exception as e:
            # Don't let task queue errors break the UI
            pass
    
    def _handle_user_input(self, user_input: str) -> None:
        """Handle user input from the UI."""
        if not user_input.strip():
            return
        
        # Handle special commands
        if user_input.startswith('/'):
            self._handle_command(user_input)
            return
        
        # Don't accept new requests while processing
        if self.processing_request:
            self.ui.add_message("system", "⏳ Please wait for the current request to complete.")
            return
        
        # Process the user request
        self._process_user_request(user_input)
    
    def _handle_command(self, command: str) -> None:
        """Handle special UI commands."""
        cmd = command.lower().strip()
        
        if cmd == '/help':
            self.ui.toggle_help()
        elif cmd == '/clear':
            self.ui.clear_conversation()
        elif cmd == '/quit' or cmd == '/exit':
            self.stop()
        elif cmd == '/tokens':
            self._show_token_usage()
        elif cmd == '/sessions':
            self._show_sessions()
        elif cmd == '/context':
            self._show_context()
        elif cmd == '/status':
            self._show_status()
        elif cmd == '/memory':
            self._show_memory_status()
        elif cmd == '/memory-report':
            self._export_memory_report()
        elif cmd == '/memory-clean':
            self._cleanup_memory()
        elif cmd == '/workspaces':
            self._show_workspaces()
        elif cmd == '/workspace':
            self._show_workspace_status()
        elif cmd == '/complete':
            self._complete_workspace()
        elif cmd == '/abandon':
            self._abandon_workspace()
        elif cmd == '/tasks':
            self._show_tasks()
        elif cmd == '/queue':
            self._show_queue_status()
        elif cmd.startswith('/bg '):
            self._queue_background_task(command[4:])  # Remove '/bg '
        elif cmd.startswith('/cancel '):
            self._cancel_task(command[8:])  # Remove '/cancel '
        elif cmd.startswith('/priority '):
            parts = command[10:].split(' ', 1)  # Remove '/priority '
            if len(parts) == 2:
                self._set_task_priority(parts[0], parts[1])
        elif cmd.startswith('/auto-accept '):
            self._set_auto_accept_level(command[13:])  # Remove '/auto-accept '
        elif cmd == '/auto-status':
            self._show_auto_accept_status()
        else:
            self.ui.add_message("system", f"Unknown command: {command}. Type /help for available commands.")
    
    def _show_token_usage(self) -> None:
        """Show detailed token usage information."""
        if not self.token_tracker:
            self.ui.add_message("system", "Token tracking not available.")
            return
        
        try:
            # Get last 7 days usage
            start_date = datetime.now() - timedelta(days=7)
            
            openai_summary = self.token_tracker.get_usage_summary(start_date, None, "openai")
            anthropic_summary = self.token_tracker.get_usage_summary(start_date, None, "anthropic")
            
            total_tokens = openai_summary.total_tokens + anthropic_summary.total_tokens
            total_cost = openai_summary.total_cost_usd + anthropic_summary.total_cost_usd
            
            usage_msg = f"""Token Usage (Last 7 days):
📊 OpenAI: {openai_summary.total_tokens:,} tokens (${openai_summary.total_cost_usd:.4f})
🤖 Anthropic: {anthropic_summary.total_tokens:,} tokens (${anthropic_summary.total_cost_usd:.4f})
💰 Total: {total_tokens:,} tokens (${total_cost:.4f})"""
            
            self.ui.add_message("system", usage_msg)
        except Exception as e:
            self.ui.add_message("error", f"Error getting token usage: {e}")
    
    def _show_sessions(self) -> None:
        """Show available sessions."""
        try:
            sessions = self.session_manager.list_sessions()
            if sessions:
                session_list = "Available Sessions:\n"
                for session in sessions[:5]:  # Show last 5 sessions
                    session_list += f"• {session['short_id']}: {session['name']} ({session['task_count']} tasks)\n"
                self.ui.add_message("system", session_list.strip())
            else:
                self.ui.add_message("system", "No sessions found.")
        except Exception as e:
            self.ui.add_message("error", f"Error listing sessions: {e}")
    
    def _show_context(self) -> None:
        """Show current session context."""
        if self.session_id:
            context = self.session_manager.get_session_context(self.session_id)
            if context:
                self.ui.add_message("system", f"Session Context: {context[:200]}...")
            else:
                self.ui.add_message("system", "No context available for current session.")
        else:
            self.ui.add_message("system", "No active session.")
    
    def _show_status(self) -> None:
        """Show detailed status information."""
        status_msg = f"""Current Status:
🆔 Session: {self.session_id[:8] if self.session_id else 'None'}
📁 Project: {self.project_folder or 'None'}
🔄 Processing: {'Yes' if self.processing_request else 'No'}
🔢 Tokens Today: {self.ui.status.total_tokens_today:,}
💰 Cost Today: ${self.ui.status.total_cost_today:.4f}"""
        
        self.ui.add_message("system", status_msg)
    
    def _show_memory_status(self) -> None:
        """Show persistent memory status."""
        if not self.persistent_memory:
            self.ui.add_message("system", "Persistent memory not available.")
            return
        
        try:
            stats = self.persistent_memory.get_stats()
            status_msg = f"""Persistent Memory Status:
📊 Entries: {stats.total_entries:,}
💾 Size: {stats.total_size_mb:.2f}MB / {stats.warning_threshold_mb:.0f}MB
📈 Usage: {(stats.total_size_mb/stats.warning_threshold_mb)*100:.1f}%"""
            
            if stats.by_type:
                status_msg += "\n\nBy Type:"
                for mem_type, count in stats.by_type.items():
                    status_msg += f"\n  {mem_type}: {count} entries"
            
            if stats.is_over_limit:
                status_msg += "\n\n🚨 WARNING: Memory usage exceeds limit!"
            elif stats.is_near_limit:
                status_msg += "\n\n⚠️  Warning: Memory usage approaching limit"
            
            self.ui.add_message("system", status_msg)
        except Exception as e:
            self.ui.add_message("error", f"Error getting memory status: {e}")
    
    def _export_memory_report(self) -> None:
        """Export detailed memory usage report."""
        if not self.persistent_memory:
            self.ui.add_message("system", "Persistent memory not available.")
            return
        
        try:
            import os
            from datetime import datetime
            
            # Create reports directory if it doesn't exist
            reports_dir = "reports"
            os.makedirs(reports_dir, exist_ok=True)
            
            # Generate report filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = os.path.join(reports_dir, f"memory_report_{timestamp}.json")
            
            # Export the report
            self.persistent_memory.export_memory_report(report_file)
            self.ui.add_message("system", f"📄 Memory report exported to: {report_file}")
            
        except Exception as e:
            self.ui.add_message("error", f"Error exporting memory report: {e}")
    
    def _cleanup_memory(self) -> None:
        """Manually trigger memory cleanup."""
        if not self.persistent_memory:
            self.ui.add_message("system", "Persistent memory not available.")
            return
        
        try:
            stats_before = self.persistent_memory.get_stats()
            deleted_count = self.persistent_memory._cleanup_memory()
            stats_after = self.persistent_memory.get_stats()
            
            size_freed = stats_before.total_size_mb - stats_after.total_size_mb
            
            if deleted_count > 0:
                self.ui.add_message("system", f"🧹 Cleaned up {deleted_count} entries, freed {size_freed:.2f}MB")
            else:
                self.ui.add_message("system", "✅ No cleanup needed - memory usage is within limits")
                
        except Exception as e:
            self.ui.add_message("error", f"Error during memory cleanup: {e}")
    
    def _show_workspaces(self) -> None:
        """Show all available workspaces."""
        if not self.session_manager.workspace_manager:
            self.ui.add_message("system", "Workspace isolation not available.")
            return
        
        try:
            workspaces = self.session_manager.workspace_manager.list_session_workspaces()
            if workspaces:
                workspace_list = "Available Workspaces:\n"
                for workspace in workspaces[:10]:  # Show last 10 workspaces
                    status_icon = {"active": "🟢", "paused": "⏸️", "completed": "✅", "failed": "❌"}.get(workspace['status'], "❓")
                    workspace_list += f"{status_icon} {workspace['workspace_id']}: {workspace['task_description'][:50]}...\n"
                    workspace_list += f"   Branch: {workspace['branch_name']} | Created: {workspace['created_at'][:19]}\n"
                self.ui.add_message("system", workspace_list.strip())
            else:
                self.ui.add_message("system", "No workspaces found.")
        except Exception as e:
            self.ui.add_message("error", f"Error listing workspaces: {e}")
    
    def _show_workspace_status(self) -> None:
        """Show current workspace status."""
        if not self.session_manager.workspace_manager:
            self.ui.add_message("system", "Workspace isolation not available.")
            return
        
        try:
            workspace = self.session_manager.workspace_manager.git_manager.get_workspace_by_session(self.session_id)
            if workspace:
                status = self.session_manager.workspace_manager.git_manager.get_workspace_status(workspace.workspace_id)
                status_msg = f"""Current Workspace Status:
🆔 ID: {workspace.workspace_id}
📝 Task: {workspace.task_description}
🌿 Branch: {workspace.branch_name}
📁 Path: {workspace.workspace_path}
🔄 Status: {workspace.status}
📅 Created: {workspace.created_at[:19]}
💾 Exists: {'Yes' if status.get('exists') else 'No'}
📝 Has Changes: {'Yes' if status.get('has_changes') else 'No'}"""
                
                if status.get('ahead_behind'):
                    ahead = status['ahead_behind']['ahead']
                    behind = status['ahead_behind']['behind']
                    status_msg += f"\n🔄 Commits: {ahead} ahead, {behind} behind base"
                
                self.ui.add_message("system", status_msg)
            else:
                self.ui.add_message("system", "No active workspace for current session.")
        except Exception as e:
            self.ui.add_message("error", f"Error getting workspace status: {e}")
    
    def _complete_workspace(self) -> None:
        """Complete the current workspace."""
        if not self.session_manager.workspace_manager:
            self.ui.add_message("system", "Workspace isolation not available.")
            return
        
        try:
            success = self.session_manager.complete_session(self.session_id, merge_back=True)
            if success:
                self.ui.add_message("system", "✅ Workspace completed and merged to main branch")
            else:
                self.ui.add_message("system", "❌ Failed to complete workspace")
        except Exception as e:
            self.ui.add_message("error", f"Error completing workspace: {e}")
    
    def _abandon_workspace(self) -> None:
        """Abandon the current workspace."""
        if not self.session_manager.workspace_manager:
            self.ui.add_message("system", "Workspace isolation not available.")
            return
        
        try:
            success = self.session_manager.abandon_session(self.session_id)
            if success:
                self.ui.add_message("system", "🗑️ Workspace abandoned (changes discarded)")
            else:
                self.ui.add_message("system", "❌ Failed to abandon workspace")
        except Exception as e:
            self.ui.add_message("error", f"Error abandoning workspace: {e}")
    
    def _show_tasks(self) -> None:
        """Show all background tasks."""
        try:
            tasks = self.task_queue.list_tasks(limit=20)
            if tasks:
                task_list = "Background Tasks:\n"
                for task in tasks:
                    status_icon = {
                        TaskStatus.PENDING: "⏳",
                        TaskStatus.QUEUED: "📋",
                        TaskStatus.RUNNING: "🔄",
                        TaskStatus.COMPLETED: "✅",
                        TaskStatus.FAILED: "❌",
                        TaskStatus.CANCELLED: "🚫",
                        TaskStatus.PAUSED: "⏸️"
                    }.get(task.status, "❓")
                    
                    progress_str = f" ({task.progress*100:.0f}%)" if task.status == TaskStatus.RUNNING else ""
                    auto_accept_str = " 🤖" if task.auto_accept else ""
                    task_list += f"{status_icon} {task.task_id}: {task.task_description[:50]}...{progress_str}{auto_accept_str}\n"
                    
                    session_info = f"   Session: {task.session_id[:8]} | Priority: {task.priority.name} | Created: {task.created_at[:19]}"
                    if task.auto_accept_reason:
                        session_info += f"\n   Auto-accept: {task.auto_accept_reason[:60]}..."
                    task_list += session_info + "\n"
                    
                    if task.error:
                        task_list += f"   Error: {task.error[:50]}...\n"
                    
                self.ui.add_message("system", task_list.strip())
            else:
                self.ui.add_message("system", "No background tasks found.")
        except Exception as e:
            self.ui.add_message("error", f"Error listing tasks: {e}")
    
    def _show_queue_status(self) -> None:
        """Show task queue status."""
        try:
            status = self.task_queue.get_queue_status()
            status_msg = f"""Task Queue Status:
📊 Total Tasks: {status['total_tasks']}
🔄 Running: {status['running_tasks']}/{status['max_workers']} workers
📋 Queued: {status['queue_size']}
✅ Recently Completed: {status['recently_completed']}

Status Breakdown:"""
            
            for status_name, count in status['status_counts'].items():
                if count > 0:
                    status_msg += f"\n  {status_name.title()}: {count}"
            
            self.ui.add_message("system", status_msg)
        except Exception as e:
            self.ui.add_message("error", f"Error getting queue status: {e}")
    
    def _queue_background_task(self, user_input: str) -> None:
        """Queue a task for background execution."""
        if not user_input.strip():
            self.ui.add_message("system", "Usage: /bg <task description>")
            return
        
        try:
            # Get workspace ID if available
            workspace_id = None
            if self.session_manager.workspace_manager:
                workspace = self.session_manager.workspace_manager.git_manager.get_workspace_by_session(self.session_id)
                if workspace:
                    workspace_id = workspace.workspace_id
            
            # Add task to background queue
            task_id = self.task_queue.add_task(
                session_id=self.session_id,
                user_input=user_input,
                task_description=f"Background: {user_input[:50]}...",
                priority=TaskPriority.MEDIUM,
                workspace_id=workspace_id,
                auto_accept=False  # For now, no auto-accept
            )
            
            self.ui.add_message("system", f"📋 Queued background task {task_id}: {user_input[:50]}...")
            
        except Exception as e:
            self.ui.add_message("error", f"Error queuing background task: {e}")
    
    def _cancel_task(self, task_id: str) -> None:
        """Cancel a background task."""
        try:
            success = self.task_queue.cancel_task(task_id)
            if success:
                self.ui.add_message("system", f"🚫 Cancelled task {task_id}")
            else:
                self.ui.add_message("system", f"❌ Could not cancel task {task_id} (may be running or completed)")
        except Exception as e:
            self.ui.add_message("error", f"Error cancelling task: {e}")
    
    def _set_task_priority(self, task_id: str, priority_str: str) -> None:
        """Set task priority."""
        try:
            priority_map = {
                'low': TaskPriority.LOW,
                'medium': TaskPriority.MEDIUM,
                'high': TaskPriority.HIGH,
                'urgent': TaskPriority.URGENT
            }
            
            priority = priority_map.get(priority_str.lower())
            if not priority:
                self.ui.add_message("system", "Priority must be: low, medium, high, urgent")
                return
            
            task = self.task_queue.get_task(task_id)
            if not task:
                self.ui.add_message("system", f"Task {task_id} not found")
                return
            
            if task.status in [TaskStatus.PENDING, TaskStatus.QUEUED, TaskStatus.PAUSED]:
                task.priority = priority
                self.task_queue._save_tasks()
                self.ui.add_message("system", f"📊 Set task {task_id} priority to {priority.name}")
            else:
                self.ui.add_message("system", f"Cannot change priority of {task.status.value} task")
                
        except Exception as e:
            self.ui.add_message("error", f"Error setting task priority: {e}")
    
    def _set_auto_accept_level(self, level_str: str) -> None:
        """Set auto-accept level."""
        try:
            from auto_accept import get_auto_accept_manager, AutoAcceptLevel
            
            level_map = {
                'none': AutoAcceptLevel.NONE,
                'safe': AutoAcceptLevel.SAFE,
                'trusted': AutoAcceptLevel.TRUSTED,
                'aggressive': AutoAcceptLevel.AGGRESSIVE
            }
            
            level = level_map.get(level_str.lower())
            if not level:
                self.ui.add_message("system", "Auto-accept level must be: none, safe, trusted, aggressive")
                return
            
            auto_accept_manager = get_auto_accept_manager()
            auto_accept_manager.set_global_level(level)
            self.ui.add_message("system", f"🤖 Set auto-accept level to: {level.value}")
            
        except Exception as e:
            self.ui.add_message("error", f"Error setting auto-accept level: {e}")
    
    def _show_auto_accept_status(self) -> None:
        """Show auto-accept status and configuration."""
        try:
            from auto_accept import get_auto_accept_manager
            
            auto_accept_manager = get_auto_accept_manager()
            stats = auto_accept_manager.get_stats()
            
            status_msg = f"""Auto-Accept Configuration:
🤖 Global Level: {stats['global_level']}
📝 Total Rules: {stats['total_rules']}
✅ Trusted File Types: {stats['trusted_file_types']}
🔒 Safe Actions: {stats['safe_actions']}
⚠️  Dangerous Actions: {stats['dangerous_actions']}

Levels:
  none: Manual approval for all tasks
  safe: Auto-accept read-only operations
  trusted: Auto-accept file creation/modification for trusted types  
  aggressive: Auto-accept most operations (except dangerous)"""
            
            self.ui.add_message("system", status_msg)
            
        except Exception as e:
            self.ui.add_message("error", f"Error getting auto-accept status: {e}")
    
    def _process_user_request(self, user_input: str) -> None:
        """Process a user request in a separate thread."""
        self.processing_request = True
        self.ui.add_message("user", user_input)
        
        # Start processing in background thread
        processing_thread = threading.Thread(
            target=self._process_request_background,
            args=(user_input,),
            daemon=True
        )
        processing_thread.start()
    
    def _process_request_background(self, user_input: str) -> None:
        """Process user request in background thread."""
        try:
            from main import generate_task_with_gpt4, run_claude_task, setup_project_folder
            from main import create_project_summary, create_project_readme, validate_task
            
            # Set up project folder for first task if not already set
            if not self.project_folder:
                self.project_folder = setup_project_folder(user_input[:30])
                self.ui.add_message("system", f"📁 Created project folder: {self.project_folder}")
            
            # Show progress
            self.ui.show_progress("Generating task with GPT-4")
            
            # Generate task with GPT-4
            task = generate_task_with_gpt4(
                user_input, self.config, self.project_folder, 
                self.token_tracker, self.session_id
            )
            
            if not task:
                self.ui.hide_progress()
                self.ui.add_message("error", "Failed to generate task. Please check your OpenAI API key.")
                self.processing_request = False
                return
            
            # Update progress
            self.ui.show_progress(f"Executing with Claude: {task['action']}")
            self.ui.add_message("system", f"🎯 GPT-4 Task: {task['action']} - {task['instruction'][:60]}...")
            
            # Execute with Claude
            session_data = self.session_manager.load_session(self.session_id)
            existing_tasks = len(session_data.get('task_history', [])) if session_data else 0
            
            if existing_tasks == 0:
                # First task - let Claude create a new session
                result = run_claude_task(task, self.config, None, None, self.project_folder, self.token_tracker)
            else:
                # Subsequent tasks - try to resume Claude session
                claude_session_id = None
                if session_data and session_data.get('task_history'):
                    last_result = session_data['task_history'][-1].get('result', {})
                    claude_session_id = last_result.get('session_id')
                result = run_claude_task(task, self.config, claude_session_id, None, self.project_folder, self.token_tracker)
            
            # Hide progress
            self.ui.hide_progress()
            
            if result.get("success"):
                # Save to session manager
                self.session_manager.add_task_to_session(self.session_id, task, result)
                
                # Update UI
                self.ui.add_message("claude", result['result'][:500] + ("..." if len(result['result']) > 500 else ""))
                self.ui.update_status(task_count=existing_tasks + 1)
                
                # Create project summary and README for first task
                if existing_tasks == 0:
                    create_project_summary(self.project_folder, task, result)
                    create_project_readme(self.project_folder, task['instruction'])
                
                # Update token display
                self._update_token_display()
                
                # Update memory display
                self._update_memory_display()
                
            else:
                self.ui.add_message("error", f"Claude failed: {result.get('error', 'Unknown error')}")
            
        except Exception as e:
            self.ui.hide_progress()
            self.ui.add_message("error", f"Processing error: {e}")
        finally:
            self.processing_request = False
    
    def run(self) -> None:
        """Run the interactive session."""
        try:
            self.running = True
            
            # Start input handler
            self.input_handler.start()
            
            # Run the UI in a separate thread
            ui_thread = threading.Thread(target=self._run_ui, daemon=True)
            ui_thread.start()
            
            # Main loop
            while self.running:
                try:
                    # Update displays periodically
                    self._update_token_display()
                    self._update_memory_display()
                    self._update_task_queue_display()
                    time.sleep(1)
                except KeyboardInterrupt:
                    self.stop()
                    break
                    
        except Exception as e:
            print(f"Session error: {e}")
        finally:
            self.stop()
    
    def _run_ui(self) -> None:
        """Run the UI in a separate thread."""
        try:
            layout = self.ui.create_layout()
            
            # Import Live here to avoid issues if rich is not available
            from rich.live import Live
            
            with Live(layout, console=self.ui.console, refresh_per_second=4, screen=True) as live:
                while self.running:
                    try:
                        # Update current input from input handler
                        if hasattr(self.input_handler, 'get_current_input'):
                            self.ui.current_input = self.input_handler.get_current_input()
                        
                        # Update the display
                        self.ui.update_layout(layout)
                        live.update(layout)
                        
                        time.sleep(0.25)
                        
                    except KeyboardInterrupt:
                        break
                    
        except Exception as e:
            print(f"UI thread error: {e}")
        finally:
            self.running = False
    
    def stop(self) -> None:
        """Stop the interactive session."""
        self.running = False
        
        # Stop input handler
        if self.input_handler:
            self.input_handler.stop()
        
        # Shutdown task queue
        try:
            from task_queue import shutdown_task_queue
            shutdown_task_queue()
        except Exception as e:
            print(f"Warning: Error shutting down task queue: {e}")
        
        # Give threads time to stop
        time.sleep(0.5)
        
        print("\n👋 Thanks for using MeistroCraft!")

def run_interactive_ui(config: Dict[str, Any], session_manager, token_tracker, session_id: Optional[str] = None, persistent_memory=None) -> None:
    """Run the interactive UI mode."""
    try:
        session = InteractiveSession(config, session_manager, token_tracker, session_id, persistent_memory)
        session.run()
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"Interactive mode error: {e}")
        print("Falling back to standard mode...")