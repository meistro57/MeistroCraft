#!/usr/bin/env python3
"""
Background Task Queue System for MeistroCraft
Enables non-blocking task execution, queuing, and parallel processing.
"""

import asyncio
import threading
import time
import uuid
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import queue
import concurrent.futures
from collections import defaultdict


class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


@dataclass
class TaskInfo:
    """Information about a background task."""
    task_id: str
    session_id: str
    workspace_id: Optional[str]
    user_input: str
    task_description: str
    priority: TaskPriority
    status: TaskStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    progress: float = 0.0  # 0.0 to 1.0
    progress_message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    dependencies: List[str] = None  # Task IDs this task depends on
    auto_accept: bool = False
    auto_accept_reason: Optional[str] = None
    estimated_duration: Optional[int] = None  # seconds
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []


class TaskQueue:
    """Manages background task execution with priority and dependency handling."""
    
    def __init__(self, max_workers: int = 3, save_file: str = "task_queue.json"):
        self.max_workers = max_workers
        self.save_file = Path(save_file)
        
        # Task storage
        self.tasks: Dict[str, TaskInfo] = {}
        self.task_queue = queue.PriorityQueue()
        self.running_tasks: Dict[str, threading.Thread] = {}
        self.completed_tasks: List[str] = []  # Recently completed task IDs
        
        # Thread management
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
        self.shutdown_event = threading.Event()
        self.queue_processor = None
        
        # Callbacks
        self.progress_callbacks: List[Callable[[TaskInfo], None]] = []
        self.completion_callbacks: List[Callable[[TaskInfo], None]] = []
        
        # Load existing tasks
        self._load_tasks()
        
        # Start background processor
        self._start_queue_processor()
    
    def _load_tasks(self) -> None:
        """Load tasks from persistent storage."""
        if self.save_file.exists():
            try:
                with open(self.save_file, 'r') as f:
                    data = json.load(f)
                
                for task_id, task_data in data.items():
                    task = TaskInfo(
                        task_id=task_data['task_id'],
                        session_id=task_data['session_id'],
                        workspace_id=task_data.get('workspace_id'),
                        user_input=task_data['user_input'],
                        task_description=task_data['task_description'],
                        priority=TaskPriority(task_data['priority']),
                        status=TaskStatus(task_data['status']),
                        created_at=task_data['created_at'],
                        started_at=task_data.get('started_at'),
                        completed_at=task_data.get('completed_at'),
                        progress=task_data.get('progress', 0.0),
                        progress_message=task_data.get('progress_message', ''),
                        result=task_data.get('result'),
                        error=task_data.get('error'),
                        dependencies=task_data.get('dependencies', []),
                        auto_accept=task_data.get('auto_accept', False),
                        estimated_duration=task_data.get('estimated_duration')
                    )
                    self.tasks[task_id] = task
                    
                    # Re-queue pending and queued tasks
                    if task.status in [TaskStatus.PENDING, TaskStatus.QUEUED]:
                        self._queue_task(task)
                        
            except Exception as e:
                print(f"Warning: Failed to load task queue: {e}")
    
    def _save_tasks(self) -> None:
        """Save tasks to persistent storage."""
        try:
            data = {}
            for task_id, task in self.tasks.items():
                data[task_id] = {
                    'task_id': task.task_id,
                    'session_id': task.session_id,
                    'workspace_id': task.workspace_id,
                    'user_input': task.user_input,
                    'task_description': task.task_description,
                    'priority': task.priority.value,
                    'status': task.status.value,
                    'created_at': task.created_at,
                    'started_at': task.started_at,
                    'completed_at': task.completed_at,
                    'progress': task.progress,
                    'progress_message': task.progress_message,
                    'result': task.result,
                    'error': task.error,
                    'dependencies': task.dependencies,
                    'auto_accept': task.auto_accept,
                    'estimated_duration': task.estimated_duration
                }
            
            with open(self.save_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Failed to save task queue: {e}")
    
    def add_task(self, session_id: str, user_input: str, task_description: str,
                 priority: TaskPriority = TaskPriority.MEDIUM, workspace_id: Optional[str] = None,
                 auto_accept: Optional[bool] = None, dependencies: Optional[List[str]] = None,
                 estimated_duration: Optional[int] = None, task_data: Optional[Dict[str, Any]] = None) -> str:
        """Add a new task to the queue."""
        task_id = str(uuid.uuid4())[:8]  # Short ID for readability
        
        # Determine auto-accept if not explicitly set
        auto_accept_reason = None
        if auto_accept is None:
            try:
                from auto_accept import get_auto_accept_manager
                auto_accept_manager = get_auto_accept_manager()
                
                # Prepare task data for auto-accept decision
                task_data_for_check = task_data.copy() if task_data else {}
                task_data_for_check.update({
                    'session_id': session_id,
                    'workspace_id': workspace_id,
                    'user_input': user_input
                })
                
                auto_accept = auto_accept_manager.should_auto_accept(task_description, task_data_for_check)
                if auto_accept:
                    auto_accept_reason = auto_accept_manager.get_auto_accept_reason(task_description, task_data_for_check)
                    
            except Exception as e:
                print(f"Warning: Auto-accept check failed: {e}")
                auto_accept = False
        
        task = TaskInfo(
            task_id=task_id,
            session_id=session_id,
            workspace_id=workspace_id,
            user_input=user_input,
            task_description=task_description,
            priority=priority,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            dependencies=dependencies or [],
            auto_accept=auto_accept or False,
            auto_accept_reason=auto_accept_reason,
            estimated_duration=estimated_duration
        )
        
        self.tasks[task_id] = task
        
        # Check if dependencies are satisfied
        if self._dependencies_satisfied(task):
            self._queue_task(task)
        
        self._save_tasks()
        print(f"📋 Added task {task_id}: {task_description[:50]}...")
        return task_id
    
    def _dependencies_satisfied(self, task: TaskInfo) -> bool:
        """Check if all dependencies are completed."""
        for dep_id in task.dependencies:
            if dep_id not in self.tasks:
                return False
            if self.tasks[dep_id].status != TaskStatus.COMPLETED:
                return False
        return True
    
    def _queue_task(self, task: TaskInfo) -> None:
        """Add task to the execution queue."""
        task.status = TaskStatus.QUEUED
        # Priority queue uses tuples: (priority, timestamp, task_id)
        # Lower numbers = higher priority, so we negate the priority value
        priority_value = -task.priority.value
        timestamp = datetime.fromisoformat(task.created_at).timestamp()
        self.task_queue.put((priority_value, timestamp, task.task_id))
    
    def _start_queue_processor(self) -> None:
        """Start the background queue processor."""
        def process_queue():
            while not self.shutdown_event.is_set():
                try:
                    # Check for available worker slots
                    if len(self.running_tasks) >= self.max_workers:
                        time.sleep(0.1)
                        continue
                    
                    # Get next task from queue (with timeout to allow shutdown)
                    try:
                        priority, timestamp, task_id = self.task_queue.get(timeout=1.0)
                    except queue.Empty:
                        continue
                    
                    if task_id not in self.tasks:
                        continue
                    
                    task = self.tasks[task_id]
                    
                    # Double-check dependencies (they might have changed)
                    if not self._dependencies_satisfied(task):
                        # Re-queue the task for later
                        self.task_queue.put((priority, timestamp, task_id))
                        time.sleep(0.1)
                        continue
                    
                    # Execute the task
                    self._execute_task(task)
                    
                except Exception as e:
                    print(f"Error in queue processor: {e}")
                    time.sleep(1.0)
        
        self.queue_processor = threading.Thread(target=process_queue, daemon=True)
        self.queue_processor.start()
    
    def _execute_task(self, task: TaskInfo) -> None:
        """Execute a task in the background."""
        def run_task():
            try:
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                self._save_tasks()
                self._notify_progress_callbacks(task)
                
                print(f"🚀 Starting task {task.task_id}: {task.task_description}")
                
                # Import here to avoid circular imports
                from main import generate_task_with_gpt4, run_claude_task
                from main import create_project_summary, create_project_readme
                
                # Update progress
                task.progress = 0.1
                task.progress_message = "Generating task with GPT-4..."
                self._notify_progress_callbacks(task)
                
                # Load configuration (simplified for background execution);
                # if config file is missing or unloadable, proceed with empty config
                try:
                    from main import load_config
                    config = load_config()
                except BaseException as e:
                    print(f"Warning: Could not load config for background task: {e}")
                    config = {}
                
                # Get workspace path if available
                project_folder = None
                if task.workspace_id:
                    # Get workspace path from session manager
                    from main import SessionManager
                    from workspace_manager import WorkspaceManager
                    workspace_manager = WorkspaceManager()
                    project_folder = workspace_manager.get_session_workspace_path(task.session_id)
                
                # Generate task with GPT-4
                gpt_task = generate_task_with_gpt4(
                    task.user_input, config, project_folder, 
                    None, task.session_id  # No token tracker for background tasks for now
                )
                
                if not gpt_task:
                    raise Exception("Failed to generate task with GPT-4")
                
                task.progress = 0.4
                task.progress_message = f"Executing with Claude: {gpt_task['action']}"
                self._notify_progress_callbacks(task)
                
                # Execute with Claude
                result = run_claude_task(gpt_task, config, None, None, project_folder, None)
                
                task.progress = 0.8
                task.progress_message = "Processing results..."
                self._notify_progress_callbacks(task)
                
                if result.get('success'):
                    # Save results
                    if project_folder:
                        create_project_summary(project_folder, gpt_task, result)
                    
                    task.status = TaskStatus.COMPLETED
                    task.result = {
                        'gpt_task': gpt_task,
                        'claude_result': result,
                        'success': True
                    }
                    task.progress = 1.0
                    task.progress_message = "Task completed successfully"
                    
                    print(f"✅ Completed task {task.task_id}")
                    
                    # Check if any dependent tasks can now be queued
                    self._check_dependent_tasks(task.task_id)
                    
                else:
                    raise Exception(f"Claude execution failed: {result.get('error', 'Unknown error')}")
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                task.progress_message = f"Error: {str(e)}"
                print(f"❌ Task {task.task_id} failed: {e}")
            
            finally:
                task.completed_at = datetime.now().isoformat()
                self.completed_tasks.append(task.task_id)
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
                self._save_tasks()
                self._notify_completion_callbacks(task)
        
        # Start task execution in thread pool
        future = self.executor.submit(run_task)
        self.running_tasks[task.task_id] = future
    
    def _check_dependent_tasks(self, completed_task_id: str) -> None:
        """Check if any tasks can be queued now that a dependency is completed."""
        for task in self.tasks.values():
            if (task.status == TaskStatus.PENDING and 
                completed_task_id in task.dependencies and
                self._dependencies_satisfied(task)):
                self._queue_task(task)
                self._save_tasks()
    
    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """Get task by ID."""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status_filter: Optional[TaskStatus] = None, 
                   session_filter: Optional[str] = None, limit: int = 50) -> List[TaskInfo]:
        """List tasks with optional filters."""
        tasks = list(self.tasks.values())
        
        if status_filter:
            tasks = [t for t in tasks if t.status == status_filter]
        
        if session_filter:
            tasks = [t for t in tasks if t.session_id == session_filter]
        
        # Sort by creation time (newest first)
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a task."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        if task.status == TaskStatus.RUNNING:
            # Try to cancel running task
            if task_id in self.running_tasks:
                future = self.running_tasks[task_id]
                if future.cancel():
                    task.status = TaskStatus.CANCELLED
                    del self.running_tasks[task_id]
                    self._save_tasks()
                    return True
                else:
                    return False  # Task already started, can't cancel
        elif task.status in [TaskStatus.PENDING, TaskStatus.QUEUED]:
            task.status = TaskStatus.CANCELLED
            self._save_tasks()
            return True
        
        return False
    
    def pause_task(self, task_id: str) -> bool:
        """Pause a task (only works for queued tasks)."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status == TaskStatus.QUEUED:
            task.status = TaskStatus.PAUSED
            self._save_tasks()
            return True
        
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status == TaskStatus.PAUSED:
            if self._dependencies_satisfied(task):
                self._queue_task(task)
                self._save_tasks()
                return True
        
        return False
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get overall queue status."""
        status_counts = defaultdict(int)
        for task in self.tasks.values():
            status_counts[task.status.value] += 1
        
        return {
            'total_tasks': len(self.tasks),
            'running_tasks': len(self.running_tasks),
            'queue_size': self.task_queue.qsize(),
            'max_workers': self.max_workers,
            'status_counts': dict(status_counts),
            'recently_completed': len(self.completed_tasks)
        }
    
    def add_progress_callback(self, callback: Callable[[TaskInfo], None]) -> None:
        """Add a callback for progress updates."""
        self.progress_callbacks.append(callback)
    
    def add_completion_callback(self, callback: Callable[[TaskInfo], None]) -> None:
        """Add a callback for task completion."""
        self.completion_callbacks.append(callback)
    
    def _notify_progress_callbacks(self, task: TaskInfo) -> None:
        """Notify all progress callbacks."""
        for callback in self.progress_callbacks:
            try:
                callback(task)
            except Exception as e:
                print(f"Error in progress callback: {e}")
    
    def _notify_completion_callbacks(self, task: TaskInfo) -> None:
        """Notify all completion callbacks."""
        for callback in self.completion_callbacks:
            try:
                callback(task)
            except Exception as e:
                print(f"Error in completion callback: {e}")
    
    def cleanup_old_tasks(self, days: int = 7) -> int:
        """Clean up old completed/failed tasks."""
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff_date.isoformat()
        
        to_remove = []
        for task_id, task in self.tasks.items():
            if (task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED] and
                task.completed_at and task.completed_at < cutoff_str):
                to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.tasks[task_id]
        
        if to_remove:
            self._save_tasks()
            print(f"🧹 Cleaned up {len(to_remove)} old tasks")
        
        return len(to_remove)
    
    def shutdown(self) -> None:
        """Shutdown the task queue."""
        print("🛑 Shutting down task queue...")
        self.shutdown_event.set()
        
        # Cancel all running tasks
        for task_id, future in self.running_tasks.items():
            future.cancel()
            if task_id in self.tasks:
                self.tasks[task_id].status = TaskStatus.CANCELLED
        
        # Wait for queue processor to stop
        if self.queue_processor and self.queue_processor.is_alive():
            self.queue_processor.join(timeout=5.0)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        # Save final state
        self._save_tasks()
        print("✅ Task queue shutdown complete")


# Global task queue instance
_task_queue: Optional[TaskQueue] = None

def get_task_queue() -> TaskQueue:
    """Get or create the global task queue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue

def shutdown_task_queue() -> None:
    """Shutdown the global task queue."""
    global _task_queue
    if _task_queue is not None:
        _task_queue.shutdown()
        _task_queue = None
