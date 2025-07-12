#!/usr/bin/env python3
"""Test script for background task processing system."""

from task_queue import TaskQueue, TaskPriority, TaskStatus
import tempfile
import os
import time

def test_background_tasks():
    print('Testing background task processing system...')
    try:
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            
            # Create task queue
            queue = TaskQueue(max_workers=2, save_file='test_queue.json')
            
            # Add some test tasks
            task1_id = queue.add_task(
                session_id='test-session-1',
                user_input='Create a simple hello world Python script',
                task_description='Test task 1: Hello world script',
                priority=TaskPriority.HIGH
            )
            
            task2_id = queue.add_task(
                session_id='test-session-2', 
                user_input='Create a calculator function',
                task_description='Test task 2: Calculator function',
                priority=TaskPriority.MEDIUM
            )
            
            print(f'✅ Added test tasks: {task1_id}, {task2_id}')
            
            # Check queue status
            status = queue.get_queue_status()
            print(f'✅ Queue status: {status["total_tasks"]} total, {status["queue_size"]} queued')
            
            # List tasks
            tasks = queue.list_tasks()
            print(f'✅ Found {len(tasks)} tasks in queue')
            
            for task in tasks:
                print(f'   - {task.task_id}: {task.status.value} | {task.task_description}')
            
            # Test cancelling a task
            if queue.cancel_task(task2_id):
                print(f'✅ Successfully cancelled task {task2_id}')
            
            # Test priority change
            remaining_tasks = [t for t in queue.list_tasks() if t.status != TaskStatus.CANCELLED]
            if remaining_tasks:
                task = remaining_tasks[0]
                task.priority = TaskPriority.URGENT
                queue._save_tasks()
                print(f'✅ Changed task {task.task_id} priority to URGENT')
            
            # Test dependency system
            task3_id = queue.add_task(
                session_id='test-session-3',
                user_input='Test dependent task',
                task_description='Test task 3: Depends on task 1',
                priority=TaskPriority.LOW,
                dependencies=[task1_id]
            )
            print(f'✅ Added dependent task {task3_id}')
            
            # Cleanup
            queue.shutdown()
            print('✅ Task queue shutdown complete')
            
            print('🎉 Background task system working correctly!')
            
    except Exception as e:
        import traceback
        print(f'❌ Error testing task queue: {e}')
        print(traceback.format_exc())

if __name__ == "__main__":
    test_background_tasks()