#!/usr/bin/env python3
"""
FastAPI Web Server for MeistroCraft Browser IDE
Provides REST API and WebSocket endpoints for the browser-based interface.
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import HTMLResponse, FileResponse
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.templating import Jinja2Templates
    import uvicorn
except ImportError:
    print("FastAPI dependencies not found. Install with: pip install -r requirements.txt")
    sys.exit(1)

# Import existing MeistroCraft modules
from interactive_ui import InteractiveSession
from task_queue import get_task_queue, TaskPriority, TaskStatus
from workspace_manager import WorkspaceManager
from token_tracker import TokenTracker
from main import SessionManager, load_config, save_config, setup_environment, generate_task_with_gpt4, run_claude_task
from claude_squad_bridge import squad_bridge, SquadAgentType, SquadSession

app = FastAPI(
    title="MeistroCraft IDE",
    description="Browser-based IDE interface for MeistroCraft AI Development Orchestrator",
    version="2.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    print("🚀 Starting MeistroCraft IDE Web Server...")
    
    # Ensure projects directory exists
    projects_dir = Path("projects")
    projects_dir.mkdir(exist_ok=True)
    print(f"📁 Projects directory: {projects_dir.resolve()}")
    
    # Test backend initialization
    if session_manager.session_manager:
        print("✅ MeistroCraft backend ready")
    else:
        print("⚠️  MeistroCraft backend not available - check your configuration")

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state management
class WebSessionManager:
    """Manages web-based interactive sessions."""
    
    def __init__(self):
        self.sessions: Dict[str, str] = {}  # web_session_id -> meistrocraft_session_id
        self.websockets: Dict[str, WebSocket] = {}
        self.task_queue = get_task_queue()
        
        # Initialize MeistroCraft components
        try:
            self.config = load_config()
            setup_environment(self.config)
            self.session_manager = SessionManager()
            self.token_tracker = TokenTracker()
            print("✅ MeistroCraft backend initialized successfully")
        except Exception as e:
            print(f"❌ Failed to initialize MeistroCraft backend: {e}")
            self.config = None
            self.session_manager = None
            self.token_tracker = None
        
    async def create_session(self, session_id: str, config: Dict[str, Any] = None) -> str:
        """Create a new MeistroCraft session for web interface."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        if not self.session_manager:
            raise Exception("MeistroCraft backend not initialized")
            
        # Create a new MeistroCraft session
        meistrocraft_session_id = self.session_manager.create_session(
            name=f"Web Session {session_id[:8]}",
            task_description="Web IDE session"
        )
        
        self.sessions[session_id] = meistrocraft_session_id
        print(f"🌐 Created MeistroCraft session {meistrocraft_session_id[:8]} for web session {session_id[:8]}")
        return meistrocraft_session_id
        
    async def get_session(self, session_id: str) -> Optional[InteractiveSession]:
        """Get existing session."""
        return self.sessions.get(session_id)
        
    async def register_websocket(self, session_id: str, websocket: WebSocket):
        """Register WebSocket connection for session."""
        self.websockets[session_id] = websocket
        
    async def unregister_websocket(self, session_id: str):
        """Unregister WebSocket connection."""
        if session_id in self.websockets:
            del self.websockets[session_id]

# Global session manager
session_manager = WebSessionManager()

# Templates and static files
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_ide(request: Request):
    """Serve the main IDE interface."""
    return templates.TemplateResponse("ide.html", {"request": request})

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0"
    }

@app.get("/MeistroCraft_logo.ico")
async def serve_favicon():
    """Serve the favicon."""
    return FileResponse("MeistroCraft_logo.ico", media_type="image/x-icon")

@app.get("/MeistroCraft_logo.png")
async def serve_logo():
    """Serve the PNG logo."""
    return FileResponse("MeistroCraft_logo.png", media_type="image/png")

@app.post("/api/sessions")
async def create_session(request: Request):
    """Create a new interactive session."""
    body = await request.json()
    session_id = body.get("session_id", f"web-{datetime.now().timestamp()}")
    config = body.get("config", {})
    
    session = await session_manager.create_session(session_id, config)
    
    return {
        "session_id": session_id,
        "status": "created",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/sessions")
async def list_sessions():
    """List all available sessions."""
    try:
        if not session_manager.session_manager:
            raise HTTPException(status_code=503, detail="Backend not initialized")
        
        # Get real sessions from MeistroCraft
        sessions_data = session_manager.session_manager.list_sessions()
        
        sessions = []
        for session in sessions_data[:10]:  # Limit to 10 recent sessions
            sessions.append({
                "id": session["id"],
                "name": session["name"],
                "created_at": session["created_at"],
                "last_accessed": session["last_used"],
                "task_count": session["task_count"],
                "status": "active" if session["task_count"] > 0 else "inactive"
            })
        
        return {
            "sessions": sessions,
            "total": len(sessions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/sessions/{session_id}")
async def update_session(session_id: str, request: Request):
    """Update session information."""
    try:
        body = await request.json()
        name = body.get("name")
        
        # Mock update - in real implementation would use session_manager
        return {
            "session_id": session_id,
            "name": name,
            "status": "updated",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    try:
        # Mock delete - in real implementation would use session_manager
        return {
            "session_id": session_id,
            "status": "deleted",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/settings")
async def get_settings():
    """Get application settings."""
    try:
        # Mock settings - in real implementation would read from config
        default_settings = {
            "api": {
                "supported_models": ["gpt-4", "gpt-3.5-turbo", "claude-3-sonnet", "claude-3-haiku"],
                "default_model": "gpt-4"
            },
            "editor": {
                "themes": ["vs-dark", "vs", "hc-black"],
                "default_theme": "vs-dark",
                "font_sizes": list(range(10, 25)),
                "default_font_size": 14
            },
            "limits": {
                "default_daily_limit": 5.00,
                "default_monthly_limit": 50.00,
                "max_daily_limit": 100.00,
                "max_monthly_limit": 1000.00
            }
        }
        return default_settings
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/settings")
async def save_settings(request: Request):
    """Save user settings."""
    try:
        settings = await request.json()
        # Mock save - in real implementation would save to user config
        return {
            "status": "saved",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/config")
async def get_api_config():
    """Get API configuration status."""
    try:
        config_status = {
            "openai": {
                "configured": False,
                "model": None,
                "status": "not_configured"
            },
            "anthropic": {
                "configured": False,
                "model": None,
                "status": "not_configured"
            },
            "github": {
                "configured": False,
                "username": None,
                "status": "not_configured"
            }
        }
        
        if session_manager.config and isinstance(session_manager.config, dict):
            # Check OpenAI configuration
            if session_manager.config.get("openai_api_key"):
                config_status["openai"]["configured"] = True
                config_status["openai"]["model"] = session_manager.config.get("openai_model", "gpt-4")
                config_status["openai"]["status"] = "configured"
            
            # Check Anthropic configuration
            if session_manager.config.get("anthropic_api_key"):
                config_status["anthropic"]["configured"] = True
                config_status["anthropic"]["model"] = session_manager.config.get("claude_model", "claude-3-sonnet")
                config_status["anthropic"]["status"] = "configured"
            
            # Check GitHub configuration
            if session_manager.config.get("github_api_key"):
                config_status["github"]["configured"] = True
                config_status["github"]["status"] = "configured"
        
        return config_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/config")
async def save_api_config(request: Request):
    """Save API configuration."""
    try:
        body = await request.json()
        
        # Load current config
        try:
            current_config = load_config()
        except:
            # If config doesn't exist, create a new one
            current_config = {
                "anthropic_api_key": "<YOUR_ANTHROPIC_API_KEY>",
                "openai_api_key": "<YOUR_OPENAI_API_KEY>",
                "github_api_key": "<YOUR_GITHUB_API_KEY>",
                "claude_model": "claude-3-sonnet-20240229",
                "openai_model": "gpt-4",
                "max_tokens": 4000,
                "max_context_length": 16000,
                "usage_limits": {
                    "daily_limit": 5.0,
                    "monthly_limit": 50.0
                }
            }
        
        # Update config with new values
        if body.get("openai_api_key"):
            current_config["openai_api_key"] = body["openai_api_key"]
        if body.get("anthropic_api_key"):
            current_config["anthropic_api_key"] = body["anthropic_api_key"]
        if body.get("github_api_key"):
            current_config["github_api_key"] = body["github_api_key"]
        if body.get("openai_model"):
            current_config["openai_model"] = body["openai_model"]
        if body.get("claude_model"):
            current_config["claude_model"] = body["claude_model"]
        
        # Save config to file
        save_config(current_config)
        
        # Update session manager config
        session_manager.config = current_config
        setup_environment(current_config)
        
        return {
            "status": "success",
            "message": "API configuration saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/test-api-key")
async def test_api_key(request: Request):
    """Test an API key for validity."""
    try:
        body = await request.json()
        provider = body.get("provider")  # "openai", "anthropic", or "github"
        api_key = body.get("api_key")
        
        if not provider or not api_key:
            raise HTTPException(status_code=400, detail="Provider and API key required")
        
        if provider == "github":
            # Test GitHub API key
            try:
                import requests
                headers = {
                    "Authorization": f"token {api_key}",
                    "Accept": "application/vnd.github.v3+json"
                }
                response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
                
                if response.status_code == 200:
                    try:
                        user_data = response.json()
                        # Ensure user_data is a dict, not a string
                        if isinstance(user_data, str):
                            return {
                                "provider": provider,
                                "status": "invalid",
                                "message": f"Unexpected response format: {user_data}"
                            }
                        return {
                            "provider": provider,
                            "status": "valid",
                            "message": f"Authenticated as {user_data.get('login', 'Unknown user')}",
                            "username": user_data.get("login", "Unknown")
                        }
                    except Exception as json_error:
                        return {
                            "provider": provider,
                            "status": "invalid",
                            "message": f"Failed to parse GitHub response: {str(json_error)}"
                        }
                else:
                    return {
                        "provider": provider,
                        "status": "invalid",
                        "message": f"GitHub API error: {response.status_code}"
                    }
            except Exception as e:
                return {
                    "provider": provider,
                    "status": "invalid",
                    "message": f"GitHub API test failed: {str(e)}"
                }
        elif provider == "openai":
            # Test OpenAI API key
            try:
                import openai
                client = openai.OpenAI(api_key=api_key)
                # Simple test call
                response = client.models.list()
                return {
                    "provider": provider,
                    "status": "valid",
                    "message": "API key is valid"
                }
            except Exception as e:
                return {
                    "provider": provider,
                    "status": "invalid",
                    "message": str(e)
                }
        
        elif provider == "anthropic":
            # Test Anthropic API key
            try:
                import requests
                headers = {
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                
                # Simple test call to check key validity
                test_data = {
                    "model": "claude-3-haiku-20240307",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}]
                }
                
                response = requests.post(
                    "https://api.anthropic.com/v1/messages",
                    headers=headers,
                    json=test_data,
                    timeout=30
                )
                
                if response.status_code == 200:
                    return {
                        "provider": provider,
                        "status": "valid",
                        "message": "API key is valid"
                    }
                else:
                    return {
                        "provider": provider,
                        "status": "invalid",
                        "message": f"API returned status {response.status_code}"
                    }
            except Exception as e:
                return {
                    "provider": provider,
                    "status": "invalid",
                    "message": str(e)
                }
        
        else:
            raise HTTPException(status_code=400, detail="Unsupported provider")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/github/repositories")
async def get_github_repositories():
    """Get user's GitHub repositories."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        repositories = client.list_repositories()
        return {
            "repositories": repositories,
            "total": len(repositories)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/github/repository")
async def create_github_repository(request: Request):
    """Create a new GitHub repository."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        body = await request.json()
        name = body.get("name")
        description = body.get("description", "")
        private = body.get("private", False)
        
        if not name:
            raise HTTPException(status_code=400, detail="Repository name is required")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        repository = client.create_repository(name, description, private)
        return repository
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/github/repository/{owner}/{repo}/fork")
async def fork_github_repository(owner: str, repo: str):
    """Fork a GitHub repository."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        fork = client.fork_repository(owner, repo)
        return fork
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/github/repository/{owner}/{repo}/contents")
async def get_github_repository_contents(owner: str, repo: str, path: str = ""):
    """Get contents of a GitHub repository directory."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        # List directory contents
        import requests
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        headers = {
            "Authorization": f"token {session_manager.config['github_api_key']}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail="Failed to get repository contents")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/github/repository/{owner}/{repo}/file")
async def get_github_file(owner: str, repo: str, path: str):
    """Get a specific file from GitHub repository."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        file_data = client.get_file_content(owner, repo, path)
        return file_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/github/repository/{owner}/{repo}/file")
async def create_github_file(owner: str, repo: str, request: Request):
    """Create a new file in GitHub repository."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        body = await request.json()
        path = body.get("path")
        content = body.get("content")
        message = body.get("message", f"Create {path}")
        branch = body.get("branch", "main")
        
        if not path or content is None:
            raise HTTPException(status_code=400, detail="Path and content are required")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        result = client.create_file(owner, repo, path, content, message, branch)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/github/repository/{owner}/{repo}/file")
async def update_github_file(owner: str, repo: str, request: Request):
    """Update an existing file in GitHub repository."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        body = await request.json()
        path = body.get("path")
        content = body.get("content")
        message = body.get("message", f"Update {path}")
        sha = body.get("sha")
        branch = body.get("branch", "main")
        
        if not path or content is None or not sha:
            raise HTTPException(status_code=400, detail="Path, content, and SHA are required")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        result = client.update_file(owner, repo, path, content, message, sha, branch)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/github/sync-project")
async def sync_project_to_github(request: Request):
    """Sync current project to GitHub repository."""
    try:
        if not session_manager.config or not isinstance(session_manager.config, dict) or not session_manager.config.get("github_api_key"):
            raise HTTPException(status_code=400, detail="GitHub API key not configured")
        
        body = await request.json()
        owner = body.get("owner")
        repo = body.get("repo")
        project_path = body.get("project_path")
        branch = body.get("branch", "main")
        
        if not owner or not repo or not project_path:
            raise HTTPException(status_code=400, detail="Owner, repo, and project_path are required")
        
        # Check if project path exists and is within projects directory
        import os
        full_project_path = os.path.join(os.getcwd(), "projects", project_path)
        if not os.path.exists(full_project_path):
            raise HTTPException(status_code=404, detail="Project path not found")
        
        from github_client import GitHubClient
        client = GitHubClient(session_manager.config["github_api_key"])
        
        synced_files = []
        failed_files = []
        
        # Walk through project directory and sync files
        for root, dirs, files in os.walk(full_project_path):
            for file in files:
                local_file_path = os.path.join(root, file)
                relative_path = os.path.relpath(local_file_path, full_project_path)
                
                try:
                    # Read local file content
                    with open(local_file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Try to get existing file from GitHub
                    try:
                        existing_file = client.get_file_content(owner, repo, relative_path, branch)
                        # File exists, update it
                        result = client.update_file(
                            owner, repo, relative_path, content,
                            f"Sync: Update {relative_path}", existing_file["sha"], branch
                        )
                        synced_files.append({
                            "path": relative_path,
                            "action": "updated",
                            "sha": result["content"]["sha"]
                        })
                    except Exception:
                        # File doesn't exist or other error, create it
                        result = client.create_file(
                            owner, repo, relative_path, content,
                            f"Sync: Create {relative_path}", branch
                        )
                        synced_files.append({
                            "path": relative_path,
                            "action": "created",
                            "sha": result["content"]["sha"]
                        })
                        
                except Exception as e:
                    failed_files.append({
                        "path": relative_path,
                        "error": str(e)
                    })
        
        return {
            "synced_files": synced_files,
            "failed_files": failed_files,
            "total_synced": len(synced_files),
            "total_failed": len(failed_files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Get session information."""
    session = await session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "status": "active",
        "timestamp": datetime.now().isoformat()
    }

@app.post("/api/projects/generate")
async def generate_project(request: Request):
    """Generate a new project from wizard specifications."""
    try:
        body = await request.json()
        project_spec = body.get("project_spec", {})
        session_id = body.get("session_id")
        
        if not project_spec:
            raise HTTPException(status_code=400, detail="Project specification required")
        
        # Ensure we have a MeistroCraft session
        meistrocraft_session_id = await session_manager.create_session(session_id or f"project-{datetime.now().timestamp()}")
        
        # Get session data for project folder
        session_data = session_manager.session_manager.load_session(meistrocraft_session_id)
        project_folder = session_data.get("project_folder") if session_data else None
        
        # Create project generation task
        project_prompt = create_project_generation_prompt(project_spec)
        
        # Generate task with GPT-4
        task = generate_task_with_gpt4(
            project_prompt,
            session_manager.config,
            project_folder,
            session_manager.token_tracker,
            meistrocraft_session_id
        )
        
        if not task:
            raise HTTPException(status_code=500, detail="Failed to generate project task")
        
        # Execute with Claude
        result = run_claude_task(
            task,
            session_manager.config,
            meistrocraft_session_id,
            session_manager.session_manager,
            project_folder,
            session_manager.token_tracker
        )
        
        if result.get("success"):
            # Save to session
            session_manager.session_manager.add_task_to_session(meistrocraft_session_id, task, result)
            
            return {
                "success": True,
                "project_id": meistrocraft_session_id,
                "project_folder": project_folder,
                "message": "Project generated successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            raise HTTPException(status_code=500, detail=f"Project generation failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def create_project_generation_prompt(project_spec: Dict[str, Any]) -> str:
    """Create a comprehensive prompt for project generation."""
    proj = project_spec.get("project", {})
    tech = project_spec.get("technology", {})
    features = project_spec.get("features", {})
    requirements = project_spec.get("requirements", {})
    options = project_spec.get("generation_options", {})
    
    prompt = f"""🚀 **PROJECT GENERATION REQUEST**

Create a complete {proj.get('type', 'application')} project based on these specifications:

## Project Overview
- **Name**: {proj.get('name', 'New Project')}
- **Description**: {proj.get('description', 'A new project')}
- **Target Audience**: {proj.get('target_audience', 'General users')}

## Technology Stack
- **Primary Language**: {tech.get('primary_language', 'Not specified')}
- **Frameworks**: {', '.join(tech.get('frameworks', [])) or 'None specified'}
- **Database**: {tech.get('database', 'None')}
- **Additional Technologies**: {', '.join(tech.get('additional_tech', [])) or 'None'}

## Core Features
{chr(10).join(f'- {feature}' for feature in features.get('core_features', [])) or '- Basic functionality'}

## Authentication & API
- **Authentication**: {features.get('authentication', 'None')}
- **API Features**: {', '.join(features.get('api_features', [])) or 'None'}

## Requirements
- **Performance**: {requirements.get('performance', 'Standard performance')}
- **Security**: {', '.join(requirements.get('security', [])) or 'Basic security'}
- **Deployment**: {requirements.get('deployment', 'Local development')}
- **Constraints**: {requirements.get('constraints', 'None specified')}

## Generation Instructions
"""
    
    if options.get('generate_structure'):
        prompt += "✅ Generate complete project structure with proper folder organization\n"
    if options.get('generate_boilerplate'):
        prompt += "✅ Create boilerplate code with best practices and patterns\n"
    if options.get('generate_docs'):
        prompt += "✅ Generate comprehensive documentation (README, API docs, etc.)\n"
    if options.get('generate_tests'):
        prompt += "✅ Create test templates and example tests\n"
    
    if options.get('final_instructions'):
        prompt += f"\n## Additional Instructions\n{options['final_instructions']}\n"
    
    prompt += """
Please create a complete, functional project foundation that:
1. Follows industry best practices and conventions
2. Includes proper error handling and validation
3. Has a clear, scalable architecture
4. Provides a solid foundation for further development
5. Includes clear setup and usage instructions

Start with the project structure, implement core functionality, and provide detailed documentation."""
    
    return prompt

@app.get("/api/projects")
async def list_projects():
    """List all projects with metadata."""
    try:
        projects_root = Path("projects").resolve()
        if not projects_root.exists():
            return []
        
        projects = []
        for project_dir in projects_root.iterdir():
            if project_dir.is_dir():
                project_data = await analyze_project_folder(project_dir)
                projects.append(project_data)
        
        # Sort by last modified
        projects.sort(key=lambda x: x.get('modified', ''), reverse=True)
        return projects
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_path:path}/stats")
async def get_project_stats(project_path: str):
    """Get project statistics."""
    try:
        projects_root = Path("projects").resolve()
        full_path = (projects_root / project_path).resolve()
        
        # Security check
        try:
            full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        stats = await calculate_project_stats(full_path)
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects/{project_path:path}/details")
async def get_project_details(project_path: str):
    """Get detailed project information."""
    try:
        projects_root = Path("projects").resolve()
        full_path = (projects_root / project_path).resolve()
        
        # Security check
        try:
            full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        details = await get_detailed_project_info(full_path)
        return details
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/projects/{project_path:path}/status")
async def update_project_status(project_path: str, request: Request):
    """Update project status (active, archived, deleted)."""
    try:
        body = await request.json()
        new_status = body.get("status")
        
        if new_status not in ["active", "archived", "deleted"]:
            raise HTTPException(status_code=400, detail="Invalid status")
        
        projects_root = Path("projects").resolve()
        full_path = (projects_root / project_path).resolve()
        
        # Security check
        try:
            full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Update project metadata
        await update_project_metadata(full_path, {"status": new_status, "modified": datetime.now().isoformat()})
        
        return {"success": True, "status": new_status}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/projects/{project_path:path}")
async def delete_project(project_path: str):
    """Permanently delete a project."""
    try:
        projects_root = Path("projects").resolve()
        full_path = (projects_root / project_path).resolve()
        
        # Security check
        try:
            full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Remove the entire project directory
        import shutil
        shutil.rmtree(full_path)
        
        return {"success": True, "message": "Project deleted successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/duplicate")
async def duplicate_project(request: Request):
    """Duplicate an existing project."""
    try:
        body = await request.json()
        source_path = body.get("source_path")
        new_name = body.get("new_name")
        
        if not source_path or not new_name:
            raise HTTPException(status_code=400, detail="Source path and new name required")
        
        projects_root = Path("projects").resolve()
        source_full_path = (projects_root / source_path).resolve()
        target_full_path = projects_root / new_name
        
        # Security checks
        try:
            source_full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not source_full_path.exists():
            raise HTTPException(status_code=404, detail="Source project not found")
        
        if target_full_path.exists():
            raise HTTPException(status_code=409, detail="Project with that name already exists")
        
        # Copy the project
        import shutil
        shutil.copytree(source_full_path, target_full_path)
        
        # Update metadata in the new project
        await update_project_metadata(target_full_path, {
            "name": new_name,
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "status": "active"
        })
        
        return {"success": True, "new_path": str(target_full_path)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_path:path}/export")
async def export_project(project_path: str):
    """Export project as ZIP file."""
    try:
        projects_root = Path("projects").resolve()
        full_path = (projects_root / project_path).resolve()
        
        # Security check
        try:
            full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Create temporary ZIP file
        import tempfile
        import zipfile
        
        temp_dir = tempfile.mkdtemp()
        zip_path = Path(temp_dir) / f"{full_path.name}.zip"
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in full_path.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(full_path)
                    zipf.write(file_path, arcname)
        
        # Return the ZIP file
        return FileResponse(
            path=zip_path,
            filename=f"{full_path.name}.zip",
            media_type="application/zip"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/import")
async def import_project(request: Request):
    """Import project from ZIP file."""
    try:
        # Handle file upload
        form = await request.form()
        file = form.get("project_file")
        
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Save uploaded file temporarily
        import tempfile
        import zipfile
        
        temp_dir = tempfile.mkdtemp()
        zip_path = Path(temp_dir) / file.filename
        
        with open(zip_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # Extract to projects directory
        projects_root = Path("projects").resolve()
        project_name = file.filename.replace('.zip', '')
        target_path = projects_root / project_name
        
        if target_path.exists():
            raise HTTPException(status_code=409, detail="Project already exists")
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(target_path)
        
        # Clean up temp file
        zip_path.unlink()
        
        # Update project metadata
        await update_project_metadata(target_path, {
            "name": project_name,
            "imported": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "status": "active"
        })
        
        return {"success": True, "project_path": str(target_path)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Claude-Squad Integration Endpoints

@app.get("/api/squad/status")
async def get_squad_status():
    """Check claude-squad installation and status."""
    try:
        status = await squad_bridge.check_installation()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/squad/install")
async def install_squad():
    """Install claude-squad if not present."""
    try:
        result = await squad_bridge.install_squad()
        if result["success"]:
            return result
        else:
            raise HTTPException(status_code=500, detail=result["error"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/squad/sessions")
async def list_squad_sessions():
    """List all active claude-squad sessions."""
    try:
        sessions = await squad_bridge.list_sessions()
        return {
            "sessions": [
                {
                    "id": session.session_id,
                    "agent_type": session.agent_type.value,
                    "project_path": session.project_path,
                    "branch_name": session.branch_name,
                    "status": session.status,
                    "created_at": session.created_at,
                    "last_activity": session.last_activity,
                    "tmux_session": session.tmux_session
                }
                for session in sessions
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/squad/sessions")
async def create_squad_session(request: Request):
    """Create a new claude-squad session."""
    try:
        body = await request.json()
        project_path = body.get("project_path")
        agent_type = body.get("agent_type", "claude-code")
        session_name = body.get("session_name")
        auto_accept = body.get("auto_accept", False)
        
        if not project_path:
            raise HTTPException(status_code=400, detail="Project path is required")
        
        # Validate agent type
        try:
            agent_enum = SquadAgentType(agent_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid agent type: {agent_type}")
        
        session = await squad_bridge.create_session(
            project_path=project_path,
            agent_type=agent_enum,
            session_name=session_name,
            auto_accept=auto_accept
        )
        
        return {
            "success": True,
            "session": {
                "id": session.session_id,
                "agent_type": session.agent_type.value,
                "project_path": session.project_path,
                "branch_name": session.branch_name,
                "status": session.status,
                "created_at": session.created_at,
                "tmux_session": session.tmux_session
            }
        }
        
    except Exception as e:
        if "SquadInstallationError" in str(type(e)):
            raise HTTPException(status_code=503, detail="Claude-squad not installed")
        elif "SquadSessionError" in str(type(e)):
            raise HTTPException(status_code=400, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/squad/sessions/{session_id}/execute")
async def execute_squad_command(session_id: str, request: Request):
    """Execute a command in a squad session."""
    try:
        body = await request.json()
        command = body.get("command")
        timeout = body.get("timeout", 300)
        
        if not command:
            raise HTTPException(status_code=400, detail="Command is required")
        
        result = await squad_bridge.execute_command(
            session_id=session_id,
            command=command,
            timeout=timeout
        )
        
        return result
        
    except Exception as e:
        if "SquadSessionError" in str(type(e)):
            raise HTTPException(status_code=404, detail=str(e))
        else:
            raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/squad/sessions/{session_id}")
async def terminate_squad_session(session_id: str):
    """Terminate a claude-squad session."""
    try:
        success = await squad_bridge.terminate_session(session_id)
        if success:
            return {"success": True, "message": f"Session {session_id} terminated"}
        else:
            raise HTTPException(status_code=400, detail="Failed to terminate session")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/squad/sessions/{session_id}/status")
async def get_squad_session_status(session_id: str):
    """Get detailed status of a squad session."""
    try:
        status = await squad_bridge.get_session_status(session_id)
        if status:
            return status
        else:
            raise HTTPException(status_code=404, detail="Session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_path:path}/git/init")
async def initialize_git(project_path: str):
    """Initialize Git repository for project."""
    try:
        projects_root = Path("projects").resolve()
        full_path = (projects_root / project_path).resolve()
        
        # Security check
        try:
            full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Initialize git repository
        import subprocess
        result = subprocess.run(
            ["git", "init"],
            cwd=full_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Git init failed: {result.stderr}")
        
        # Create initial commit
        subprocess.run(["git", "add", "."], cwd=full_path, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=full_path,
            capture_output=True
        )
        
        # Update project metadata
        await update_project_metadata(full_path, {
            "git": {"initialized": True, "branch": "main"},
            "modified": datetime.now().isoformat()
        })
        
        return {"success": True, "message": "Git repository initialized"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/projects/{project_path:path}/git/push")
async def push_to_git(project_path: str, request: Request):
    """Push project to Git repository."""
    try:
        body = await request.json()
        remote_url = body.get("remote_url")
        branch = body.get("branch", "main")
        
        if not remote_url:
            raise HTTPException(status_code=400, detail="Remote URL required")
        
        projects_root = Path("projects").resolve()
        full_path = (projects_root / project_path).resolve()
        
        # Security check
        try:
            full_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="Project not found")
        
        # Add remote and push
        import subprocess
        
        # Add remote origin
        subprocess.run(
            ["git", "remote", "add", "origin", remote_url],
            cwd=full_path,
            capture_output=True
        )
        
        # Push to remote
        result = subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=full_path,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"Git push failed: {result.stderr}")
        
        # Update project metadata
        await update_project_metadata(full_path, {
            "git": {
                "initialized": True,
                "remote": remote_url,
                "branch": branch
            },
            "modified": datetime.now().isoformat()
        })
        
        return {"success": True, "message": "Pushed to repository successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def analyze_project_folder(project_path: Path) -> Dict[str, Any]:
    """Analyze a project folder and return metadata."""
    try:
        # Try to load existing metadata
        metadata_file = project_path / ".meistrocraft" / "project.json"
        metadata = {}
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            except json.JSONDecodeError:
                pass
        
        # Get basic info
        stat = project_path.stat()
        
        # Detect technologies
        technologies = await detect_project_technologies(project_path)
        
        # Get Git info
        git_info = await get_git_info(project_path)
        
        # Calculate stats
        stats = await calculate_project_stats(project_path)
        
        return {
            "id": generate_project_id(str(project_path)),
            "name": metadata.get("name", project_path.name),
            "description": metadata.get("description", "No description available"),
            "path": str(project_path.relative_to(Path("projects").resolve())),
            "status": metadata.get("status", "active"),
            "type": metadata.get("type", detect_project_type(project_path)),
            "created": metadata.get("created", datetime.fromtimestamp(stat.st_ctime).isoformat()),
            "modified": metadata.get("modified", datetime.fromtimestamp(stat.st_mtime).isoformat()),
            "technologies": technologies,
            "git": git_info,
            "stats": stats,
            "metadata": metadata
        }
        
    except Exception as e:
        print(f"Error analyzing project {project_path}: {e}")
        return {
            "id": generate_project_id(str(project_path)),
            "name": project_path.name,
            "description": "Error loading project",
            "path": str(project_path.relative_to(Path("projects").resolve())),
            "status": "unknown",
            "type": "unknown",
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "technologies": [],
            "git": {"initialized": False},
            "stats": {"files": 0, "size": 0},
            "metadata": {}
        }

async def detect_project_technologies(project_path: Path) -> List[str]:
    """Detect technologies used in a project."""
    technologies = []
    
    # Check for common config files
    config_files = {
        "package.json": "Node.js",
        "requirements.txt": "Python",
        "Pipfile": "Python",
        "pyproject.toml": "Python",
        "Gemfile": "Ruby",
        "composer.json": "PHP",
        "pom.xml": "Java",
        "build.gradle": "Java",
        "Cargo.toml": "Rust",
        "go.mod": "Go",
        "pubspec.yaml": "Dart/Flutter",
        "CMakeLists.txt": "C/C++",
        "Makefile": "C/C++",
        "*.csproj": "C#",
        "*.sln": "C#"
    }
    
    for config_file, tech in config_files.items():
        if "*" in config_file:
            # Handle wildcard patterns
            pattern = config_file.replace("*", "")
            for file_path in project_path.rglob(f"*{pattern}"):
                if file_path.is_file():
                    technologies.append(tech)
                    break
        else:
            if (project_path / config_file).exists():
                technologies.append(tech)
    
    # Check for common framework indicators
    if (project_path / "src" / "App.js").exists() or (project_path / "src" / "App.tsx").exists():
        technologies.append("React")
    if (project_path / "src" / "main.js").exists() and (project_path / "package.json").exists():
        technologies.append("Vue.js")
    if (project_path / "angular.json").exists():
        technologies.append("Angular")
    if (project_path / "django" / "settings.py").exists() or any(project_path.rglob("settings.py")):
        technologies.append("Django")
    if (project_path / "app.py").exists() or (project_path / "main.py").exists():
        technologies.append("Flask/FastAPI")
    
    return list(set(technologies))  # Remove duplicates

def detect_project_type(project_path: Path) -> str:
    """Detect the type of project."""
    if (project_path / "package.json").exists():
        # Check package.json for more specific type
        try:
            with open(project_path / "package.json", 'r') as f:
                package_data = json.load(f)
                if "react" in str(package_data.get("dependencies", {})):
                    return "web-app"
                if "express" in str(package_data.get("dependencies", {})):
                    return "api-service"
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            pass
        return "web-app"
    
    if (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists():
        if any(project_path.rglob("*.ipynb")):
            return "data-analysis"
        if (project_path / "app.py").exists() or (project_path / "main.py").exists():
            return "api-service"
        return "automation-script"
    
    if (project_path / "Cargo.toml").exists():
        return "library-tool"
    
    if (project_path / "pom.xml").exists() or (project_path / "build.gradle").exists():
        return "desktop-app"
    
    return "other"

async def get_git_info(project_path: Path) -> Dict[str, Any]:
    """Get Git repository information."""
    git_dir = project_path / ".git"
    
    if not git_dir.exists():
        return {"initialized": False}
    
    try:
        import subprocess
        
        # Get current branch
        branch_result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True
        )
        branch = branch_result.stdout.strip() if branch_result.returncode == 0 else "main"
        
        # Get remote URL
        remote_result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=project_path,
            capture_output=True,
            text=True
        )
        remote = remote_result.stdout.strip() if remote_result.returncode == 0 else None
        
        # Get commit count
        count_result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=project_path,
            capture_output=True,
            text=True
        )
        commits = int(count_result.stdout.strip()) if count_result.returncode == 0 else 0
        
        return {
            "initialized": True,
            "branch": branch,
            "remote": remote,
            "commits": commits
        }
        
    except Exception:
        return {"initialized": True}

async def calculate_project_stats(project_path: Path) -> Dict[str, Any]:
    """Calculate project statistics."""
    try:
        file_count = 0
        total_size = 0
        
        for file_path in project_path.rglob("*"):
            if file_path.is_file():
                file_count += 1
                try:
                    total_size += file_path.stat().st_size
                except (OSError, PermissionError):
                    pass
        
        return {
            "files": file_count,
            "size": total_size
        }
        
    except Exception:
        return {"files": 0, "size": 0}

async def update_project_metadata(project_path: Path, updates: Dict[str, Any]):
    """Update project metadata file."""
    try:
        metadata_dir = project_path / ".meistrocraft"
        metadata_dir.mkdir(exist_ok=True)
        
        metadata_file = metadata_dir / "project.json"
        
        # Load existing metadata
        metadata = {}
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
            except json.JSONDecodeError:
                pass
        
        # Apply updates
        metadata.update(updates)
        
        # Save metadata
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
            
    except Exception as e:
        print(f"Failed to update project metadata: {e}")

async def get_detailed_project_info(project_path: Path) -> Dict[str, Any]:
    """Get detailed project information."""
    try:
        # Get basic project info
        project_data = await analyze_project_folder(project_path)
        
        # Add additional details
        recent_files = []
        for file_path in project_path.rglob("*"):
            if file_path.is_file() and not file_path.name.startswith('.'):
                try:
                    stat = file_path.stat()
                    recent_files.append({
                        "name": file_path.name,
                        "path": str(file_path.relative_to(project_path)),
                        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                        "size": stat.st_size
                    })
                except (OSError, PermissionError):
                    pass
        
        # Sort by modified date and take the 10 most recent
        recent_files.sort(key=lambda x: x["modified"], reverse=True)
        project_data["recent_files"] = recent_files[:10]
        
        return project_data
        
    except Exception as e:
        print(f"Error getting detailed project info: {e}")
        return {}

def generate_project_id(path: str) -> str:
    """Generate a unique ID for a project path."""
    import base64
    return base64.b64encode(path.encode()).decode().replace('=', '').replace('/', '_').replace('+', '-')

@app.get("/api/files")
async def list_files(path: str = "projects"):
    """List files and directories in the specified path (restricted to projects folder)."""
    try:
        # Ensure we only serve files from the projects directory
        projects_root = Path("projects").resolve()
        
        # If path is "." or empty, default to projects folder
        if path in [".", "", "projects"]:
            file_path = projects_root
        else:
            # Construct path relative to projects folder
            requested_path = Path(path)
            if requested_path.is_absolute():
                # Convert absolute path to relative within projects
                try:
                    relative_path = requested_path.relative_to(projects_root)
                    file_path = projects_root / relative_path
                except ValueError:
                    # Path is outside projects directory, redirect to projects root
                    file_path = projects_root
            else:
                # Relative path - join with projects root
                file_path = (projects_root / path).resolve()
        
        # Security check: ensure the resolved path is still within projects
        try:
            file_path.relative_to(projects_root)
        except ValueError:
            # Path traversal attempt detected, redirect to projects root
            file_path = projects_root
        
        # Create projects directory if it doesn't exist
        if not file_path.exists() and file_path == projects_root:
            file_path.mkdir(parents=True, exist_ok=True)
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Path not found")
        
        if not file_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        items = []
        for item in file_path.iterdir():
            try:
                stat = item.stat()
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": stat.st_size if item.is_file() else None,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "extension": item.suffix.lower() if item.is_file() else None
                })
            except (OSError, PermissionError):
                # Skip files that can't be accessed
                continue
        
        # Sort: directories first, then files alphabetically
        items.sort(key=lambda x: (x["type"] != "directory", x["name"].lower()))
        
        return {
            "path": str(file_path),
            "items": items
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/files/content")
async def get_file_content(path: str):
    """Get the content of a specific file (restricted to projects folder)."""
    try:
        # Ensure we only serve files from the projects directory
        projects_root = Path("projects").resolve()
        
        # Construct secure file path
        requested_path = Path(path)
        if requested_path.is_absolute():
            # Convert absolute path to relative within projects
            try:
                relative_path = requested_path.relative_to(projects_root)
                file_path = projects_root / relative_path
            except ValueError:
                raise HTTPException(status_code=403, detail="Access denied: Path outside projects directory")
        else:
            # Relative path - join with projects root
            file_path = (projects_root / path).resolve()
        
        # Security check: ensure the resolved path is still within projects
        try:
            file_path.relative_to(projects_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Access denied: Path traversal detected")
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        if not file_path.is_file():
            raise HTTPException(status_code=400, detail="Path is not a file")
        
        # Check file size (limit to 10MB for safety)
        if file_path.stat().st_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="File too large")
        
        # Try to read as text
        try:
            content = file_path.read_text(encoding='utf-8')
            return {
                "path": str(file_path),
                "content": content,
                "encoding": "utf-8",
                "size": len(content)
            }
        except UnicodeDecodeError:
            # File is binary
            raise HTTPException(status_code=415, detail="Binary file not supported for text display")
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/files/save")
async def save_file_content(request: Request):
    """Save content to a file."""
    try:
        body = await request.json()
        file_path = Path(body.get("path", "")).resolve()
        content = body.get("content", "")
        
        if not file_path.parent.exists():
            raise HTTPException(status_code=400, detail="Parent directory does not exist")
        
        # Write file
        file_path.write_text(content, encoding='utf-8')
        
        return {
            "path": str(file_path),
            "status": "saved",
            "size": len(content),
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time communication."""
    await websocket.accept()
    await session_manager.register_websocket(session_id, websocket)
    
    try:
        # Send connection confirmation
        await websocket.send_text(json.dumps({
            "type": "connection",
            "status": "connected",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }))
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Handle different message types
            await handle_websocket_message(websocket, session_id, message)
            
    except WebSocketDisconnect:
        await session_manager.unregister_websocket(session_id)
        print(f"WebSocket disconnected for session: {session_id}")
    except Exception as e:
        print(f"WebSocket error for session {session_id}: {e}")
        await session_manager.unregister_websocket(session_id)

async def handle_websocket_message(websocket: WebSocket, session_id: str, message: Dict[str, Any]):
    """Handle incoming WebSocket messages."""
    message_type = message.get("type")
    
    if message_type == "chat":
        # Handle chat messages (AI interaction)
        content = message.get("content", "")
        context = message.get("context", None)
        
        try:
            # Initialize token tracking variables
            total_tokens = 0
            cost = 0.0
            
            # Ensure we have a MeistroCraft session
            meistrocraft_session_id = await session_manager.create_session(session_id)
            
            # Send start message
            await websocket.send_text(json.dumps({
                "type": "chat_response_start",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat()
            }))
            
            # Get session data to determine project folder
            session_data = session_manager.session_manager.load_session(meistrocraft_session_id)
            project_folder = session_data.get("project_folder") if session_data else None
            
            # Enhance content with file context if available
            enhanced_content = content
            if context and context.get("is_file") and context.get("file_path"):
                file_info = f"\n\nCurrent file context:\n"
                file_info += f"- File: {context.get('file_path')}\n"
                file_info += f"- Language: {context.get('language')}\n"
                if context.get("content_preview"):
                    file_info += f"- Current content:\n```{context.get('language', '')}\n{context.get('content_preview')}\n```\n"
                enhanced_content = content + file_info
            
            # Generate task with GPT-4
            task = generate_task_with_gpt4(
                enhanced_content, 
                session_manager.config, 
                project_folder,
                session_manager.token_tracker,
                meistrocraft_session_id
            )
            
            if not task:
                # Fallback response if GPT-4 fails
                await websocket.send_text(json.dumps({
                    "type": "chat_response_chunk", 
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "chunk": "I apologize, but I'm having trouble connecting to the AI service right now. Please check your API configuration and try again."
                }))
            else:
                # Send task info
                await websocket.send_text(json.dumps({
                    "type": "chat_response_chunk", 
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "chunk": f"🎯 Task: {task['action']} - {task['instruction'][:100]}{'...' if len(task['instruction']) > 100 else ''}\n\n"
                }))
                
                # Execute with Claude
                result = run_claude_task(
                    task, 
                    session_manager.config, 
                    meistrocraft_session_id, 
                    session_manager.session_manager, 
                    project_folder,
                    session_manager.token_tracker
                )
                
                if result.get("success"):
                    # Stream the response
                    response_text = result.get("result", "Task completed successfully!")
                    words = response_text.split()
                    chunk_size = 8
                    
                    for i in range(0, len(words), chunk_size):
                        chunk = ' '.join(words[i:i+chunk_size])
                        await websocket.send_text(json.dumps({
                            "type": "chat_response_chunk", 
                            "session_id": session_id,
                            "timestamp": datetime.now().isoformat(),
                            "chunk": chunk + " "
                        }))
                        await asyncio.sleep(0.05)  # Faster streaming
                    
                    # Save to session
                    session_manager.session_manager.add_task_to_session(meistrocraft_session_id, task, result)
                    
                    # Get token usage from result
                    usage = result.get("response", {}).get("usage", {})
                    total_tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
                    cost = result.get("response", {}).get("total_cost_usd", 0.0)
                    
                else:
                    await websocket.send_text(json.dumps({
                        "type": "chat_response_chunk", 
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "chunk": f"❌ Task failed: {result.get('error', 'Unknown error')}"
                    }))
                    total_tokens = 0
                    cost = 0.0
            
            # Send completion message
            await websocket.send_text(json.dumps({
                "type": "chat_response_complete",
                "session_id": session_id, 
                "timestamp": datetime.now().isoformat(),
                "total_tokens": total_tokens,
                "cost": cost
            }))
            
        except Exception as e:
            print(f"Chat error: {e}")
            await websocket.send_text(json.dumps({
                "type": "chat_response_chunk", 
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "chunk": f"❌ Error: {str(e)}"
            }))
            await websocket.send_text(json.dumps({
                "type": "chat_response_complete",
                "session_id": session_id, 
                "timestamp": datetime.now().isoformat(),
                "total_tokens": 0,
                "cost": 0.0
            }))
        
    elif message_type == "command":
        # Handle terminal commands
        command = message.get("command", "")
        
        try:
            import subprocess
            import shlex
            
            # Get session data to determine project folder
            session_data = session_manager.session_manager.load_session(meistrocraft_session_id)
            project_folder = session_data.get("project_folder") if session_data else None
            
            # Determine working directory
            if project_folder and os.path.exists(project_folder):
                working_dir = project_folder
            else:
                # If no project folder or empty projects, use projects directory with template
                projects_dir = os.path.join(os.getcwd(), "projects")
                if not os.path.exists(projects_dir):
                    os.makedirs(projects_dir)
                
                # Create template CLAUDE.md if it doesn't exist
                template_claude_path = os.path.join(projects_dir, "CLAUDE.md")
                if not os.path.exists(template_claude_path):
                    template_content = """# Project Instructions

This is a template CLAUDE.md file for your project.

## Overview
Add your project description here.

## Setup Instructions
Add setup instructions here.

## Development Guidelines
Add development guidelines here.
"""
                    with open(template_claude_path, 'w') as f:
                        f.write(template_content)
                
                working_dir = projects_dir
            
            # Execute command safely
            result = subprocess.run(
                shlex.split(command), 
                capture_output=True, 
                text=True, 
                timeout=30,  # 30 second timeout
                cwd=working_dir
            )
            
            output = f"$ {command}\n"
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += result.stderr
            
            response = {
                "type": "command_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "output": output,
                "exit_code": result.returncode
            }
        
        except subprocess.TimeoutExpired:
            response = {
                "type": "command_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "output": f"$ {command}\nError: Command timed out after 30 seconds",
                "exit_code": 124
            }
        except Exception as e:
            response = {
                "type": "command_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "output": f"$ {command}\nError: {str(e)}",
                "exit_code": 1
            }
        
        await websocket.send_text(json.dumps(response))
        
    elif message_type == "file_operation":
        # Handle file operations (read, write, delete)
        operation = message.get("operation")
        file_path = message.get("path", "")
        
        try:
            if operation == "read":
                # Read file content
                path_obj = Path(file_path).resolve()
                if path_obj.exists() and path_obj.is_file():
                    content = path_obj.read_text(encoding='utf-8')
                    response = {
                        "type": "file_response",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "operation": operation,
                        "path": file_path,
                        "status": "success",
                        "data": content
                    }
                else:
                    response = {
                        "type": "file_response",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "operation": operation,
                        "path": file_path,
                        "status": "error",
                        "error": "File not found or not accessible"
                    }
            elif operation == "list":
                # List directory contents
                path_obj = Path(file_path or ".").resolve()
                if path_obj.exists() and path_obj.is_dir():
                    items = []
                    for item in path_obj.iterdir():
                        try:
                            items.append({
                                "name": item.name,
                                "type": "directory" if item.is_dir() else "file",
                                "path": str(item)
                            })
                        except (OSError, PermissionError):
                            continue
                    
                    response = {
                        "type": "file_response",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "operation": operation,
                        "path": file_path,
                        "status": "success",
                        "data": items
                    }
                else:
                    response = {
                        "type": "file_response",
                        "session_id": session_id,
                        "timestamp": datetime.now().isoformat(),
                        "operation": operation,
                        "path": file_path,
                        "status": "error",
                        "error": "Directory not found"
                    }
            else:
                response = {
                    "type": "file_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "operation": operation,
                    "path": file_path,
                    "status": "error",
                    "error": f"Unsupported operation: {operation}"
                }
        except Exception as e:
            response = {
                "type": "file_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "path": file_path,
                "status": "error",
                "error": str(e)
            }
        
        await websocket.send_text(json.dumps(response))
        
    elif message_type == "get_tasks":
        # Get task queue status
        try:
            # Get real task data from session
            session_data = session_manager.session_manager.load_session(meistrocraft_session_id)
            tasks = []
            
            if session_data and "task_history" in session_data:
                # Convert task history to current task format
                for i, task_entry in enumerate(session_data["task_history"][-3:]):  # Show last 3 tasks
                    task_data = task_entry.get("task", {})
                    result_data = task_entry.get("result", {})
                    
                    status = "completed" if task_entry.get("success", False) else "failed"
                    
                    tasks.append({
                        "id": str(i + 1),
                        "name": task_data.get("instruction", "Unknown task")[:50] + "...",
                        "status": status,
                        "completed_at": task_entry.get("timestamp", datetime.now().isoformat())
                    })
            
            # If no tasks, show empty state
            if not tasks:
                tasks = []
            
            response = {
                "type": "task_queue_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "tasks": tasks
            }
        except Exception as e:
            response = {
                "type": "error",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "error": f"Failed to get tasks: {str(e)}"
            }
        
        await websocket.send_text(json.dumps(response))
        
    elif message_type == "squad_command":
        # Handle claude-squad commands via WebSocket
        operation = message.get("operation")
        
        try:
            if operation == "status":
                # Get squad installation status
                status = await squad_bridge.check_installation()
                response = {
                    "type": "squad_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "operation": operation,
                    "data": status
                }
            
            elif operation == "list_sessions":
                # List active squad sessions
                sessions = await squad_bridge.list_sessions()
                response = {
                    "type": "squad_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "operation": operation,
                    "data": {
                        "sessions": [
                            {
                                "id": session.session_id,
                                "agent_type": session.agent_type.value,
                                "project_path": session.project_path,
                                "status": session.status
                            }
                            for session in sessions
                        ]
                    }
                }
            
            elif operation == "create_session":
                # Create new squad session
                project_path = message.get("project_path")
                agent_type = message.get("agent_type", "claude-code")
                
                if not project_path:
                    raise ValueError("Project path is required")
                
                try:
                    agent_enum = SquadAgentType(agent_type)
                except ValueError:
                    raise ValueError(f"Invalid agent type: {agent_type}")
                
                session = await squad_bridge.create_session(
                    project_path=project_path,
                    agent_type=agent_enum
                )
                
                response = {
                    "type": "squad_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "operation": operation,
                    "data": {
                        "success": True,
                        "session": {
                            "id": session.session_id,
                            "agent_type": session.agent_type.value,
                            "project_path": session.project_path,
                            "status": session.status
                        }
                    }
                }
            
            elif operation == "execute":
                # Execute command in squad session
                squad_session_id = message.get("squad_session_id")
                command = message.get("command")
                
                if not squad_session_id or not command:
                    raise ValueError("Squad session ID and command are required")
                
                # Send start message
                await websocket.send_text(json.dumps({
                    "type": "squad_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "operation": "execute_start",
                    "data": {
                        "squad_session_id": squad_session_id,
                        "command": command
                    }
                }))
                
                result = await squad_bridge.execute_command(
                    session_id=squad_session_id,
                    command=command
                )
                
                response = {
                    "type": "squad_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "operation": "execute_complete",
                    "data": {
                        "squad_session_id": squad_session_id,
                        "result": result
                    }
                }
            
            else:
                response = {
                    "type": "squad_response",
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "operation": operation,
                    "data": {"error": f"Unknown squad operation: {operation}"}
                }
        
        except Exception as e:
            response = {
                "type": "squad_response",
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "data": {"error": str(e)}
            }
        
        await websocket.send_text(json.dumps(response))
        
    else:
        # Unknown message type
        response = {
            "type": "error",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "error": f"Unknown message type: {message_type}"
        }
        await websocket.send_text(json.dumps(response))

def main():
    """Main entry point for the web server."""
    print("🌐 Starting MeistroCraft Web IDE...")
    print("📖 Open your browser to: http://localhost:8000")
    print("🔧 API docs available at: http://localhost:8000/docs")
    print("⏹️  Press Ctrl+C to stop")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        reload=False  # Disable reload for stability with AI backend
    )

if __name__ == "__main__":
    main()