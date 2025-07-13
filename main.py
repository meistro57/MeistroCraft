#!/usr/bin/env python3
"""
MeistroCraft - GPT-4 Orchestrator with Claude Code CLI
Main orchestrator script that coordinates between GPT-4 planner and Claude coder.
"""

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

try:
    from openai import OpenAI
except ImportError:
    print("OpenAI library not found. Install with: pip install openai")
    OpenAI = None

from naming_agent import generate_creative_project_name

from token_tracker import TokenTracker, TokenUsage, UsageLimits
from persistent_memory import PersistentMemory, MemoryType, MemoryPriority
from workspace_manager import WorkspaceManager
from github_client import create_github_client, GitHubClient, GitHubClientError
from github_workflows import create_workflow_integration, WorkflowIntegration, GitHubWorkflowError
from cicd_integration import create_cicd_integration, GitHubActionsManager, CICDIntegrationError
from build_monitor import BuildStatusMonitor
from deployment_automation import create_deployment_automation, DeploymentAutomation

def load_config(config_path: str = "config/config.json") -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in config file: {e}")
        sys.exit(1)

def setup_environment(config: Dict[str, Any]) -> None:
    """Set up environment variables for API keys."""
    if config.get("anthropic_api_key") and config["anthropic_api_key"] != "<YOUR_ANTHROPIC_API_KEY>":
        os.environ["ANTHROPIC_API_KEY"] = config["anthropic_api_key"]
    
    # Check if API key is set
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY not set. Please update config.json or set environment variable.")
        sys.exit(1)

class SessionManager:
    """Manages Claude CLI sessions for multi-turn conversations."""
    
    def __init__(self, sessions_dir: str = "sessions", workspace_manager: Optional[WorkspaceManager] = None):
        self.sessions_dir = sessions_dir
        self.workspace_manager = workspace_manager
        os.makedirs(sessions_dir, exist_ok=True)
    
    def create_session(self, name: Optional[str] = None, task_description: Optional[str] = None) -> str:
        """Create a new session and return session ID."""
        session_id = str(uuid.uuid4())
        
        # Create sandboxed project folder for this session
        project_folder = self._create_session_project_folder(session_id, task_description or "session_workspace")
        
        session_data = {
            "id": session_id,
            "name": name or f"Session {session_id}",
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
            "task_history": [],
            "context": "",
            "workspace_id": None,
            "workspace_path": None,
            "project_folder": project_folder
        }
        
        # Create isolated workspace if workspace manager is available
        if self.workspace_manager and task_description:
            workspace_path = self.workspace_manager.create_session_workspace(session_id, task_description)
            if workspace_path:
                workspace = self.workspace_manager.git_manager.get_workspace_by_session(session_id)
                if workspace:
                    session_data["workspace_id"] = workspace.workspace_id
                    session_data["workspace_path"] = workspace_path
                    print(f"🏗️  Created isolated workspace for session {session_id[:8]}")
        
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        print(f"📁 Created project folder: {project_folder}")
        return session_id
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data by ID with error handling."""
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        if os.path.exists(session_file):
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                # Validate required fields and repair if necessary
                if not isinstance(data, dict):
                    print(f"⚠️  Session {session_id[:8]} has invalid format, skipping")
                    return None
                
                # Ensure required fields exist
                if "id" not in data:
                    data["id"] = session_id
                if "name" not in data:
                    data["name"] = f"Session {session_id}"
                if "created_at" not in data:
                    data["created_at"] = datetime.now().isoformat()
                if "last_used" not in data:
                    data["last_used"] = datetime.now().isoformat()
                if "task_history" not in data:
                    data["task_history"] = []
                if "context" not in data:
                    data["context"] = ""
                if "project_folder" not in data:
                    data["project_folder"] = None
                
                return data
                
            except json.JSONDecodeError as e:
                print(f"⚠️  Session {session_id[:8]} has corrupted JSON: {e}")
                return None
            except Exception as e:
                print(f"⚠️  Error loading session {session_id[:8]}: {e}")
                return None
        return None
    
    def find_session_by_short_id(self, short_id: str) -> Optional[str]:
        """Find full session ID by short ID (first 8 characters)."""
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith('.json'):
                full_id = filename[:-5]
                if full_id.startswith(short_id):
                    return full_id
        return None
    
    def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        return os.path.exists(session_file)
    
    def save_session(self, session_data: Dict[str, Any]) -> None:
        """Save session data."""
        session_id = session_data["id"]
        session_data["last_used"] = datetime.now().isoformat()
        
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions with error handling."""
        sessions = []
        corrupted_count = 0
        
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith('.json'):
                session_id = filename[:-5]
                session_data = self.load_session(session_id)
                if session_data:
                    sessions.append({
                        "id": session_id,
                        "short_id": session_id[:8],
                        "name": session_data.get("name", "Unnamed"),
                        "created_at": session_data.get("created_at", ""),
                        "last_used": session_data.get("last_used", ""),
                        "task_count": len(session_data.get("task_history", []))
                    })
                else:
                    corrupted_count += 1
        
        # Sort by last used (most recent first)
        sessions.sort(key=lambda x: x["last_used"], reverse=True)
        
        if corrupted_count > 0:
            print(f"⚠️  Found {corrupted_count} corrupted session files. Run --repair-sessions to fix them.")
        
        return sessions
    
    def add_task_to_session(self, session_id: str, task: Dict[str, Any], result: Dict[str, Any]) -> None:
        """Add a completed task to session history."""
        session_data = self.load_session(session_id)
        if session_data:
            task_entry = {
                "timestamp": datetime.now().isoformat(),
                "task": task,
                "result": result,
                "success": result.get("success", False)
            }
            session_data["task_history"].append(task_entry)
            
            # Update context with recent successful tasks
            if result.get("success"):
                result_text = str(result.get('result', '')).replace('\n', ' ')[:80]
                context_update = f"\n[{task['action']}] {task['instruction'][:50]}... -> {result_text}..."
                session_data["context"] = (session_data.get("context", "") + context_update)[-2000:]  # Keep last 2000 chars
            
            self.save_session(session_data)
    
    def get_session_context(self, session_id: str) -> str:
        """Get session context for including in prompts."""
        session_data = self.load_session(session_id)
        if session_data and session_data.get("context"):
            return f"\nSession Context (previous actions):{session_data['context']}"
        return ""
    
    def complete_session(self, session_id: str, merge_workspace: bool = True) -> bool:
        """Complete a session and handle workspace cleanup."""
        session_data = self.load_session(session_id)
        if not session_data:
            return False
        
        # Complete workspace if it exists
        if self.workspace_manager and session_data.get("workspace_id"):
            success = self.workspace_manager.complete_session_workspace(session_id, merge_workspace)
            if success:
                # Update session data to reflect completion
                session_data["workspace_completed"] = True
                session_data["workspace_merged"] = merge_workspace
                session_data["completed_at"] = datetime.now().isoformat()
                self.save_session(session_data)
                print(f"✅ Completed session {session_id[:8]} workspace")
            return success
        
        return True
    
    def abandon_session(self, session_id: str) -> bool:
        """Abandon a session without merging workspace changes."""
        session_data = self.load_session(session_id)
        if not session_data:
            return False
        
        # Abandon workspace if it exists
        if self.workspace_manager and session_data.get("workspace_id"):
            workspace = self.workspace_manager.git_manager.get_workspace_by_session(session_id)
            if workspace:
                success = self.workspace_manager.git_manager.abandon_workspace(workspace.workspace_id)
                if success:
                    session_data["workspace_abandoned"] = True
                    session_data["abandoned_at"] = datetime.now().isoformat()
                    self.save_session(session_data)
                    print(f"🗑️  Abandoned session {session_id[:8]} workspace")
                return success
        
        return True
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session file permanently."""
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        if os.path.exists(session_file):
            try:
                # Load session data to get project folder before deletion
                session_data = self.load_session(session_id)
                
                # Clean up associated project folder if it exists
                if session_data and session_data.get("project_folder"):
                    project_folder = session_data["project_folder"]
                    self._cleanup_session_project_folder(project_folder, session_id)
                
                os.remove(session_file)
                print(f"🗑️  Deleted session {session_id[:8]}")
                return True
            except Exception as e:
                print(f"❌ Failed to delete session {session_id[:8]}: {e}")
                return False
        return False
    
    def _cleanup_session_project_folder(self, project_folder: str, session_id: str) -> None:
        """Clean up the project folder associated with a session."""
        try:
            if os.path.exists(project_folder):
                # Check if this is actually a session folder by looking for .session marker
                session_marker = os.path.join(project_folder, ".session")
                if os.path.exists(session_marker):
                    with open(session_marker, 'r') as f:
                        marker_data = json.load(f)
                    
                    # Only delete if it belongs to this session
                    if marker_data.get("session_id") == session_id:
                        import shutil
                        shutil.rmtree(project_folder)
                        print(f"🗑️  Cleaned up project folder: {project_folder}")
                    else:
                        print(f"⚠️  Project folder belongs to different session, skipping cleanup")
                else:
                    print(f"⚠️  Project folder {project_folder} is not a session folder, skipping cleanup")
        except Exception as e:
            print(f"❌ Error cleaning up project folder {project_folder}: {e}")
    
    def cleanup_old_sessions(self, days_old: int = 30, max_sessions: int = 50) -> Dict[str, int]:
        """Clean up old sessions based on age and session count."""
        cleanup_stats = {
            "deleted_by_age": 0,
            "deleted_by_count": 0,
            "corrupted_deleted": 0,
            "total_remaining": 0
        }
        
        sessions = []
        corrupted_files = []
        
        # First pass: identify valid sessions and corrupted files
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith('.json'):
                session_id = filename[:-5]
                session_file = os.path.join(self.sessions_dir, filename)
                
                try:
                    session_data = self.load_session(session_id)
                    if session_data:
                        sessions.append({
                            "id": session_id,
                            "last_used": session_data.get("last_used", ""),
                            "created_at": session_data.get("created_at", ""),
                            "task_count": len(session_data.get("task_history", []))
                        })
                    else:
                        corrupted_files.append(session_file)
                except (json.JSONDecodeError, FileNotFoundError, Exception):
                    corrupted_files.append(session_file)
        
        # Remove corrupted files
        for corrupted_file in corrupted_files:
            try:
                os.remove(corrupted_file)
                cleanup_stats["corrupted_deleted"] += 1
                print(f"🗑️  Removed corrupted session file: {os.path.basename(corrupted_file)}")
            except Exception as e:
                print(f"❌ Failed to remove corrupted file {corrupted_file}: {e}")
        
        # Sort sessions by last_used (oldest first)
        sessions.sort(key=lambda x: x["last_used"] or x["created_at"])
        
        # Delete sessions older than specified days
        cutoff_date = datetime.now() - timedelta(days=days_old)
        for session in sessions[:]:
            last_used_str = session["last_used"] or session["created_at"]
            if last_used_str:
                try:
                    last_used = datetime.fromisoformat(last_used_str.replace('Z', '+00:00'))
                    if last_used < cutoff_date:
                        if self.delete_session(session["id"]):
                            cleanup_stats["deleted_by_age"] += 1
                            sessions.remove(session)
                except Exception:
                    # If we can't parse the date, skip this session
                    pass
        
        # If we still have too many sessions, delete oldest ones
        if len(sessions) > max_sessions:
            sessions_to_delete = sessions[:len(sessions) - max_sessions]
            for session in sessions_to_delete:
                if self.delete_session(session["id"]):
                    cleanup_stats["deleted_by_count"] += 1
                    sessions.remove(session)
        
        cleanup_stats["total_remaining"] = len(sessions)
        return cleanup_stats
    
    def repair_sessions(self) -> Dict[str, int]:
        """Attempt to repair corrupted session files."""
        repair_stats = {
            "repaired": 0,
            "deleted": 0,
            "unchanged": 0
        }
        
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith('.json'):
                session_id = filename[:-5]
                session_file = os.path.join(self.sessions_dir, filename)
                
                try:
                    with open(session_file, 'r') as f:
                        content = f.read().strip()
                    
                    # Try to parse as JSON
                    json.loads(content)
                    repair_stats["unchanged"] += 1
                    
                except json.JSONDecodeError:
                    # Try to repair common JSON issues
                    try:
                        # Remove trailing commas and fix basic issues
                        import re
                        fixed_content = re.sub(r',(\s*[}\]])', r'\1', content)
                        
                        # Try parsing the fixed content
                        data = json.loads(fixed_content)
                        
                        # Ensure required fields exist
                        if "id" not in data:
                            data["id"] = session_id
                        if "name" not in data:
                            data["name"] = f"Session {session_id}"
                        if "created_at" not in data:
                            data["created_at"] = datetime.now().isoformat()
                        if "last_used" not in data:
                            data["last_used"] = datetime.now().isoformat()
                        if "task_history" not in data:
                            data["task_history"] = []
                        if "context" not in data:
                            data["context"] = ""
                        
                        # Write the repaired session
                        with open(session_file, 'w') as f:
                            json.dump(data, f, indent=2)
                        
                        repair_stats["repaired"] += 1
                        print(f"🔧 Repaired session {session_id[:8]}")
                        
                    except Exception:
                        # Can't repair, delete the file
                        try:
                            os.remove(session_file)
                            repair_stats["deleted"] += 1
                            print(f"🗑️  Deleted unrepairable session {session_id[:8]}")
                        except Exception as e:
                            print(f"❌ Failed to delete session {session_id[:8]}: {e}")
                
                except Exception as e:
                    print(f"❌ Error processing session {session_id[:8]}: {e}")
        
        return repair_stats
    
    def _create_session_project_folder(self, session_id: str, task_description: str) -> str:
        """Create a sandboxed project folder for a session."""
        from naming_agent import generate_creative_project_name
        
        # Generate creative name for the project folder
        try:
            # Use a basic config for naming if none provided
            basic_config = {"openai_api_key": "dummy"}  # Just for naming
            creative_name = generate_creative_project_name(task_description, basic_config)
            print(f"🎨 Generated project name: {creative_name}")
        except Exception as e:
            print(f"⚠️  Naming agent failed, using fallback: {e}")
            creative_name = _fallback_project_name(task_description)
        
        # Create projects directory if it doesn't exist
        projects_dir = "projects"
        os.makedirs(projects_dir, exist_ok=True)
        
        # Create unique project folder with session prefix for sandboxing
        session_prefix = f"session_{session_id[:8]}"
        project_folder_name = f"{session_prefix}_{creative_name}"
        project_folder = os.path.join(projects_dir, project_folder_name)
        
        # Ensure uniqueness
        counter = 1
        original_folder = project_folder
        while os.path.exists(project_folder):
            project_folder = f"{original_folder}_{counter}"
            counter += 1
        
        # Create the sandboxed project folder
        os.makedirs(project_folder, exist_ok=True)
        
        # Create a .session file to mark this as a session folder
        session_marker_file = os.path.join(project_folder, ".session")
        with open(session_marker_file, 'w') as f:
            json.dump({
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "task_description": task_description,
                "sandboxed": True
            }, f, indent=2)
        
        # Create basic project structure
        readme_content = f"""# {creative_name}

## Session Information
- **Session ID**: {session_id[:8]}...
- **Created**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Description**: {task_description}

## Workspace
This is a sandboxed workspace for the MeistroCraft session. All files created during this session will be contained within this folder.

## Getting Started
1. Use the terminal commands to interact with this project
2. Files created by Claude will appear in this directory
3. Use `/test`, `/run`, and `/build` commands to work with your project
"""
        readme_file = os.path.join(project_folder, "README.md")
        with open(readme_file, 'w') as f:
            f.write(readme_content)
        
        return project_folder

def run_claude_task(task: Dict[str, Any], config: Dict[str, Any], session_id: Optional[str] = None, session_manager: Optional[SessionManager] = None, project_folder: Optional[str] = None, token_tracker: Optional[TokenTracker] = None) -> Dict[str, Any]:
    """
    Execute a task using Claude Code CLI.
    
    Args:
        task: Task dictionary with action, instruction, etc.
        config: Configuration dictionary
        
    Returns:
        Dictionary with result and metadata
    """
    # Compose the prompt for Claude based on the task
    if task.get("filename"):
        prompt_text = f"Please apply the following instruction.\nFile: {task['filename']}\nInstruction: {task['instruction']}"
        if task.get("context"):
            prompt_text += f"\nAdditional context:\n{task['context']}"
    else:
        prompt_text = task["instruction"]
    
    # Add session context if available
    if session_id and session_manager:
        session_context = session_manager.get_session_context(session_id)
        if session_context:
            prompt_text += session_context
    
    # Build the CLI command
    cli_cmd = [
        "claude", "-p", prompt_text,
        "--output-format", "json",
        "--max-turns", str(config.get("max_turns", 5))
    ]
    
    # Add session resume if continuing an existing session
    # Only resume if we have evidence that the Claude CLI session already exists
    if session_id and session_manager:
        session_data = session_manager.load_session(session_id)
        # Only resume if this session has had successful Claude interactions before
        if session_data and session_data.get("task_history"):
            cli_cmd += ["--resume", session_id]
    
    # Set working directory if we have a project folder
    working_dir = project_folder if project_folder else None
    
    # Add allowed tools
    allowed_tools = task.get("tools") or config.get("allowed_tools", ["Read", "Write"])
    if allowed_tools:
        cli_cmd += ["--allowedTools", ",".join(allowed_tools)]
    
    # Add permission mode
    permission_mode = config.get("permission_mode", "acceptEdits")
    cli_cmd += ["--permission-mode", permission_mode]
    
    print(f"Running Claude CLI: {' '.join(cli_cmd[:3])} [additional flags omitted]")
    
    try:
        # Run the Claude CLI subprocess
        result = subprocess.run(cli_cmd, capture_output=True, text=True, timeout=300, cwd=working_dir)
        
        if result.returncode != 0:
            print(f"Claude CLI error (exit code {result.returncode}):")
            print(result.stderr)
            return {
                "success": False,
                "error": result.stderr,
                "exit_code": result.returncode
            }
        
        # Parse JSON output
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError:
            print("Failed to parse Claude output as JSON:")
            print(result.stdout)
            return {
                "success": False,
                "error": "Invalid JSON output",
                "raw_output": result.stdout
            }
        
        # Track Claude token usage if available in response
        if token_tracker and response.get("usage"):
            try:
                model = config.get("claude_model", "claude-sonnet-4-20250514")
                usage_data = response["usage"]
                
                # Create a mock response object for the tracker
                class MockUsage:
                    def __init__(self, input_tokens, output_tokens):
                        self.input_tokens = input_tokens
                        self.output_tokens = output_tokens
                
                class MockResponse:
                    def __init__(self, usage):
                        self.usage = usage
                
                mock_usage = MockUsage(
                    usage_data.get("input_tokens", 0),
                    usage_data.get("output_tokens", 0)
                )
                mock_response = MockResponse(mock_usage)
                
                usage = TokenUsage.from_anthropic_response(mock_response, model, session_id, task.get("action", "claude_task"))
                token_tracker.track_usage(usage)
                print(f"🔢 Claude Usage: {usage.input_tokens} in + {usage.output_tokens} out = {usage.total_tokens} tokens (${usage.cost_usd:.4f})")
            except Exception as e:
                print(f"Warning: Could not track Claude token usage: {e}")
        
        # Check for Claude-reported errors
        if response.get("is_error"):
            print(f"Claude reported an error: {response.get('subtype', 'Unknown error')}")
            return {
                "success": False,
                "error": response.get("subtype", "Unknown error"),
                "response": response
            }
        
        result = {
            "success": True,
            "result": response.get("result", ""),
            "response": response,
            "session_id": response.get("session_id")  # Claude CLI includes session_id in JSON output
        }
        
        # Save task to session if session manager is provided
        if session_manager:
            actual_session_id = session_id or response.get("session_id")
            if actual_session_id:
                session_manager.add_task_to_session(actual_session_id, task, result)
        
        return result
        
    except subprocess.TimeoutExpired:
        print("Claude CLI timed out after 5 minutes")
        return {
            "success": False,
            "error": "Timeout after 5 minutes"
        }
    except Exception as e:
        print(f"Unexpected error running Claude CLI: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def load_example_task(task_path: str = "tasks/example_task.json") -> Dict[str, Any]:
    """Load an example task from JSON file."""
    try:
        with open(task_path, 'r') as f:
            task = json.load(f)
        return task
    except FileNotFoundError:
        print(f"Task file not found: {task_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in task file: {e}")
        sys.exit(1)

def validate_task(task: Dict[str, Any]) -> bool:
    """Validate that a task has required fields."""
    required_fields = ["action", "instruction"]
    for field in required_fields:
        if field not in task:
            print(f"Task missing required field: {field}")
            return False
    return True

def get_function_schema() -> Dict[str, Any]:
    """Define the OpenAI function calling schema for Claude tasks."""
    return {
        "name": "invoke_claude_task",
        "description": "Instruct Claude Code CLI to perform a coding task.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Type of code task",
                    "enum": ["create_file", "modify_file", "explain_code", "run_tests", "debug_code", "refactor_code"]
                },
                "filename": {
                    "type": "string",
                    "description": "Target file path (for create/modify actions)"
                },
                "instruction": {
                    "type": "string",
                    "description": "Detailed instructions for Claude about what to do"
                },
                "context": {
                    "type": "string",
                    "description": "Optional additional context (code snippet, error message, etc.)"
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional list of tools Claude is allowed to use for this task"
                }
            },
            "required": ["action", "instruction"]
        }
    }

def setup_project_folder(project_description: str, config: Optional[Dict[str, Any]] = None) -> str:
    """Create and setup a project folder with a creative name generated from description."""
    
    # Generate creative name using naming agent
    if config:
        try:
            creative_name = generate_creative_project_name(project_description, config)
            print(f"🎨 Generated project name: {creative_name}")
        except Exception as e:
            print(f"⚠️  Naming agent failed, using fallback: {e}")
            creative_name = _fallback_project_name(project_description)
    else:
        creative_name = _fallback_project_name(project_description)
    
    # Create projects directory if it doesn't exist
    projects_dir = "projects"
    os.makedirs(projects_dir, exist_ok=True)
    
    # Create unique project folder
    project_folder = os.path.join(projects_dir, creative_name)
    counter = 1
    original_folder = project_folder
    
    while os.path.exists(project_folder):
        project_folder = f"{original_folder}-{counter}"
        counter += 1
    
    os.makedirs(project_folder, exist_ok=True)
    return project_folder

def _fallback_project_name(description: str) -> str:
    """Fallback method for generating project names when naming agent fails."""
    # Clean and truncate description for filesystem
    clean_name = "".join(c for c in description if c.isalnum() or c in (' ', '-', '_')).rstrip()
    clean_name = clean_name.replace(' ', '_').lower()
    
    # Limit to 30 characters as before
    return clean_name[:30]

def generate_task_with_gpt4(user_request: str, config: Dict[str, Any], project_folder: Optional[str] = None, token_tracker: Optional[TokenTracker] = None, session_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Use GPT-4 to generate a task from user request."""
    if not OpenAI or not config.get("openai_api_key") or config["openai_api_key"] == "<YOUR_OPENAI_API_KEY>":
        print("❌ OpenAI integration not available (missing API key or library)")
        return None
    
    client = OpenAI(api_key=config["openai_api_key"])
    
    system_prompt = """
You are a project planning assistant working with Claude Code CLI. 
Analyze user requests and create structured tasks for Claude to execute.

Guidelines:
- Break complex requests into specific, actionable tasks
- Be precise about file names and instructions
- Include relevant context like error messages or requirements
- Choose appropriate actions: create_file, modify_file, explain_code, run_tests, debug_code, refactor_code
- Consider what tools Claude might need (Read, Write, Bash, etc.)
- When creating files, use relative paths within the project structure
- For multi-file projects, organize code logically with proper folder structure
"""
    
    try:
        model = config.get("openai_model", "gpt-4-0613")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request}
            ],
            functions=[get_function_schema()],
            function_call={"name": "invoke_claude_task"}
        )
        
        # Track token usage
        if token_tracker and hasattr(response, 'usage'):
            usage = TokenUsage.from_openai_response(response, model, session_id, "task_generation")
            token_tracker.track_usage(usage)
            print(f"🔢 OpenAI Usage: {usage.input_tokens} in + {usage.output_tokens} out = {usage.total_tokens} tokens (${usage.cost_usd:.4f})")
        
        if response.choices[0].message.function_call:
            task_args = json.loads(response.choices[0].message.function_call.arguments)
            
            # If we have a project folder, adjust the filename to be within that folder
            if project_folder and task_args.get("filename"):
                filename = task_args["filename"]
                # Don't modify if it's already a relative path within projects/
                if not filename.startswith("projects/"):
                    task_args["filename"] = os.path.join(project_folder, filename)
            
            print(f"🎯 GPT-4 generated task: {task_args['action']} - {task_args['instruction'][:60]}...")
            return task_args
        else:
            print("❌ GPT-4 did not generate a valid task")
            return None
            
    except Exception as e:
        print(f"❌ Error calling GPT-4: {e}")
        return None

def create_project_readme(project_folder: str, project_description: str) -> None:
    """Create a README file for the project with usage instructions."""
    readme_file = os.path.join(project_folder, "README.md")
    
    if not os.path.exists(readme_file):
        project_name = os.path.basename(project_folder).replace('_', ' ').title()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        readme_content = f"""# {project_name}

*Generated by MeistroCraft on {timestamp}*

## Description

{project_description}

## Project Structure

This project was created using an AI coding agent and organized for easy development and maintenance.

## Files

- Check the PROJECT_SUMMARY.md file for a complete log of all AI-generated tasks and changes
- Each file was created with specific instructions and validated for quality

## Usage Instructions

1. **Setup**: Ensure you have the necessary dependencies installed
2. **Configuration**: Update any configuration files as needed
3. **Running**: Follow the specific instructions for your project type below

### Getting Started

*This section will be populated based on the project type and files created*

## Development

This project structure supports:
- ✅ Organized file structure
- ✅ Automated documentation
- ✅ Task tracking and history
- ✅ AI-assisted development

## Support

If you need modifications or have questions about this AI-generated code:
- Check the PROJECT_SUMMARY.md for implementation details
- Review individual file comments for specific functionality
- Consider using MeistroCraft for further development

---

*Generated with MeistroCraft - GPT-4 Orchestrator with Claude Code CLI*
"""
        
        with open(readme_file, 'w') as f:
            f.write(readme_content)

def create_project_summary(project_folder: str, task: Dict[str, Any], result: Dict[str, Any]) -> None:
    """Create or update a project summary file for tracking all tasks and changes."""
    summary_file = os.path.join(project_folder, "PROJECT_SUMMARY.md")
    
    # Create summary entry
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"""
## Task: {task['action']} - {timestamp}

**File**: {task.get('filename', 'N/A')}
**Instruction**: {task['instruction']}
**Status**: {'✅ Success' if result.get('success') else '❌ Failed'}

**Claude's Response**:
{result.get('result', 'No response')[:500]}{'...' if len(result.get('result', '')) > 500 else ''}

---
"""
    
    # Read existing content or create header
    if os.path.exists(summary_file):
        with open(summary_file, 'r') as f:
            existing_content = f.read()
    else:
        project_name = os.path.basename(project_folder)
        existing_content = f"""# Project Summary: {project_name}

*Auto-generated log of all MeistroCraft tasks*

**Created**: {timestamp}
**Location**: {project_folder}

---
"""
    
    # Append new entry at the top (after header)
    lines = existing_content.split('\n')
    header_end = 0
    for i, line in enumerate(lines):
        if line.startswith('---') and i > 5:  # Find first separator after header
            header_end = i + 1
            break
    
    if header_end == 0:
        # No separator found, add after header
        header_end = len(lines)
    
    # Insert new entry
    new_content = '\n'.join(lines[:header_end]) + entry + '\n'.join(lines[header_end:])
    
    # Write updated summary
    with open(summary_file, 'w') as f:
        f.write(new_content)

def create_and_run_tests(project_folder: str, task: Dict[str, Any]) -> Dict[str, Any]:
    """Create and run basic tests for the generated code."""
    test_result = {
        "tests_created": False,
        "tests_passed": False,
        "test_output": ""
    }
    
    # Only create tests for Python files for now
    if task.get("filename") and task["filename"].endswith('.py'):
        try:
            # Create tests directory
            test_dir = os.path.join(project_folder, "tests")
            os.makedirs(test_dir, exist_ok=True)
            
            # Create basic test file
            test_file = os.path.join(test_dir, "test_basic.py")
            test_content = f"""import unittest
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestBasic(unittest.TestCase):
    def test_file_exists(self):
        \"\"\"Test that generated files exist.\"\"\"
        filename = \"{task.get('filename', '')}\"
        if filename:
            self.assertTrue(os.path.exists(filename), f\"File {{filename}} should exist\")
    
    def test_python_syntax(self):
        \"\"\"Test Python syntax is valid.\"\"\"
        filename = \"{task.get('filename', '')}\"
        if filename and filename.endswith('.py') and os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    compile(f.read(), filename, 'exec')
            except SyntaxError as e:
                self.fail(f\"Syntax error in {{filename}}: {{e}}\")

if __name__ == '__main__':
    unittest.main()
"""
            
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            test_result["tests_created"] = True
            
            # Run the tests
            result = subprocess.run([sys.executable, "-m", "unittest", "tests.test_basic"], 
                                  capture_output=True, text=True, cwd=project_folder, timeout=30)
            test_result["test_output"] = result.stdout + result.stderr
            test_result["tests_passed"] = result.returncode == 0
            
        except Exception as e:
            test_result["test_output"] = f"Test creation/execution failed: {e}"
    
    return test_result

def validate_code_output(result: Dict[str, Any], task: Dict[str, Any], project_folder: Optional[str] = None) -> Dict[str, Any]:
    """Validate Claude's code output and run basic checks."""
    validation_result = {
        "passed": True,
        "issues": [],
        "suggestions": []
    }
    
    # Check if file was created when expected
    if task["action"] == "create_file" and task.get("filename"):
        if not os.path.exists(task["filename"]):
            validation_result["issues"].append(f"Expected file {task['filename']} was not created")
            validation_result["passed"] = False
    
    # Basic syntax check for Python files
    if task.get("filename", "").endswith(".py") and os.path.exists(task["filename"]):
        try:
            with open(task["filename"], 'r') as f:
                code = f.read()
            compile(code, task["filename"], 'exec')
            validation_result["suggestions"].append("Python syntax is valid")
        except SyntaxError as e:
            validation_result["issues"].append(f"Python syntax error: {e}")
            validation_result["passed"] = False
    
    return validation_result

def create_feedback_task(original_task: Dict[str, Any], validation: Dict[str, Any], claude_result: str) -> Dict[str, Any]:
    """Create a feedback task to fix issues found in validation."""
    issues_text = "; ".join(validation["issues"])
    
    feedback_task = {
        "action": "modify_file" if original_task.get("filename") else "debug_code",
        "filename": original_task.get("filename"),
        "instruction": f"Fix the following issues in the previous implementation: {issues_text}",
        "context": f"Previous Claude output: {claude_result}\n\nOriginal task: {original_task['instruction']}",
        "tools": original_task.get("tools", ["Read", "Write"])
    }
    
    return feedback_task

def interactive_mode(config: Dict[str, Any], session_id: Optional[str] = None, token_tracker: Optional[TokenTracker] = None, persistent_memory: Optional[PersistentMemory] = None, session_manager: Optional[SessionManager] = None):
    """Run in interactive mode with GPT-4 task generation."""
    if session_manager is None:
        session_manager = SessionManager()
    project_folder = None
    
    # Handle session creation or continuation
    if session_id:
        # Try to find session by short ID if not found directly
        session_data = session_manager.load_session(session_id)
        if not session_data and len(session_id) == 8:
            full_session_id = session_manager.find_session_by_short_id(session_id)
            if full_session_id:
                session_id = full_session_id
                session_data = session_manager.load_session(session_id)
        
        if session_data:
            print(f"🔄 Continuing session: {session_data['name']} (ID: {session_id[:8]}...)")
            print(f"📊 Previous tasks: {len(session_data.get('task_history', []))}")
            
            # Load persistent memory context for this session
            if persistent_memory:
                memory_context = persistent_memory.get_session_context(session_id)
                if memory_context:
                    print(f"🧠 Loaded persistent memory context")
        else:
            print(f"❌ Session {session_id} not found. Creating new session.")
            session_id = session_manager.create_session()
    else:
        session_id = session_manager.create_session()
        print(f"🆕 Created new session: {session_id[:8]}...")
    
    print("🤖 Interactive Mode - Enter requests for GPT-4 to plan and Claude to execute")
    print("Commands: 'quit' to exit, 'sessions' to list all sessions, 'context' to view session context\n")
    
    while True:
        user_input = input("👤 Your request: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            break
        
        if not user_input:
            continue
        
        print(f"\n🔄 Processing request with GPT-4...")
        
        # Handle special commands
        if user_input.lower() == 'sessions':
            sessions = session_manager.list_sessions()
            print("\n📋 Available Sessions:")
            for session in sessions[:10]:  # Show last 10 sessions
                print(f"  {session['short_id']}: {session['name']} ({session['task_count']} tasks, last used: {session['last_used'][:19]})")
            continue
        
        if user_input.lower() == 'context':
            context = session_manager.get_session_context(session_id)
            if context:
                print(f"\n📝 Session Context:{context}")
            else:
                print("\n📝 No session context available yet.")
            continue
        
        # Set up project folder for first task if not already set
        if not project_folder:
            # Check if session has a workspace
            session_data = session_manager.load_session(session_id)
            workspace_path = session_data.get('workspace_path') if session_data else None
            
            if workspace_path:
                project_folder = workspace_path
                print(f"📁 Using existing workspace: {project_folder}")
            else:
                # Create workspace for this session with task description
                if session_manager.workspace_manager:
                    workspace_path = session_manager.workspace_manager.create_session_workspace(session_id, user_input[:100])
                    if workspace_path:
                        project_folder = workspace_path
                        print(f"🏗️  Created isolated workspace: {project_folder}")
                        # Update session data with workspace info
                        if session_data:
                            workspace = session_manager.workspace_manager.git_manager.get_workspace_by_session(session_id)
                            if workspace:
                                session_data["workspace_id"] = workspace.workspace_id
                                session_data["workspace_path"] = workspace_path
                                session_manager.save_session(session_data)
                    else:
                        # Fallback to regular project folder
                        project_folder = setup_project_folder(user_input, config)
                        print(f"📁 Created project folder: {project_folder}")
                else:
                    # No workspace manager, use regular project folder
                    project_folder = setup_project_folder(user_input, config)
                    print(f"📁 Created project folder: {project_folder}")
        
        # Generate task with GPT-4
        task = generate_task_with_gpt4(user_input, config, project_folder, token_tracker, session_id)
        if not task:
            continue
        
        # Execute with Claude
        print(f"\n🎯 Executing with Claude: {task['action']} (Session: {session_id[:8]}...)")
        # For the first task in interactive mode, don't use Claude session
        # Claude will create a new session and return the session_id
        session_data = session_manager.load_session(session_id)
        existing_tasks = len(session_data.get('task_history', [])) if session_data else 0
        
        if existing_tasks == 0:
            # First task - let Claude create a new session
            result = run_claude_task(task, config, None, None, project_folder, token_tracker)
            # Save to our session manager and create project summary
            if result.get('success'):
                session_manager.add_task_to_session(session_id, task, result)
                create_project_summary(project_folder, task, result)
                
                # Create README for first task
                create_project_readme(project_folder, task['instruction'])
                
                # Create and run tests
                test_result = create_and_run_tests(project_folder, task)
                if test_result['tests_created']:
                    print(f"🧪 Tests created and run: {'✅ Passed' if test_result['tests_passed'] else '❌ Failed'}")
                    if test_result['test_output']:
                        print(f"📋 Test output: {test_result['test_output'][:200]}{'...' if len(test_result['test_output']) > 200 else ''}")
        else:
            # Subsequent tasks - try to resume Claude session from previous task
            claude_session_id = None
            if session_data and session_data.get('task_history'):
                last_result = session_data['task_history'][-1].get('result', {})
                claude_session_id = last_result.get('session_id')
            result = run_claude_task(task, config, claude_session_id, None, project_folder, token_tracker)
            # Save to our session manager and update project summary
            if result.get('success'):
                session_manager.add_task_to_session(session_id, task, result)
                create_project_summary(project_folder, task, result)
                
                # Create and run tests for subsequent tasks too
                test_result = create_and_run_tests(project_folder, task)
                if test_result['tests_created']:
                    print(f"🧪 Tests updated and run: {'✅ Passed' if test_result['tests_passed'] else '❌ Failed'}")
                    if test_result['test_output']:
                        print(f"📋 Test output: {test_result['test_output'][:200]}{'...' if len(test_result['test_output']) > 200 else ''}")
        
        if result["success"]:
            print(f"\n✅ Claude completed the task!")
            print(f"📝 Response: {result['result'][:200]}{'...' if len(result['result']) > 200 else ''}")
            
            # Store conversation and code context in persistent memory
            if persistent_memory:
                try:
                    # Store conversation memory
                    conversation_data = {
                        "messages": [
                            {"role": "user", "content": user_input},
                            {"role": "assistant", "content": result['result'][:1000]}  # Limit size
                        ],
                        "summary": f"Task: {task['action']} - {task['instruction'][:100]}",
                        "topics": [task['action']],
                        "decisions": [f"Created/modified: {task.get('filename', 'code')}"]
                    }
                    persistent_memory.store_conversation_memory(conversation_data, session_id)
                    
                    # Store code context if applicable
                    if task.get('filename'):
                        code_data = {
                            "files_created": [task['filename']] if task['action'] == 'create_file' else [],
                            "files_modified": [task['filename']] if task['action'] == 'modify_file' else [],
                            "technologies": [task.get('language', 'unknown')],
                            "patterns": [task['action']],
                            "structure": {"main_file": task['filename']}
                        }
                        persistent_memory.store_code_context(code_data, session_id)
                    
                    print(f"💾 Stored session memory ({persistent_memory.get_memory_summary()})")
                except Exception as e:
                    print(f"⚠️  Failed to store memory: {e}")
            
            # Validate the output
            validation = validate_code_output(result, task)
            
            if not validation["passed"]:
                print(f"\n⚠️  Validation found issues: {', '.join(validation['issues'])}")
                print(f"🔧 Attempting to fix...")
                
                # Create feedback task
                feedback_task = create_feedback_task(task, validation, result['result'])
                # Get Claude session ID for feedback
                claude_session_id = result.get('session_id')
                feedback_result = run_claude_task(feedback_task, config, claude_session_id, None, project_folder, token_tracker)
                if feedback_result.get('success'):
                    session_manager.add_task_to_session(session_id, feedback_task, feedback_result)
                    create_project_summary(project_folder, feedback_task, feedback_result)
                
                if feedback_result["success"]:
                    print(f"✅ Issues fixed!")
                    print(f"📝 Fixed result: {feedback_result['result'][:200]}{'...' if len(feedback_result['result']) > 200 else ''}")
                else:
                    print(f"❌ Failed to fix issues: {feedback_result['error']}")
            else:
                if validation["suggestions"]:
                    print(f"💡 Validation notes: {', '.join(validation['suggestions'])}")
        else:
            print(f"\n❌ Claude failed: {result['error']}")
        
        # Session history is now automatically managed by SessionManager
        pass
        
        print("\n" + "="*50)

def main():
    """Main orchestrator loop."""
    print("MeistroCraft - GPT-4 Orchestrator with Claude Code CLI")
    print("=" * 60)
    
    # Load configuration
    config = load_config()
    setup_environment(config)
    
    # Initialize token tracker
    token_tracker = TokenTracker()
    
    # Load token limits from config if available
    if config.get("token_limits"):
        limits = UsageLimits(**config["token_limits"])
        token_tracker.save_limits(limits)
    
    # Initialize persistent memory
    memory_limit_mb = config.get("memory_limit_mb", 512.0)
    persistent_memory = PersistentMemory(max_size_mb=memory_limit_mb)
    
    # Initialize workspace manager
    workspace_manager = WorkspaceManager()
    
    # Initialize GitHub client
    github_client = create_github_client(config)
    
    # Initialize GitHub workflow integration
    workflow_integration = create_workflow_integration(github_client) if github_client else None
    
    # Initialize Phase 3: CI/CD Pipeline Integration
    cicd_manager = create_cicd_integration(github_client, config) if github_client else None
    build_monitor = BuildStatusMonitor(cicd_manager, config) if cicd_manager else None
    deployment_automation = create_deployment_automation(cicd_manager, build_monitor, config) if cicd_manager and build_monitor else None
    
    # Show memory status
    memory_summary = persistent_memory.get_memory_summary()
    print(f"  {memory_summary}")
    print(f"  🏗️  Workspace isolation: enabled")
    if github_client:
        print(f"  🐙 GitHub integration: enabled ({github_client.get_authenticated_user()})")
        if workflow_integration:
            print(f"  🔄 GitHub workflows: enabled (PR/Issue automation)")
        else:
            print(f"  🔄 GitHub workflows: basic mode")
        
        # Phase 3 CI/CD status
        if cicd_manager:
            print(f"  🚀 CI/CD integration: enabled (GitHub Actions)")
            if build_monitor:
                print(f"  📊 Build monitoring: enabled (Status tracking & analytics)")
            if deployment_automation:
                print(f"  🚀 Deployment automation: enabled (Multi-environment)")
        else:
            print(f"  🚀 CI/CD integration: disabled")
    else:
        print(f"  🐙 GitHub integration: disabled")
        print(f"  🚀 CI/CD integration: disabled (requires GitHub)")
    
    print(f"Configuration loaded:")
    print(f"  Claude model: {config.get('claude_model', 'default')}")
    print(f"  OpenAI model: {config.get('openai_model', 'gpt-4-0613')}")
    print(f"  Permission mode: {config.get('permission_mode', 'acceptEdits')}")
    print(f"  Allowed tools: {', '.join(config.get('allowed_tools', ['Read', 'Write']))}")
    print()
    
    # Check if we can use GPT-4 integration
    has_openai = OpenAI and config.get("openai_api_key") and config["openai_api_key"] != "<YOUR_OPENAI_API_KEY>"
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        if has_openai:
            # Check for session ID parameter
            session_id = None
            if len(sys.argv) > 2 and sys.argv[2].startswith("--session="):
                session_id = sys.argv[2].split("=")[1]
            
            # Try to use the new split terminal UI
            try:
                from interactive_ui import run_interactive_ui
                session_manager = SessionManager(workspace_manager=workspace_manager)
                run_interactive_ui(config, session_manager, token_tracker, session_id, persistent_memory)
            except ImportError:
                print("⚠️  Rich UI not available. Install with: pip install rich")
                print("Falling back to basic interactive mode...")
                session_manager = SessionManager(workspace_manager=workspace_manager)
                interactive_mode(config, session_id, token_tracker, persistent_memory, session_manager)
            except Exception as e:
                print(f"⚠️  UI error: {e}")
                print("Falling back to basic interactive mode...")
                session_manager = SessionManager(workspace_manager=workspace_manager)
                interactive_mode(config, session_id, token_tracker, persistent_memory, session_manager)
        else:
            print("❌ Interactive mode requires OpenAI API key")
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == "--sessions":
        # List all sessions
        session_manager = SessionManager(workspace_manager=workspace_manager)
        sessions = session_manager.list_sessions()
        print("📋 Available Sessions:")
        if sessions:
            for session in sessions:
                print(f"  {session['short_id']}: {session['name']}")
                print(f"    Created: {session['created_at'][:19]}, Last used: {session['last_used'][:19]}")
                print(f"    Tasks: {session['task_count']}\n")
        else:
            print("  No sessions found.")
    elif len(sys.argv) > 1 and sys.argv[1] == "--continue":
        # Continue a specific session
        if len(sys.argv) > 2:
            session_id = sys.argv[2]
            if has_openai:
                # Try to use the new split terminal UI
                try:
                    from interactive_ui import run_interactive_ui
                    session_manager = SessionManager(workspace_manager=workspace_manager)
                    run_interactive_ui(config, session_manager, token_tracker, session_id, persistent_memory)
                except ImportError:
                    print("⚠️  Rich UI not available. Install with: pip install rich")
                    print("Falling back to basic interactive mode...")
                    session_manager = SessionManager(workspace_manager=workspace_manager)
                    interactive_mode(config, session_id, token_tracker, persistent_memory, session_manager)
                except Exception as e:
                    print(f"⚠️  UI error: {e}")
                    print("Falling back to basic interactive mode...")
                    session_manager = SessionManager(workspace_manager=workspace_manager)
                    interactive_mode(config, session_id, token_tracker, persistent_memory, session_manager)
            else:
                print("❌ Interactive mode requires OpenAI API key")
                sys.exit(1)
        else:
            print("❌ --continue requires a session ID")
            sys.exit(1)
    elif len(sys.argv) > 1 and sys.argv[1] == "--token-usage":
        # Show token usage statistics
        if len(sys.argv) > 2:
            days = int(sys.argv[2])
        else:
            days = 7
        
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=days)
        
        # OpenAI usage
        openai_summary = token_tracker.get_usage_summary(start_date, None, "openai")
        print(f"\n📊 OpenAI Usage (Last {days} days):")
        print(f"  Requests: {openai_summary.total_requests}")
        print(f"  Tokens: {openai_summary.total_input_tokens:,} in + {openai_summary.total_output_tokens:,} out = {openai_summary.total_tokens:,} total")
        print(f"  Cost: ${openai_summary.total_cost_usd:.4f}")
        if openai_summary.models_used:
            print(f"  Models: {', '.join(openai_summary.models_used)}")
        
        # Anthropic usage
        anthropic_summary = token_tracker.get_usage_summary(start_date, None, "anthropic")
        print(f"\n🤖 Anthropic Usage (Last {days} days):")
        print(f"  Requests: {anthropic_summary.total_requests}")
        print(f"  Tokens: {anthropic_summary.total_input_tokens:,} in + {anthropic_summary.total_output_tokens:,} out = {anthropic_summary.total_tokens:,} total")
        print(f"  Cost: ${anthropic_summary.total_cost_usd:.4f}")
        if anthropic_summary.models_used:
            print(f"  Models: {', '.join(anthropic_summary.models_used)}")
        
        # Combined totals
        total_tokens = openai_summary.total_tokens + anthropic_summary.total_tokens
        total_cost = openai_summary.total_cost_usd + anthropic_summary.total_cost_usd
        print(f"\n💰 Total Usage (Last {days} days):")
        print(f"  Total Tokens: {total_tokens:,}")
        print(f"  Total Cost: ${total_cost:.4f}")
        
        # Show top sessions
        print(f"\n🔝 Top Sessions by Usage:")
        top_sessions = token_tracker.get_top_sessions_by_usage(5)
        for i, (session_id, tokens, cost) in enumerate(top_sessions, 1):
            print(f"  {i}. {session_id[:8]}... - {tokens:,} tokens (${cost:.4f})")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--set-token-limits":
        # Set token usage limits
        print("🔧 Token Usage Limits Configuration")
        try:
            daily_token_limit = input("Daily token limit (enter for no limit): ").strip()
            monthly_token_limit = input("Monthly token limit (enter for no limit): ").strip()
            daily_cost_limit = input("Daily cost limit USD (enter for no limit): ").strip()
            monthly_cost_limit = input("Monthly cost limit USD (enter for no limit): ").strip()
            
            limits = UsageLimits(
                daily_token_limit=int(daily_token_limit) if daily_token_limit else None,
                monthly_token_limit=int(monthly_token_limit) if monthly_token_limit else None,
                daily_cost_limit_usd=float(daily_cost_limit) if daily_cost_limit else None,
                monthly_cost_limit_usd=float(monthly_cost_limit) if monthly_cost_limit else None
            )
            
            token_tracker.save_limits(limits)
            print("✅ Token limits saved successfully!")
            
        except ValueError as e:
            print(f"❌ Invalid input: {e}")
        except KeyboardInterrupt:
            print("\n❌ Configuration cancelled")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--export-usage":
        # Export usage report
        if len(sys.argv) > 2:
            days = int(sys.argv[2])
        else:
            days = 30
        
        start_date = datetime.now() - timedelta(days=days)
        output_file = f"token_usage_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        token_tracker.export_usage_report(start_date, datetime.now(), output_file)
        print(f"📄 Usage report exported to: {output_file}")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--memory-status":
        # Show detailed memory status
        stats = persistent_memory.get_stats()
        print(f"\n💾 Persistent Memory Status:")
        print(f"  Total Entries: {stats.total_entries:,}")
        print(f"  Total Size: {stats.total_size_mb:.2f}MB / {stats.warning_threshold_mb:.0f}MB")
        print(f"  Usage: {(stats.total_size_mb/stats.warning_threshold_mb)*100:.1f}%")
        
        if stats.by_type:
            print(f"\n📊 By Type:")
            for mem_type, count in stats.by_type.items():
                print(f"    {mem_type}: {count} entries")
        
        if stats.by_priority:
            print(f"\n🏷️  By Priority:")
            for priority, count in stats.by_priority.items():
                print(f"    {priority}: {count} entries")
        
        if stats.is_over_limit:
            print(f"\n🚨 WARNING: Memory usage exceeds {stats.warning_threshold_mb}MB limit!")
        elif stats.is_near_limit:
            print(f"\n⚠️  Warning: Memory usage approaching limit")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--memory-cleanup":
        # Clean up memory
        print("🧹 Starting memory cleanup...")
        deleted_count = persistent_memory._cleanup_memory()
        if deleted_count > 0:
            new_stats = persistent_memory.get_stats()
            print(f"✅ Cleaned up {deleted_count} entries")
            print(f"   New usage: {new_stats.total_size_mb:.2f}MB ({new_stats.total_entries} entries)")
        else:
            print("✅ No cleanup needed - memory usage is within limits")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--memory-export":
        # Export memory report
        output_file = f"memory_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        persistent_memory.export_memory_report(output_file)
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--clear-session-memory":
        # Clear memory for a specific session
        if len(sys.argv) > 2:
            session_id = sys.argv[2]
            deleted_count = persistent_memory.clear_session_memories(session_id)
            print(f"🗑️  Cleared {deleted_count} memory entries for session {session_id[:8]}...")
        else:
            print("❌ --clear-session-memory requires a session ID")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--cleanup-sessions":
        # Clean up old sessions
        session_manager = SessionManager(workspace_manager=workspace_manager)
        
        # Parse optional parameters
        days_old = 30
        max_sessions = 50
        
        if len(sys.argv) > 2:
            try:
                days_old = int(sys.argv[2])
            except ValueError:
                print("❌ Days parameter must be a number")
                sys.exit(1)
        
        if len(sys.argv) > 3:
            try:
                max_sessions = int(sys.argv[3])
            except ValueError:
                print("❌ Max sessions parameter must be a number")
                sys.exit(1)
        
        print(f"🧹 Cleaning up sessions older than {days_old} days and keeping max {max_sessions} sessions...")
        stats = session_manager.cleanup_old_sessions(days_old, max_sessions)
        
        print(f"✅ Cleanup completed:")
        print(f"   Sessions deleted by age: {stats['deleted_by_age']}")
        print(f"   Sessions deleted by count limit: {stats['deleted_by_count']}")
        print(f"   Corrupted files removed: {stats['corrupted_deleted']}")
        print(f"   Sessions remaining: {stats['total_remaining']}")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--repair-sessions":
        # Repair corrupted session files
        session_manager = SessionManager(workspace_manager=workspace_manager)
        
        print("🔧 Repairing session files...")
        stats = session_manager.repair_sessions()
        
        print(f"✅ Session repair completed:")
        print(f"   Sessions repaired: {stats['repaired']}")
        print(f"   Unrepairable sessions deleted: {stats['deleted']}")
        print(f"   Sessions unchanged: {stats['unchanged']}")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--delete-session":
        # Delete a specific session
        if len(sys.argv) > 2:
            session_id = sys.argv[2]
            session_manager = SessionManager(workspace_manager=workspace_manager)
            
            # Try to find session by short ID if not found directly
            session_data = session_manager.load_session(session_id)
            if not session_data and len(session_id) == 8:
                full_session_id = session_manager.find_session_by_short_id(session_id)
                if full_session_id:
                    session_id = full_session_id
            
            success = session_manager.delete_session(session_id)
            if success:
                print(f"✅ Session {session_id[:8]} deleted successfully")
            else:
                print(f"❌ Failed to delete session {session_id[:8]} (may not exist)")
        else:
            print("❌ --delete-session requires a session ID")
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--request":
        if has_openai and len(sys.argv) > 2:
            user_request = " ".join(sys.argv[2:])
            print(f"🎯 Processing request: {user_request}")
            
            # Single requests get their own project folder
            project_folder = setup_project_folder(user_request, config)
            print(f"📁 Created project folder: {project_folder}")
            
            session_manager = SessionManager()
            session_id = session_manager.create_session(f"Single request: {user_request[:30]}...")
            
            task = generate_task_with_gpt4(user_request, config, project_folder, token_tracker, session_id)
            if task and validate_task(task):
                # Don't pass session_id to Claude for single requests
                result = run_claude_task(task, config, None, None, project_folder, token_tracker)
                # But save to our session manager and create project summary
                if result.get("success"):
                    session_manager.add_task_to_session(session_id, task, result)
                    create_project_summary(project_folder, task, result)
                    create_project_readme(project_folder, user_request)
                    
                    # Create and run tests
                    test_result = create_and_run_tests(project_folder, task)
                    if test_result['tests_created']:
                        print(f"🧪 Tests created and run: {'✅ Passed' if test_result['tests_passed'] else '❌ Failed'}")
                        if test_result['test_output']:
                            print(f"📋 Test output: {test_result['test_output'][:100]}...")
                if result["success"]:
                    print(f"\n✅ Task completed successfully!")
                    print(f"📝 Claude's response:\n{result['result']}")
                    
                    # Validate output
                    validation = validate_code_output(result, task)
                    if not validation["passed"]:
                        print(f"\n⚠️  Validation issues: {', '.join(validation['issues'])}")
                else:
                    print(f"\n❌ Task failed: {result['error']}")
        else:
            print("❌ --request mode requires OpenAI API key and a request string")
            sys.exit(1)
    
    # GitHub integration commands
    elif len(sys.argv) > 1 and sys.argv[1] == "--github":
        if not github_client:
            print("❌ GitHub integration not available. Please check your configuration.")
            sys.exit(1)
        
        if len(sys.argv) < 3:
            print("❌ --github requires a subcommand")
            print("Available commands:")
            print("  --github test                    # Test GitHub connection")
            print("  --github status                  # Show GitHub API status")
            print("  --github repos                   # List repositories")
            print("  --github create <name>           # Create new repository")
            print("  --github fork <owner/repo>       # Fork repository")
            print("  --github prs <owner/repo>        # List pull requests")
            print("  --github issues <owner/repo>     # List issues")
            print("  --github workflow <owner/repo>   # Show workflow status")
            print("  Phase 3 - CI/CD Commands:")
            print("  --github builds <owner/repo>     # Monitor build status")
            print("  --github deploy <owner/repo> <env> # Deploy to environment")
            print("  --github rollback <owner/repo> <env> # Rollback deployment")
            print("  --github health <owner/repo>     # Check build health")
            print("  --github actions <owner/repo>    # List workflow runs")
            sys.exit(1)
        
        subcommand = sys.argv[2]
        
        if subcommand == "test":
            print("🔗 Testing GitHub connection...")
            test_result = github_client.test_connection()
            if test_result["success"]:
                print(f"✅ {test_result['message']}")
                if test_result.get('using_pygithub'):
                    print("   Using PyGitHub library (full functionality)")
                else:
                    print("   Using fallback mode (basic functionality)")
            else:
                print(f"❌ GitHub connection failed: {test_result['error']}")
        
        elif subcommand == "status":
            print("🐙 GitHub Status:")
            rate_limit = github_client.get_rate_limit_status()
            if "error" not in rate_limit:
                if "core" in rate_limit:
                    core = rate_limit["core"]
                    print(f"  API Rate Limit: {core['remaining']}/{core['limit']} remaining")
                    print(f"  Reset time: {core['reset']}")
                print(f"  User: {github_client.get_authenticated_user()}")
            else:
                print(f"  Error: {rate_limit['error']}")
        
        elif subcommand == "repos":
            print("📋 Listing repositories...")
            try:
                repos = github_client.list_repositories()
                if repos:
                    print(f"Found {len(repos)} repositories:")
                    for repo in repos[:10]:  # Show first 10
                        if hasattr(repo, 'full_name'):  # PyGitHub object
                            name = repo.full_name
                            desc = repo.description or "No description"
                            private = "🔒" if repo.private else "🌐"
                        else:  # Dict from fallback mode
                            name = repo.get('full_name', 'Unknown')
                            desc = repo.get('description') or "No description"
                            private = "🔒" if repo.get('private') else "🌐"
                        print(f"  {private} {name} - {desc[:50]}{'...' if len(desc) > 50 else ''}")
                    if len(repos) > 10:
                        print(f"  ... and {len(repos) - 10} more")
                else:
                    print("  No repositories found.")
            except GitHubClientError as e:
                print(f"❌ Failed to list repositories: {e}")
        
        elif subcommand == "create":
            if len(sys.argv) < 4:
                print("❌ --github create requires a repository name")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            description = " ".join(sys.argv[4:]) if len(sys.argv) > 4 else f"Repository created by MeistroCraft"
            
            print(f"🔨 Creating repository '{repo_name}'...")
            try:
                repo = github_client.create_repository(
                    name=repo_name,
                    description=description,
                    private=True,  # Default to private for safety
                    auto_init=True
                )
                
                if hasattr(repo, 'html_url'):  # PyGitHub object
                    print(f"✅ Repository created: {repo.html_url}")
                    print(f"   Clone URL: {repo.clone_url}")
                else:  # Dict from fallback mode
                    print(f"✅ Repository created: {repo.get('html_url')}")
                    print(f"   Clone URL: {repo.get('clone_url')}")
                    
            except GitHubClientError as e:
                print(f"❌ Failed to create repository: {e}")
        
        elif subcommand == "fork":
            if len(sys.argv) < 4:
                print("❌ --github fork requires a repository name (owner/repo)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            if '/' not in repo_name:
                print("❌ Repository name must be in format 'owner/repo'")
                sys.exit(1)
            
            print(f"🍴 Forking repository '{repo_name}'...")
            try:
                forked_repo = github_client.fork_repository(repo_name)
                
                if hasattr(forked_repo, 'html_url'):  # PyGitHub object
                    print(f"✅ Repository forked: {forked_repo.html_url}")
                    print(f"   Clone URL: {forked_repo.clone_url}")
                else:  # Dict from fallback mode
                    print(f"✅ Repository forked: {forked_repo.get('html_url')}")
                    print(f"   Clone URL: {forked_repo.get('clone_url')}")
                    
            except GitHubClientError as e:
                print(f"❌ Failed to fork repository: {e}")
        
        elif subcommand == "prs":
            if len(sys.argv) < 4:
                print("❌ --github prs requires a repository name (owner/repo)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            state = sys.argv[4] if len(sys.argv) > 4 else "open"
            
            if not workflow_integration:
                print("❌ GitHub workflow integration not available")
                sys.exit(1)
            
            print(f"📋 Listing {state} pull requests for {repo_name}...")
            try:
                prs = workflow_integration.pr_manager.list_repository_prs(repo_name, state)
                if prs:
                    print(f"Found {len(prs)} {state} pull request(s):")
                    for pr in prs[:10]:  # Show first 10
                        branch_info = f" ({pr.get('branch')} → {pr.get('base')})" if pr.get('branch') else ""
                        print(f"  #{pr.get('number')} {pr.get('title')}{branch_info}")
                        print(f"    👤 {pr.get('user')} • 🔗 {pr.get('html_url')}")
                    if len(prs) > 10:
                        print(f"  ... and {len(prs) - 10} more")
                else:
                    print(f"  No {state} pull requests found.")
            except GitHubWorkflowError as e:
                print(f"❌ Failed to list pull requests: {e}")
        
        elif subcommand == "issues":
            if len(sys.argv) < 4:
                print("❌ --github issues requires a repository name (owner/repo)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            state = sys.argv[4] if len(sys.argv) > 4 else "open"
            
            if not workflow_integration:
                print("❌ GitHub workflow integration not available")
                sys.exit(1)
            
            print(f"🎫 Listing {state} issues for {repo_name}...")
            try:
                issues = workflow_integration.issue_manager.list_repository_issues(repo_name, state)
                if issues:
                    print(f"Found {len(issues)} {state} issue(s):")
                    for issue in issues[:10]:  # Show first 10
                        labels_str = ", ".join(issue.get('labels', [])) if issue.get('labels') else "no labels"
                        print(f"  #{issue.get('number')} {issue.get('title')}")
                        print(f"    🏷️  {labels_str} • 👤 {issue.get('user')} • 🔗 {issue.get('html_url')}")
                    if len(issues) > 10:
                        print(f"  ... and {len(issues) - 10} more")
                else:
                    print(f"  No {state} issues found.")
            except GitHubWorkflowError as e:
                print(f"❌ Failed to list issues: {e}")
        
        elif subcommand == "workflow":
            if len(sys.argv) < 4:
                print("❌ --github workflow requires a repository name (owner/repo)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            
            if not workflow_integration:
                print("❌ GitHub workflow integration not available")
                sys.exit(1)
            
            print(f"🔄 Getting workflow status for {repo_name}...")
            try:
                status = workflow_integration.get_repository_status(repo_name)
                
                print(f"📊 Repository Status:")
                print(f"  Open PRs: {status.get('total_open_prs', 0)}")
                print(f"  Open Issues: {status.get('total_open_issues', 0)}")
                print(f"  MeistroCraft PRs: {status.get('meistrocraft_prs', 0)}")
                print(f"  MeistroCraft Issues: {status.get('meistrocraft_issues', 0)}")
                print(f"  Workflow Health: {status.get('workflow_health', 'unknown')}")
                
                recommendations = status.get('recommendations', [])
                if recommendations:
                    print(f"\n💡 Recommendations:")
                    for rec in recommendations:
                        print(f"  • {rec}")
                else:
                    print(f"\n✅ No recommendations - workflow looks good!")
                    
            except GitHubWorkflowError as e:
                print(f"❌ Failed to get workflow status: {e}")
        
        # Phase 3 CI/CD Commands
        elif subcommand == "builds":
            if len(sys.argv) < 4:
                print("❌ --github builds requires a repository name (owner/repo)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            branch = sys.argv[4] if len(sys.argv) > 4 else None
            
            if not build_monitor:
                print("❌ Build monitoring not available (requires CI/CD integration)")
                sys.exit(1)
            
            print(f"📊 Getting build status for {repo_name}" + (f" (branch: {branch})" if branch else ""))
            try:
                status = build_monitor.get_build_status(repo_name, branch)
                
                print(f"🏗️  Build Status: {status.get('status')}")
                print(f"📈 Overall Health: {status.get('overall_health', 0):.1%}")
                
                metrics = status.get('metrics', {})
                print(f"📊 Metrics:")
                print(f"  Success Rate: {metrics.get('success_rate', 0):.1%}")
                print(f"  Total Runs: {metrics.get('total_runs', 0)}")
                print(f"  Consecutive Failures: {metrics.get('consecutive_failures', 0)}")
                
                recommendations = status.get('recommendations', [])
                if recommendations:
                    print(f"\n💡 Recommendations:")
                    for rec in recommendations[:3]:
                        print(f"  • {rec.get('title', 'Unknown')}: {rec.get('description', '')}")
                
            except Exception as e:
                print(f"❌ Failed to get build status: {e}")
        
        elif subcommand == "deploy":
            if len(sys.argv) < 5:
                print("❌ --github deploy requires repository and environment (owner/repo environment)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            environment = sys.argv[4]
            ref = sys.argv[5] if len(sys.argv) > 5 else 'main'
            
            if not deployment_automation:
                print("❌ Deployment automation not available (requires CI/CD integration)")
                sys.exit(1)
            
            print(f"🚀 Creating deployment for {repo_name} to {environment} (ref: {ref})")
            try:
                result = deployment_automation.create_deployment(
                    repo_name=repo_name,
                    environment=environment,
                    ref=ref,
                    description=f"MeistroCraft deployment to {environment}"
                )
                
                if result.get('deployment') == 'created':
                    print(f"✅ Deployment created successfully!")
                    print(f"  Deployment ID: {result.get('deployment_id')}")
                    print(f"  Environment: {environment}")
                    print(f"  Reference: {ref}")
                    print(f"  Status: {result.get('status')}")
                elif result.get('deployment') == 'blocked':
                    print(f"🚫 Deployment blocked by quality gates:")
                    for gate in result.get('failed_gates', []):
                        print(f"  ❌ {gate}")
                elif result.get('deployment') == 'pending_approval':
                    print(f"⏳ Deployment requires manual approval")
                    approval = result.get('approval_request', {})
                    if approval.get('approval_url'):
                        print(f"  Approve at: {approval['approval_url']}")
                else:
                    print(f"❌ Deployment failed: {result.get('message', 'Unknown error')}")
                
            except Exception as e:
                print(f"❌ Failed to create deployment: {e}")
        
        elif subcommand == "rollback":
            if len(sys.argv) < 5:
                print("❌ --github rollback requires repository and environment (owner/repo environment)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            environment = sys.argv[4]
            target_version = sys.argv[5] if len(sys.argv) > 5 else None
            
            if not deployment_automation:
                print("❌ Deployment automation not available (requires CI/CD integration)")
                sys.exit(1)
            
            print(f"🔄 Rolling back {repo_name} in {environment}" + (f" to {target_version}" if target_version else " to last successful deployment"))
            try:
                result = deployment_automation.rollback_deployment(
                    repo_name=repo_name,
                    environment=environment,
                    target_version=target_version
                )
                
                if result.get('rollback') == 'completed':
                    print(f"✅ Rollback completed successfully!")
                    print(f"  Target Version: {result.get('target_version')}")
                    print(f"  Deployment ID: {result.get('deployment_id')}")
                    rollback_result = result.get('result', {})
                    if rollback_result.get('monitoring') == 'completed':
                        print(f"  Final Status: {rollback_result.get('final_status')}")
                else:
                    print(f"❌ Rollback failed: {result.get('message', 'Unknown error')}")
                
            except Exception as e:
                print(f"❌ Failed to rollback deployment: {e}")
        
        elif subcommand == "health":
            if len(sys.argv) < 4:
                print("❌ --github health requires a repository name (owner/repo)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            
            if not build_monitor:
                print("❌ Build monitoring not available (requires CI/CD integration)")
                sys.exit(1)
            
            print(f"🏥 Monitoring build health for {repo_name}...")
            try:
                health = build_monitor.monitor_build_health(repo_name)
                
                if health.get('health_monitoring') == 'completed':
                    score = health.get('health_score', 0)
                    print(f"💚 Health Score: {score:.1%}")
                    
                    alerts = health.get('alerts', [])
                    if alerts:
                        print(f"🚨 Alerts ({len(alerts)}):")
                        for alert in alerts:
                            severity_emoji = "🔴" if alert['severity'] == 'critical' else "🟡" if alert['severity'] == 'high' else "🟠"
                            print(f"  {severity_emoji} {alert['type']}: {alert['message']}")
                    else:
                        print(f"✅ No alerts - build health is good!")
                    
                    action_items = health.get('action_items', [])
                    if action_items:
                        print(f"\n📋 Action Items:")
                        for item in action_items[:3]:
                            priority_emoji = "🔥" if item['priority'] == 'critical' else "⚡" if item['priority'] == 'high' else "📝"
                            print(f"  {priority_emoji} {item['action']}: {item['description']}")
                else:
                    print(f"❌ Health monitoring failed: {health.get('message', 'Unknown error')}")
                
            except Exception as e:
                print(f"❌ Failed to monitor build health: {e}")
        
        elif subcommand == "actions":
            if len(sys.argv) < 4:
                print("❌ --github actions requires a repository name (owner/repo)")
                sys.exit(1)
            
            repo_name = sys.argv[3]
            branch = sys.argv[4] if len(sys.argv) > 4 else None
            limit = int(sys.argv[5]) if len(sys.argv) > 5 else 10
            
            if not cicd_manager:
                print("❌ CI/CD integration not available")
                sys.exit(1)
            
            print(f"⚡ Listing workflow runs for {repo_name}" + (f" (branch: {branch})" if branch else ""))
            try:
                runs = cicd_manager.get_workflow_runs(
                    repo_name=repo_name,
                    branch=branch,
                    limit=limit
                )
                
                if runs:
                    print(f"Found {len(runs)} workflow run(s):")
                    for run in runs:
                        status_emoji = "✅" if run.get('conclusion') == 'success' else "❌" if run.get('conclusion') == 'failure' else "🔄"
                        print(f"  {status_emoji} #{run.get('run_number')} {run.get('name')}")
                        print(f"    📝 {run.get('head_branch')} • 🔗 {run.get('html_url')}")
                        print(f"    📅 {run.get('created_at', '')[:19]}")
                else:
                    print(f"  No workflow runs found.")
                
            except Exception as e:
                print(f"❌ Failed to list workflow runs: {e}")
        
        else:
            print(f"❌ Unknown GitHub subcommand: {subcommand}")
            print("Available commands:")
            print("  Phase 1&2: test, status, repos, create, fork, prs, issues, workflow")
            print("  Phase 3: builds, deploy, rollback, health, actions")
            sys.exit(1)
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--github-interactive":
        if not github_client:
            print("❌ GitHub integration not available. Please check your configuration.")
            sys.exit(1)
        
        print("🐙 GitHub Interactive Mode")
        print("Commands: 'repos', 'create <name>', 'fork <owner/repo>', 'status', 'quit'")
        
        while True:
            try:
                command = input("\n🐙 GitHub> ").strip()
                if not command:
                    continue
                
                if command.lower() in ['quit', 'exit', 'q']:
                    break
                
                # Parse command
                parts = command.split()
                cmd = parts[0].lower()
                
                if cmd == "status":
                    rate_limit = github_client.get_rate_limit_status()
                    if "error" not in rate_limit:
                        if "core" in rate_limit:
                            core = rate_limit["core"]
                            print(f"API Rate Limit: {core['remaining']}/{core['limit']} remaining")
                        print(f"User: {github_client.get_authenticated_user()}")
                    else:
                        print(f"Error: {rate_limit['error']}")
                
                elif cmd == "repos":
                    repos = github_client.list_repositories()
                    if repos:
                        for repo in repos[:5]:  # Show first 5 in interactive mode
                            if hasattr(repo, 'full_name'):
                                print(f"  {repo.full_name} - {repo.description or 'No description'}")
                            else:
                                print(f"  {repo.get('full_name')} - {repo.get('description') or 'No description'}")
                    else:
                        print("No repositories found.")
                
                elif cmd == "create" and len(parts) > 1:
                    repo_name = parts[1]
                    description = " ".join(parts[2:]) if len(parts) > 2 else "Created from MeistroCraft"
                    
                    try:
                        repo = github_client.create_repository(repo_name, description)
                        if hasattr(repo, 'html_url'):
                            print(f"✅ Created: {repo.html_url}")
                        else:
                            print(f"✅ Created: {repo.get('html_url')}")
                    except GitHubClientError as e:
                        print(f"❌ Error: {e}")
                
                elif cmd == "fork" and len(parts) > 1:
                    repo_name = parts[1]
                    if '/' not in repo_name:
                        print("❌ Repository name must be in format 'owner/repo'")
                        continue
                    
                    try:
                        forked_repo = github_client.fork_repository(repo_name)
                        if hasattr(forked_repo, 'html_url'):
                            print(f"✅ Forked: {forked_repo.html_url}")
                        else:
                            print(f"✅ Forked: {forked_repo.get('html_url')}")
                    except GitHubClientError as e:
                        print(f"❌ Error: {e}")
                
                else:
                    print("❌ Unknown command. Available: 'repos', 'create <name>', 'fork <owner/repo>', 'status', 'quit'")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    else:
        # Default: run example task
        print("🔧 Running example task (use --interactive or --request for GPT-4 mode)")
        task = load_example_task()
        
        if not validate_task(task):
            sys.exit(1)
        
        print(f"Executing task:")
        print(f"  Action: {task['action']}")
        print(f"  File: {task.get('filename', 'N/A')}")
        print(f"  Instruction: {task['instruction']}")
        print()
        
        # Execute the task with Claude (no session for example mode)
        result = run_claude_task(task, config, None, None, None, token_tracker)
        
        if result["success"]:
            print("✅ Task completed successfully!")
            print(f"Claude's response:\n{result['result']}")
            
            # If this was a file creation task, check if the file was created
            if task["action"] == "create_file" and task.get("filename"):
                if os.path.exists(task["filename"]):
                    print(f"✅ File {task['filename']} was created successfully!")
                else:
                    print(f"ℹ️  File {task['filename']} was not created (may be in Claude's response text)")
        else:
            print("❌ Task failed!")
            print(f"Error: {result['error']}")
    
    print(f"\n💡 Try these commands:")
    print(f"  meistrocraft --interactive                    # Interactive mode with split terminal UI")
    print(f"  meistrocraft --interactive --session=abc123   # Continue specific session")
    print(f"  meistrocraft --sessions                       # List all sessions")
    print(f"  meistrocraft --continue abc123                # Continue session abc123")
    print(f"  meistrocraft --request 'Create a calculator'  # Single request mode")
    print(f"  meistrocraft --token-usage [days]             # Show token usage statistics")
    print(f"  meistrocraft --set-token-limits               # Configure usage limits")
    print(f"  meistrocraft --export-usage [days]            # Export usage report to CSV")
    print(f"\n🐙 GitHub Integration Commands:")
    print(f"  meistrocraft --github test                    # Test GitHub connection")
    print(f"  meistrocraft --github status                  # Show GitHub API status")
    print(f"  meistrocraft --github repos                   # List your repositories")
    print(f"  meistrocraft --github create myrepo           # Create new repository")
    print(f"  meistrocraft --github fork owner/repo         # Fork a repository")
    print(f"  meistrocraft --github-interactive             # GitHub interactive mode")
    print(f"\n🔄 GitHub Workflow Commands (Phase 2):")
    print(f"  meistrocraft --github prs owner/repo          # List pull requests")
    print(f"  meistrocraft --github issues owner/repo       # List issues")
    print(f"  meistrocraft --github workflow owner/repo     # Show workflow status")
    print(f"  meistrocraft --memory-status                  # Show persistent memory status")
    print(f"  meistrocraft --memory-cleanup                 # Clean up old memory entries")
    print(f"  meistrocraft --memory-export                  # Export memory report")
    print(f"  meistrocraft --clear-session-memory <id>      # Clear memory for session")
    print(f"  meistrocraft --cleanup-sessions [days] [max]  # Clean up old sessions (default: 30 days, 50 max)")
    print(f"  meistrocraft --repair-sessions                # Repair corrupted session files")
    print(f"  meistrocraft --delete-session <id>            # Delete a specific session")
    print(f"\n📦 Dependencies:")
    print(f"  pip install openai rich                       # Install required packages")

if __name__ == "__main__":
    main()