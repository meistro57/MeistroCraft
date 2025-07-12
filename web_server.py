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

app = FastAPI(
    title="MeistroCraft IDE",
    description="Browser-based IDE interface for MeistroCraft AI Development Orchestrator",
    version="2.0.0"
)

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
        self.sessions: Dict[str, InteractiveSession] = {}
        self.websockets: Dict[str, WebSocket] = {}
        self.task_queue = get_task_queue()
        
    async def create_session(self, session_id: str, config: Dict[str, Any]) -> InteractiveSession:
        """Create a new interactive session for web interface."""
        if session_id in self.sessions:
            return self.sessions[session_id]
            
        # Initialize session components (will be implemented in phase1-4)
        session = None  # Placeholder for InteractiveSession integration
        self.sessions[session_id] = session
        return session
        
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
        # Mock sessions data - in real implementation would use session_manager
        sessions = [
            {
                "id": "session-1",
                "name": "Python API Project",
                "created_at": (datetime.now() - timedelta(hours=2)).isoformat(),
                "last_accessed": (datetime.now() - timedelta(hours=2)).isoformat(),
                "task_count": 15,
                "status": "saved"
            },
            {
                "id": "session-2", 
                "name": "React Dashboard",
                "created_at": (datetime.now() - timedelta(days=1)).isoformat(),
                "last_accessed": (datetime.now() - timedelta(days=1)).isoformat(),
                "task_count": 8,
                "status": "saved"
            }
        ]
        
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

@app.get("/api/files")
async def list_files(path: str = "."):
    """List files and directories in the specified path."""
    try:
        file_path = Path(path).resolve()
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
    """Get the content of a specific file."""
    try:
        file_path = Path(path).resolve()
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
        
        # Simulate streaming AI response
        await websocket.send_text(json.dumps({
            "type": "chat_response_start",
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }))
        
        # Simulate streamed chunks
        ai_response = f"I understand you said: '{content}'. This is a placeholder AI response that would normally be generated by the actual AI model. In the real implementation, this would integrate with the existing InteractiveSession class and use OpenAI/Anthropic APIs to generate intelligent responses."
        
        words = ai_response.split()
        chunk_size = 5
        
        for i in range(0, len(words), chunk_size):
            chunk = ' '.join(words[i:i+chunk_size])
            await websocket.send_text(json.dumps({
                "type": "chat_response_chunk", 
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "chunk": chunk + " "
            }))
            # Small delay to simulate streaming
            await asyncio.sleep(0.1)
        
        # Send completion message
        await websocket.send_text(json.dumps({
            "type": "chat_response_complete",
            "session_id": session_id, 
            "timestamp": datetime.now().isoformat(),
            "total_tokens": len(words),
            "cost": 0.001  # Placeholder cost
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

if __name__ == "__main__":
    # Development server
    uvicorn.run(
        "web_server:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )