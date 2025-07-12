#!/usr/bin/env python3
"""
Workspace Manager for MeistroCraft
Provides git worktree-based workspace isolation similar to Claude Squad.
Each task gets its own isolated branch and workspace directory.
"""

import os
import subprocess
import uuid
import shutil
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class WorkspaceInfo:
    """Information about a workspace."""
    workspace_id: str
    session_id: str
    branch_name: str
    workspace_path: str
    base_branch: str
    created_at: str
    last_used: str
    task_description: str
    status: str  # 'active', 'paused', 'completed', 'failed'
    files_created: List[str]
    files_modified: List[str]


class GitWorktreeManager:
    """Manages git worktrees for workspace isolation."""
    
    def __init__(self, base_repo_path: str = ".", workspaces_dir: str = "workspaces"):
        self.base_repo_path = Path(base_repo_path).resolve()
        self.workspaces_dir = Path(workspaces_dir).resolve()
        self.workspaces_file = self.workspaces_dir / "workspaces.json"
        
        # Ensure directories exist
        self.workspaces_dir.mkdir(exist_ok=True)
        
        # Initialize git repo if needed
        self._ensure_git_repo()
        
        # Load existing workspaces
        self.workspaces: Dict[str, WorkspaceInfo] = self._load_workspaces()
    
    def _ensure_git_repo(self) -> None:
        """Ensure we have a git repository."""
        git_dir = self.base_repo_path / ".git"
        if not git_dir.exists():
            # Initialize git repo
            subprocess.run(["git", "init"], cwd=self.base_repo_path, check=True)
            
            # Create initial commit if no commits exist
            try:
                subprocess.run(["git", "rev-parse", "HEAD"], 
                             cwd=self.base_repo_path, check=True, 
                             capture_output=True)
            except subprocess.CalledProcessError:
                # No commits yet, create initial commit
                subprocess.run(["git", "add", "."], cwd=self.base_repo_path)
                subprocess.run(["git", "commit", "-m", "Initial commit for MeistroCraft workspace isolation"],
                             cwd=self.base_repo_path, check=True)
    
    def _load_workspaces(self) -> Dict[str, WorkspaceInfo]:
        """Load existing workspaces from storage."""
        if not self.workspaces_file.exists():
            return {}
        
        try:
            with open(self.workspaces_file, 'r') as f:
                data = json.load(f)
            
            workspaces = {}
            for workspace_id, workspace_data in data.items():
                workspaces[workspace_id] = WorkspaceInfo(**workspace_data)
            
            return workspaces
        except Exception as e:
            print(f"Warning: Failed to load workspaces: {e}")
            return {}
    
    def _save_workspaces(self) -> None:
        """Save workspaces to storage."""
        try:
            data = {}
            for workspace_id, workspace in self.workspaces.items():
                data[workspace_id] = {
                    "workspace_id": workspace.workspace_id,
                    "session_id": workspace.session_id,
                    "branch_name": workspace.branch_name,
                    "workspace_path": workspace.workspace_path,
                    "base_branch": workspace.base_branch,
                    "created_at": workspace.created_at,
                    "last_used": workspace.last_used,
                    "task_description": workspace.task_description,
                    "status": workspace.status,
                    "files_created": workspace.files_created,
                    "files_modified": workspace.files_modified
                }
            
            with open(self.workspaces_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save workspaces: {e}")
    
    def create_workspace(self, session_id: str, task_description: str, 
                        base_branch: Optional[str] = None) -> WorkspaceInfo:
        """Create a new isolated workspace using git worktree."""
        workspace_id = str(uuid.uuid4())[:8]  # Short ID for readability
        branch_name = f"task-{workspace_id}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        workspace_path = str(self.workspaces_dir / f"workspace-{workspace_id}")
        
        try:
            # Auto-detect base branch if not specified
            if base_branch is None:
                try:
                    # Try to get current branch
                    current_branch_result = subprocess.run(["git", "branch", "--show-current"],
                                                          cwd=self.base_repo_path, 
                                                          capture_output=True, text=True)
                    if current_branch_result.returncode == 0 and current_branch_result.stdout.strip():
                        base_branch = current_branch_result.stdout.strip()
                    else:
                        # Try master first, then main
                        try:
                            subprocess.run(["git", "show-ref", "--verify", "refs/heads/master"],
                                         cwd=self.base_repo_path, check=True, capture_output=True)
                            base_branch = "master"
                        except subprocess.CalledProcessError:
                            try:
                                subprocess.run(["git", "show-ref", "--verify", "refs/heads/main"],
                                             cwd=self.base_repo_path, check=True, capture_output=True)
                                base_branch = "main"
                            except subprocess.CalledProcessError:
                                # Get the first branch that exists
                                branches_result = subprocess.run(["git", "branch", "--list"],
                                                               cwd=self.base_repo_path,
                                                               capture_output=True, text=True)
                                if branches_result.returncode == 0:
                                    branches = [b.strip().lstrip('* ') for b in branches_result.stdout.strip().split('\n') if b.strip()]
                                    if branches:
                                        base_branch = branches[0]
                                    else:
                                        # No branches exist, create master
                                        subprocess.run(["git", "checkout", "-b", "master"],
                                                     cwd=self.base_repo_path, check=True)
                                        base_branch = "master"
                except subprocess.CalledProcessError:
                    base_branch = "master"  # Default fallback
            
            # Ensure base branch exists
            self._ensure_branch_exists(base_branch)
            
            # Ensure we're on the base branch
            subprocess.run(["git", "checkout", base_branch], 
                         cwd=self.base_repo_path, check=True)
            
            # Create worktree with new branch (this creates both the branch and worktree)
            subprocess.run(["git", "worktree", "add", "-b", branch_name, workspace_path, base_branch],
                         cwd=self.base_repo_path, check=True)
            
            # Create workspace info
            workspace = WorkspaceInfo(
                workspace_id=workspace_id,
                session_id=session_id,
                branch_name=branch_name,
                workspace_path=workspace_path,
                base_branch=base_branch,
                created_at=datetime.now().isoformat(),
                last_used=datetime.now().isoformat(),
                task_description=task_description,
                status="active",
                files_created=[],
                files_modified=[]
            )
            
            # Store workspace
            self.workspaces[workspace_id] = workspace
            self._save_workspaces()
            
            print(f"🏗️  Created workspace {workspace_id} on branch {branch_name}")
            return workspace
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to create workspace: {e}")
            # Cleanup on failure
            try:
                subprocess.run(["git", "worktree", "remove", workspace_path],
                             cwd=self.base_repo_path)
                subprocess.run(["git", "branch", "-D", branch_name],
                             cwd=self.base_repo_path)
            except:
                pass
            raise
    
    def _ensure_branch_exists(self, branch_name: str) -> None:
        """Ensure a branch exists, create if it doesn't."""
        try:
            # Check if branch exists
            subprocess.run(["git", "show-ref", "--verify", f"refs/heads/{branch_name}"],
                         cwd=self.base_repo_path, check=True, capture_output=True)
        except subprocess.CalledProcessError:
            # Branch doesn't exist, create it
            try:
                # Try to create from origin if it exists
                subprocess.run(["git", "checkout", "-b", branch_name, f"origin/{branch_name}"],
                             cwd=self.base_repo_path, check=True, capture_output=True)
            except subprocess.CalledProcessError:
                # Create new branch from current HEAD or master/main
                try:
                    # Try to get current branch or default to master/main
                    current_branch_result = subprocess.run(["git", "branch", "--show-current"],
                                                          cwd=self.base_repo_path, 
                                                          capture_output=True, text=True)
                    if current_branch_result.returncode == 0 and current_branch_result.stdout.strip():
                        current_branch = current_branch_result.stdout.strip()
                    else:
                        # Try master first, then main
                        try:
                            subprocess.run(["git", "show-ref", "--verify", "refs/heads/master"],
                                         cwd=self.base_repo_path, check=True, capture_output=True)
                            current_branch = "master"
                        except subprocess.CalledProcessError:
                            try:
                                subprocess.run(["git", "show-ref", "--verify", "refs/heads/main"],
                                             cwd=self.base_repo_path, check=True, capture_output=True)
                                current_branch = "main"
                            except subprocess.CalledProcessError:
                                # Use HEAD if no main/master branches exist
                                current_branch = "HEAD"
                    
                    if current_branch != branch_name:
                        subprocess.run(["git", "checkout", current_branch],
                                     cwd=self.base_repo_path, check=True)
                        subprocess.run(["git", "checkout", "-b", branch_name],
                                     cwd=self.base_repo_path, check=True)
                except subprocess.CalledProcessError:
                    # Last resort: create from HEAD
                    subprocess.run(["git", "checkout", "-b", branch_name],
                                 cwd=self.base_repo_path, check=True)
    
    def get_workspace(self, workspace_id: str) -> Optional[WorkspaceInfo]:
        """Get workspace by ID."""
        return self.workspaces.get(workspace_id)
    
    def get_workspace_by_session(self, session_id: str) -> Optional[WorkspaceInfo]:
        """Get active workspace for a session."""
        for workspace in self.workspaces.values():
            if workspace.session_id == session_id and workspace.status == "active":
                return workspace
        return None
    
    def list_workspaces(self, status_filter: Optional[str] = None) -> List[WorkspaceInfo]:
        """List all workspaces, optionally filtered by status."""
        workspaces = list(self.workspaces.values())
        if status_filter:
            workspaces = [w for w in workspaces if w.status == status_filter]
        return sorted(workspaces, key=lambda w: w.last_used, reverse=True)
    
    def pause_workspace(self, workspace_id: str) -> bool:
        """Pause a workspace (mark as paused, keep worktree)."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False
        
        workspace.status = "paused"
        workspace.last_used = datetime.now().isoformat()
        self._save_workspaces()
        
        print(f"⏸️  Paused workspace {workspace_id}")
        return True
    
    def resume_workspace(self, workspace_id: str) -> bool:
        """Resume a paused workspace."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace or workspace.status != "paused":
            return False
        
        # Check if worktree still exists
        if not Path(workspace.workspace_path).exists():
            print(f"❌ Workspace directory missing: {workspace.workspace_path}")
            return False
        
        workspace.status = "active"
        workspace.last_used = datetime.now().isoformat()
        self._save_workspaces()
        
        print(f"▶️  Resumed workspace {workspace_id}")
        return True
    
    def complete_workspace(self, workspace_id: str, merge_back: bool = True) -> bool:
        """Complete a workspace and optionally merge changes back."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False
        
        try:
            if merge_back:
                # Switch to base branch and merge
                subprocess.run(["git", "checkout", workspace.base_branch],
                             cwd=self.base_repo_path, check=True)
                subprocess.run(["git", "merge", workspace.branch_name],
                             cwd=self.base_repo_path, check=True)
                print(f"✅ Merged {workspace.branch_name} into {workspace.base_branch}")
            
            # Remove worktree
            subprocess.run(["git", "worktree", "remove", workspace.workspace_path],
                         cwd=self.base_repo_path, check=True)
            
            # Delete branch if merged
            if merge_back:
                subprocess.run(["git", "branch", "-d", workspace.branch_name],
                             cwd=self.base_repo_path, check=True)
            
            workspace.status = "completed"
            workspace.last_used = datetime.now().isoformat()
            self._save_workspaces()
            
            print(f"🎉 Completed workspace {workspace_id}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to complete workspace: {e}")
            return False
    
    def abandon_workspace(self, workspace_id: str) -> bool:
        """Abandon a workspace without merging changes."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return False
        
        try:
            # Remove worktree
            subprocess.run(["git", "worktree", "remove", workspace.workspace_path, "--force"],
                         cwd=self.base_repo_path, check=True)
            
            # Delete branch
            subprocess.run(["git", "branch", "-D", workspace.branch_name],
                         cwd=self.base_repo_path, check=True)
            
            workspace.status = "failed"
            workspace.last_used = datetime.now().isoformat()
            self._save_workspaces()
            
            print(f"🗑️  Abandoned workspace {workspace_id}")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to abandon workspace: {e}")
            return False
    
    def get_workspace_status(self, workspace_id: str) -> Dict[str, Any]:
        """Get detailed status of a workspace."""
        workspace = self.workspaces.get(workspace_id)
        if not workspace:
            return {"error": "Workspace not found"}
        
        status = {
            "workspace": workspace,
            "exists": Path(workspace.workspace_path).exists(),
            "branch_exists": False,
            "has_changes": False,
            "ahead_behind": None
        }
        
        try:
            # Check if branch exists
            subprocess.run(["git", "show-ref", "--verify", f"refs/heads/{workspace.branch_name}"],
                         cwd=self.base_repo_path, check=True, capture_output=True)
            status["branch_exists"] = True
            
            # Check for uncommitted changes
            if status["exists"]:
                result = subprocess.run(["git", "status", "--porcelain"],
                                      cwd=workspace.workspace_path, 
                                      capture_output=True, text=True)
                status["has_changes"] = bool(result.stdout.strip())
                
                # Check ahead/behind status
                result = subprocess.run(["git", "rev-list", "--left-right", "--count",
                                       f"{workspace.base_branch}...{workspace.branch_name}"],
                                      cwd=self.base_repo_path, 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    behind, ahead = result.stdout.strip().split('\t')
                    status["ahead_behind"] = {"ahead": int(ahead), "behind": int(behind)}
                    
        except subprocess.CalledProcessError:
            pass
        
        return status
    
    def cleanup_completed_workspaces(self, older_than_days: int = 7) -> int:
        """Clean up old completed workspaces."""
        cutoff_date = datetime.now().timestamp() - (older_than_days * 24 * 60 * 60)
        cleaned = 0
        
        to_remove = []
        for workspace_id, workspace in self.workspaces.items():
            if workspace.status == "completed":
                last_used = datetime.fromisoformat(workspace.last_used).timestamp()
                if last_used < cutoff_date:
                    to_remove.append(workspace_id)
        
        for workspace_id in to_remove:
            del self.workspaces[workspace_id]
            cleaned += 1
        
        if cleaned > 0:
            self._save_workspaces()
            print(f"🧹 Cleaned up {cleaned} old completed workspaces")
        
        return cleaned


class WorkspaceManager:
    """High-level workspace manager for MeistroCraft integration."""
    
    def __init__(self, base_repo_path: str = ".", workspaces_dir: str = "workspaces"):
        self.git_manager = GitWorktreeManager(base_repo_path, workspaces_dir)
        self.active_workspaces: Dict[str, str] = {}  # session_id -> workspace_id
    
    def create_session_workspace(self, session_id: str, task_description: str) -> Optional[str]:
        """Create a new workspace for a session."""
        try:
            workspace = self.git_manager.create_workspace(session_id, task_description)
            self.active_workspaces[session_id] = workspace.workspace_id
            return workspace.workspace_path
        except Exception as e:
            print(f"❌ Failed to create workspace for session {session_id}: {e}")
            return None
    
    def get_session_workspace_path(self, session_id: str) -> Optional[str]:
        """Get the workspace path for a session."""
        workspace = self.git_manager.get_workspace_by_session(session_id)
        if workspace and workspace.status == "active":
            return workspace.workspace_path
        return None
    
    def complete_session_workspace(self, session_id: str, merge_back: bool = True) -> bool:
        """Complete the workspace for a session."""
        workspace = self.git_manager.get_workspace_by_session(session_id)
        if workspace:
            success = self.git_manager.complete_workspace(workspace.workspace_id, merge_back)
            if success and session_id in self.active_workspaces:
                del self.active_workspaces[session_id]
            return success
        return False
    
    def list_session_workspaces(self) -> List[Dict[str, Any]]:
        """List all workspaces with their status."""
        workspaces = self.git_manager.list_workspaces()
        result = []
        
        for workspace in workspaces:
            status = self.git_manager.get_workspace_status(workspace.workspace_id)
            result.append({
                "workspace_id": workspace.workspace_id,
                "session_id": workspace.session_id,
                "task_description": workspace.task_description,
                "status": workspace.status,
                "created_at": workspace.created_at,
                "branch_name": workspace.branch_name,
                "workspace_path": workspace.workspace_path,
                "exists": status.get("exists", False),
                "has_changes": status.get("has_changes", False)
            })
        
        return result