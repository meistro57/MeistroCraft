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
from main import SessionManager, load_config, setup_environment, generate_task_with_gpt4, run_claude_task

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
        except:
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
            
            # Execute command safely
            result = subprocess.run(
                shlex.split(command), 
                capture_output=True, 
                text=True, 
                timeout=30,  # 30 second timeout
                cwd=os.getcwd()
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
            # Mock task data for demo - in real implementation would use task_queue
            tasks = [
                {
                    "id": "1",
                    "name": "Install dependencies",
                    "status": "completed",
                    "completed_at": (datetime.now() - timedelta(minutes=2)).isoformat()
                },
                {
                    "id": "2", 
                    "name": "Running tests",
                    "status": "running",
                    "started_at": datetime.now().isoformat()
                },
                {
                    "id": "3",
                    "name": "Build project", 
                    "status": "pending"
                }
            ]
            
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