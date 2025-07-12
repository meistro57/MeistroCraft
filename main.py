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

from token_tracker import TokenTracker, TokenUsage, UsageLimits
from persistent_memory import PersistentMemory, MemoryType, MemoryPriority
from workspace_manager import WorkspaceManager

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
        session_data = {
            "id": session_id,
            "name": name or f"Session {session_id}",
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
            "task_history": [],
            "context": "",
            "workspace_id": None,
            "workspace_path": None
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
        
        return session_id
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data by ID."""
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        if os.path.exists(session_file):
            with open(session_file, 'r') as f:
                return json.load(f)
        return None
    
    def find_session_by_short_id(self, short_id: str) -> Optional[str]:
        """Find full session ID by short ID (first 8 characters)."""
        for filename in os.listdir(self.sessions_dir):
            if filename.endswith('.json'):
                full_id = filename[:-5]
                if full_id.startswith(short_id):
                    return full_id
        return None
    
    def save_session(self, session_data: Dict[str, Any]) -> None:
        """Save session data."""
        session_id = session_data["id"]
        session_data["last_used"] = datetime.now().isoformat()
        
        session_file = os.path.join(self.sessions_dir, f"{session_id}.json")
        with open(session_file, 'w') as f:
            json.dump(session_data, f, indent=2)
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions."""
        sessions = []
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
        
        # Sort by last used (most recent first)
        sessions.sort(key=lambda x: x["last_used"], reverse=True)
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
    if session_id:
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

def setup_project_folder(project_name: str) -> str:
    """Create and setup a project folder for organized code generation."""
    # Clean project name for filesystem
    clean_name = "".join(c for c in project_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    clean_name = clean_name.replace(' ', '_').lower()
    
    # Create projects directory if it doesn't exist
    projects_dir = "projects"
    os.makedirs(projects_dir, exist_ok=True)
    
    # Create unique project folder
    project_folder = os.path.join(projects_dir, clean_name)
    counter = 1
    original_folder = project_folder
    
    while os.path.exists(project_folder):
        project_folder = f"{original_folder}_{counter}"
        counter += 1
    
    os.makedirs(project_folder, exist_ok=True)
    return project_folder

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
                        project_folder = setup_project_folder(user_input[:30])
                        print(f"📁 Created project folder: {project_folder}")
                else:
                    # No workspace manager, use regular project folder
                    project_folder = setup_project_folder(user_input[:30])
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
    
    # Show memory status
    memory_summary = persistent_memory.get_memory_summary()
    print(f"  {memory_summary}")
    print(f"  🏗️  Workspace isolation: enabled")
    
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
    
    elif len(sys.argv) > 1 and sys.argv[1] == "--request":
        if has_openai and len(sys.argv) > 2:
            user_request = " ".join(sys.argv[2:])
            print(f"🎯 Processing request: {user_request}")
            
            # Single requests get their own project folder
            project_folder = setup_project_folder(user_request[:30])
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
    print(f"  meistrocraft --memory-status                  # Show persistent memory status")
    print(f"  meistrocraft --memory-cleanup                 # Clean up old memory entries")
    print(f"  meistrocraft --memory-export                  # Export memory report")
    print(f"  meistrocraft --clear-session-memory <id>      # Clear memory for session")
    print(f"\n📦 Dependencies:")
    print(f"  pip install openai rich                       # Install required packages")

if __name__ == "__main__":
    main()