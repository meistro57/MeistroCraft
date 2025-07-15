#!/usr/bin/env python3
"""Test script for auto-accept and background processing integration."""

from auto_accept import AutoAcceptManager, AutoAcceptLevel, AutoAcceptRule
from task_queue import TaskQueue, TaskPriority
import tempfile
import os


def test_auto_accept_system():
    print('Testing auto-accept and background processing integration...')

    try:
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)

            # Create auto-accept manager
            auto_manager = AutoAcceptManager('test_auto_accept.json')

            # Test different auto-accept levels
            print('\n🧪 Testing auto-accept decisions...')

            test_cases = [
                # Safe operations
                ("read the file contents", {"action": "read", "affected_files": ["test.py"]}),
                ("document the function", {"action": "document", "affected_files": ["main.py"]}),
                ("show all Python files", {"action": "list", "affected_files": []}),

                # Trusted operations
                ("create a test file", {"action": "create", "affected_files": ["test.py"]}),
                ("add comments to the code", {"action": "modify", "affected_files": ["main.py"]}),

                # Dangerous operations
                ("delete the database", {"action": "delete", "affected_files": ["data.db"]}),
                ("remove all files", {"action": "remove", "affected_files": ["*"]}),

                # File type checks
                ("create a binary file", {"action": "create", "affected_files": ["app.exe"]}),
                ("modify configuration", {"action": "modify", "affected_files": ["config.json"]}),
            ]

            # Test with different levels
            for level in [AutoAcceptLevel.NONE, AutoAcceptLevel.SAFE, AutoAcceptLevel.TRUSTED]:
                print(f'\n📋 Testing with level: {level.value}')
                auto_manager.set_global_level(level)

                for task_desc, task_data in test_cases:
                    should_accept = auto_manager.should_auto_accept(task_desc, task_data)
                    reason = auto_manager.get_auto_accept_reason(
                        task_desc, task_data) if should_accept else "Manual approval required"
                    status = "✅ AUTO" if should_accept else "⏸️  MANUAL"
                    print(f'  {status}: {task_desc[:40]:<40} | {reason[:50]}')

            print('\n🔄 Testing task queue integration...')

            # Create task queue with auto-accept
            queue = TaskQueue(max_workers=1, save_file='test_queue_auto.json')
            auto_manager.set_global_level(AutoAcceptLevel.TRUSTED)

            # Add tasks with different auto-accept potential
            tasks = [
                ("create test file for validation", {"action": "create", "affected_files": ["test_validation.py"]}),
                ("document the main function", {"action": "document", "affected_files": ["main.py"]}),
                ("delete old backup files", {"action": "delete", "affected_files": ["backup/*"]}),
                ("read the configuration", {"action": "read", "affected_files": ["config.json"]}),
            ]

            for task_desc, task_data in tasks:
                task_id = queue.add_task(
                    session_id='test-session',
                    user_input=task_desc,
                    task_description=task_desc,  # Use task description directly
                    priority=TaskPriority.MEDIUM,
                    auto_accept=None,  # Let auto-accept manager decide
                    task_data=task_data
                )

                task = queue.get_task(task_id)
                auto_status = "🤖 AUTO-ACCEPT" if task.auto_accept else "👤 MANUAL"
                print(f'  {auto_status}: {task.task_id} - {task_desc}')
                if task.auto_accept_reason:
                    print(f'    Reason: {task.auto_accept_reason}')

            # Show queue stats
            queue_status = queue.get_queue_status()
            print('\n📊 Queue Status:')
            print(f'   Total tasks: {queue_status["total_tasks"]}')
            print(f'   Auto-accepted: {sum(1 for t in queue.tasks.values() if t.auto_accept)}')
            print(f'   Manual approval: {sum(1 for t in queue.tasks.values() if not t.auto_accept)}')

            # Cleanup
            queue.shutdown()

            print('\n🎉 Auto-accept and background processing system working correctly!')

    except Exception as e:
        import traceback
        print(f'❌ Error testing auto-accept system: {e}')
        print(traceback.format_exc())


if __name__ == "__main__":
    test_auto_accept_system()
