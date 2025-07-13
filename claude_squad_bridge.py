"""
Claude-Squad Integration Bridge
Handles subprocess communication with claude-squad-unginged for multi-agent AI development.
"""

import os
import sys
import json
import subprocess
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import shutil

logger = logging.getLogger(__name__)

class SquadAgentType(Enum):
    """Available Claude-Squad agent types"""
    CLAUDE_CODE = "claude-code"
    CODEX = "codex" 
    GEMINI = "gemini"
    AIDER = "aider"
    AUTO = "auto"

@dataclass
class SquadSession:
    """Represents a claude-squad session"""
    session_id: str
    agent_type: SquadAgentType
    project_path: str
    branch_name: str
    status: str
    created_at: str
    last_activity: str
    tmux_session: Optional[str] = None
    
class SquadInstallationError(Exception):
    """Raised when claude-squad is not properly installed"""
    pass

class SquadSessionError(Exception):
    """Raised when there's an error with squad session management"""
    pass

class ClaudeSquadBridge:
    """Bridge between MeistroCraft and Claude-Squad"""
    
    def __init__(self, projects_root: str = "projects"):
        self.projects_root = Path(projects_root)
        self.squad_command = self._find_squad_command()
        self.active_sessions: Dict[str, SquadSession] = {}
        self._installation_checked = False
        
    def _find_squad_command(self) -> Optional[str]:
        """Find the claude-squad command in PATH"""
        # Check common installation paths
        possible_commands = [
            "claude-squad",
            "squad",
            "/usr/local/bin/claude-squad",
            "/opt/homebrew/bin/claude-squad",
            os.path.expanduser("~/.local/bin/claude-squad")
        ]
        
        for cmd in possible_commands:
            if shutil.which(cmd):
                return cmd
                
        return None
    
    async def check_installation(self) -> Dict[str, Any]:
        """Check if claude-squad is properly installed and configured"""
        if self._installation_checked:
            return {"installed": self.squad_command is not None}
            
        result = {
            "installed": False,
            "squad_command": None,
            "tmux_available": False,
            "git_available": False,
            "github_cli_available": False,
            "errors": []
        }
        
        # Check claude-squad command
        if self.squad_command:
            result["squad_command"] = self.squad_command
            try:
                proc = await asyncio.create_subprocess_exec(
                    self.squad_command, "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await proc.communicate()
                if proc.returncode == 0:
                    result["installed"] = True
                    result["version"] = stdout.decode().strip()
                else:
                    result["errors"].append(f"Squad command failed: {stderr.decode()}")
            except Exception as e:
                result["errors"].append(f"Failed to run squad command: {e}")
        else:
            result["errors"].append("Claude-squad command not found in PATH")
        
        # Check dependencies
        dependencies = {
            "tmux": "tmux_available",
            "git": "git_available", 
            "gh": "github_cli_available"
        }
        
        for cmd, key in dependencies.items():
            if shutil.which(cmd):
                result[key] = True
            else:
                result["errors"].append(f"{cmd} not found in PATH")
        
        self._installation_checked = True
        return result
    
    async def install_squad(self) -> Dict[str, Any]:
        """Attempt to install claude-squad via the installation script"""
        if not shutil.which("curl"):
            return {"success": False, "error": "curl not available for installation"}
        
        try:
            # Download and run the installation script
            install_script = """
            curl -fsSL https://raw.githubusercontent.com/meistro57/claude-squad-unginged/main/install.sh | bash
            """
            
            proc = await asyncio.create_subprocess_shell(
                install_script,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                # Re-check installation
                self._installation_checked = False
                self.squad_command = self._find_squad_command()
                install_result = await self.check_installation()
                
                return {
                    "success": True,
                    "message": "Claude-squad installed successfully",
                    "installation_output": stdout.decode(),
                    "check_result": install_result
                }
            else:
                return {
                    "success": False,
                    "error": f"Installation failed: {stderr.decode()}",
                    "output": stdout.decode()
                }
                
        except Exception as e:
            return {"success": False, "error": f"Installation exception: {e}"}
    
    async def create_session(self, 
                           project_path: str,
                           agent_type: SquadAgentType = SquadAgentType.CLAUDE_CODE,
                           session_name: Optional[str] = None,
                           auto_accept: bool = False) -> SquadSession:
        """Create a new claude-squad session"""
        
        if not self.squad_command:
            raise SquadInstallationError("Claude-squad not installed")
        
        # Ensure project path exists and is absolute
        abs_project_path = (self.projects_root / project_path).resolve()
        abs_project_path.mkdir(parents=True, exist_ok=True)
        
        # Generate session name if not provided
        if not session_name:
            session_name = f"meistrocraft-{agent_type.value}-{len(self.active_sessions)}"
        
        # Build command
        cmd = [
            self.squad_command,
            "create",
            "--agent", agent_type.value,
            "--project", str(abs_project_path),
            "--name", session_name
        ]
        
        if auto_accept:
            cmd.append("--auto-accept")
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=abs_project_path
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                # Parse the session info from output
                session_info = self._parse_session_output(stdout.decode())
                
                session = SquadSession(
                    session_id=session_info.get("id", session_name),
                    agent_type=agent_type,
                    project_path=str(abs_project_path),
                    branch_name=session_info.get("branch", f"squad-{session_name}"),
                    status="active",
                    created_at=session_info.get("created_at", ""),
                    last_activity="",
                    tmux_session=session_info.get("tmux_session")
                )
                
                self.active_sessions[session.session_id] = session
                logger.info(f"Created squad session: {session.session_id}")
                
                return session
            else:
                error_msg = stderr.decode() or "Unknown error creating session"
                raise SquadSessionError(f"Failed to create session: {error_msg}")
                
        except Exception as e:
            raise SquadSessionError(f"Exception creating session: {e}")
    
    def _parse_session_output(self, output: str) -> Dict[str, str]:
        """Parse claude-squad command output for session information"""
        info = {}
        lines = output.strip().split('\n')
        
        for line in lines:
            if 'Session ID:' in line:
                info['id'] = line.split(':', 1)[1].strip()
            elif 'Branch:' in line:
                info['branch'] = line.split(':', 1)[1].strip()
            elif 'Tmux Session:' in line:
                info['tmux_session'] = line.split(':', 1)[1].strip()
            elif 'Created:' in line:
                info['created_at'] = line.split(':', 1)[1].strip()
        
        return info
    
    async def list_sessions(self) -> List[SquadSession]:
        """List all active claude-squad sessions"""
        if not self.squad_command:
            return []
        
        try:
            proc = await asyncio.create_subprocess_exec(
                self.squad_command, "list",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                sessions = self._parse_session_list(stdout.decode())
                
                # Update our active sessions
                for session in sessions:
                    self.active_sessions[session.session_id] = session
                
                return sessions
            else:
                logger.error(f"Failed to list sessions: {stderr.decode()}")
                return []
                
        except Exception as e:
            logger.error(f"Exception listing sessions: {e}")
            return []
    
    def _parse_session_list(self, output: str) -> List[SquadSession]:
        """Parse the output of 'claude-squad list' command"""
        sessions = []
        lines = output.strip().split('\n')
        
        current_session = {}
        for line in lines:
            line = line.strip()
            if not line or line.startswith('-'):
                if current_session:
                    session = SquadSession(
                        session_id=current_session.get('id', ''),
                        agent_type=SquadAgentType(current_session.get('agent', 'claude-code')),
                        project_path=current_session.get('project', ''),
                        branch_name=current_session.get('branch', ''),
                        status=current_session.get('status', 'unknown'),
                        created_at=current_session.get('created', ''),
                        last_activity=current_session.get('activity', ''),
                        tmux_session=current_session.get('tmux', None)
                    )
                    sessions.append(session)
                    current_session = {}
            else:
                if ':' in line:
                    key, value = line.split(':', 1)
                    current_session[key.lower().strip()] = value.strip()
        
        # Handle last session
        if current_session:
            session = SquadSession(
                session_id=current_session.get('id', ''),
                agent_type=SquadAgentType(current_session.get('agent', 'claude-code')),
                project_path=current_session.get('project', ''),
                branch_name=current_session.get('branch', ''),
                status=current_session.get('status', 'unknown'),
                created_at=current_session.get('created', ''),
                last_activity=current_session.get('activity', ''),
                tmux_session=current_session.get('tmux', None)
            )
            sessions.append(session)
        
        return sessions
    
    async def execute_command(self, 
                            session_id: str, 
                            command: str,
                            timeout: int = 300) -> Dict[str, Any]:
        """Execute a command in a specific squad session"""
        
        if session_id not in self.active_sessions:
            raise SquadSessionError(f"Session {session_id} not found")
        
        session = self.active_sessions[session_id]
        
        try:
            # Execute command via claude-squad
            cmd = [
                self.squad_command,
                "exec",
                "--session", session_id,
                "--", command
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), 
                    timeout=timeout
                )
                
                return {
                    "success": proc.returncode == 0,
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "exit_code": proc.returncode
                }
                
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "success": False,
                    "error": f"Command timed out after {timeout} seconds",
                    "exit_code": -1
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Exception executing command: {e}",
                "exit_code": -1
            }
    
    async def terminate_session(self, session_id: str) -> bool:
        """Terminate a claude-squad session"""
        if not self.squad_command:
            return False
        
        try:
            proc = await asyncio.create_subprocess_exec(
                self.squad_command, "terminate", session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                if session_id in self.active_sessions:
                    del self.active_sessions[session_id]
                logger.info(f"Terminated squad session: {session_id}")
                return True
            else:
                logger.error(f"Failed to terminate session {session_id}: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Exception terminating session {session_id}: {e}")
            return False
    
    async def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a specific session"""
        if not self.squad_command:
            return None
        
        try:
            proc = await asyncio.create_subprocess_exec(
                self.squad_command, "status", session_id,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                return self._parse_session_status(stdout.decode())
            else:
                return {"error": stderr.decode()}
                
        except Exception as e:
            return {"error": f"Exception getting session status: {e}"}
    
    def _parse_session_status(self, output: str) -> Dict[str, Any]:
        """Parse session status output"""
        status = {}
        lines = output.strip().split('\n')
        
        for line in lines:
            if ':' in line:
                key, value = line.split(':', 1)
                status[key.lower().strip().replace(' ', '_')] = value.strip()
        
        return status

# Global bridge instance
squad_bridge = ClaudeSquadBridge()