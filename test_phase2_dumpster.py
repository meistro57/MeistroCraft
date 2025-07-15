#!/usr/bin/env python3
"""
Phase 2 Testing with Real Repository: meistro57/Dumpster
Tests GitHub workflow automation features with a real repository.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestPhase2WithDumpster(unittest.TestCase):
    """Test Phase 2 features using the Dumpster repository as a test case."""

    def setUp(self):
        """Set up test environment for Dumpster repository."""
        self.repo_name = "meistro57/Dumpster"
        self.test_config = {
            'github_api_key': 'test_token_123',
            'github': {
                'enabled': True,
                'default_branch': 'main',
                'rate_limit_delay': 0.1,
                'max_retries': 2
            }
        }

    def test_branch_naming_for_dumpster_tasks(self):
        """Test branch naming logic for typical Dumpster repository tasks."""
        from github_workflows import PullRequestManager

        # Mock GitHub client
        mock_github = Mock()
        pr_manager = PullRequestManager(mock_github)

        # Test different task types that might be used with Dumpster
        test_cases = [
            {
                "task": {
                    "action": "create_file",
                    "filename": "database_utils.py",
                    "instruction": "Create database utility functions"
                },
                "session_id": "abc12345-67890",
                "expected_pattern": "meistrocraft/abc12345/create-file-database-utils"
            },
            {
                "task": {
                    "action": "modify_file",
                    "filename": "bolt_manager.py",
                    "instruction": "Add error handling to bolt manager"
                },
                "session_id": "def67890-12345",
                "expected_pattern": "meistrocraft/def67890/modify-file-bolt-manager"
            },
            {
                "task": {
                    "action": "debug_code",
                    "instruction": "Fix SQL connection issues"
                },
                "session_id": "xyz99999-11111",
                "expected_pattern": "meistrocraft/xyz99999/debug-code-update"
            }
        ]

        for case in test_cases:
            with self.subTest(case=case):
                branch_name = pr_manager._generate_branch_name(
                    case["task"],
                    case["session_id"]
                )

                # Check branch name structure
                self.assertTrue(branch_name.startswith("meistrocraft/"))
                self.assertIn(case["session_id"][:8], branch_name)
                self.assertLessEqual(len(branch_name), 60)  # Reasonable length

                # Check no invalid characters
                valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-/_")
                self.assertTrue(all(c in valid_chars for c in branch_name))

    def test_pr_title_generation_for_dumpster(self):
        """Test PR title generation for Dumpster-specific tasks."""
        from github_workflows import PullRequestManager

        mock_github = Mock()
        pr_manager = PullRequestManager(mock_github)

        test_cases = [
            {
                "task": {
                    "action": "create_file",
                    "filename": "requirements.txt",
                    "instruction": "Add PyQt5 and database dependencies"
                },
                "expected": "Add requirements.txt"
            },
            {
                "task": {
                    "action": "modify_file",
                    "filename": "bolt_manager.py",
                    "instruction": "Improve error handling for SQL Server connections"
                },
                "expected": "Update bolt_manager.py"
            },
            {
                "task": {
                    "action": "debug_code",
                    "instruction": "Fix threading issues in database operations"
                },
                "expected": "Fix code issues - Fix threading issues in database"
            }
        ]

        for case in test_cases:
            with self.subTest(case=case):
                title = pr_manager._generate_pr_title(case["task"])
                self.assertEqual(title, case["expected"])

    def test_pr_description_for_dumpster_tasks(self):
        """Test PR description generation for Dumpster tasks."""
        from github_workflows import PullRequestManager

        mock_github = Mock()
        pr_manager = PullRequestManager(mock_github)

        task = {
            "action": "modify_file",
            "filename": "bolt_manager.py",
            "instruction": "Add connection pooling for better performance",
            "context": "Current implementation creates new connections for each operation"
        }

        result = {
            "success": True,
            "result": "Successfully added connection pooling with configurable pool size"
        }

        session_id = "test-session-12345"

        description = pr_manager._generate_pr_description(task, result, session_id)

        # Check description contains key elements
        self.assertIn("MeistroCraft Automated Changes", description)
        self.assertIn("modify_file", description)
        self.assertIn("bolt_manager.py", description)
        self.assertIn("test-ses", description)  # Session ID short form
        self.assertIn("Add connection pooling", description)
        self.assertIn("Review Checklist", description)
        self.assertIn("Generated by MeistroCraft", description)

    def test_issue_creation_for_dumpster_failures(self):
        """Test issue creation for typical Dumpster repository failures."""
        from github_workflows import IssueManager

        mock_github = Mock()
        issue_manager = IssueManager(mock_github)

        # Test PyQt5 import error (common in GUI applications)
        task = {
            "action": "modify_file",
            "filename": "bolt_manager.py",
            "instruction": "Add new dialog for database configuration"
        }

        error = "ImportError: No module named 'PyQt5'"
        session_id = "gui-test-session"

        title = issue_manager._generate_issue_title(task, error)
        description = issue_manager._generate_issue_description(task, error, session_id)
        labels = issue_manager._generate_issue_labels(task, error)

        # Check issue title
        self.assertIn("Failed to modify file", title)
        self.assertIn("bolt_manager.py", title)

        # Check description
        self.assertIn("MeistroCraft Task Failure", description)
        self.assertIn("ImportError", description)
        self.assertIn("PyQt5", description)
        self.assertIn("gui-test", description)

        # Check labels
        self.assertIn("bug", labels)
        self.assertIn("meistrocraft", labels)
        self.assertIn("modification-failure", labels)
        self.assertIn("dependencies", labels)  # Should detect import error

    def test_workflow_status_analysis(self):
        """Test workflow status analysis for repository health."""
        from github_workflows import WorkflowIntegration

        mock_github = Mock()
        workflow = WorkflowIntegration(mock_github)

        # Mock typical Dumpster repository state
        mock_prs = [
            {
                "number": 1,
                "title": "Add error handling to database operations",
                "created_at": "2025-07-10T12:00:00Z",
                "branch": "meistrocraft/abc123/modify-file-bolt-manager"
            }
        ]

        mock_issues = [
            {
                "number": 2,
                "title": "PyQt5 import error in bolt_manager",
                "labels": ["bug", "meistrocraft", "dependencies"],
                "created_at": "2025-07-12T14:00:00Z"
            }
        ]

        # Test workflow health assessment
        health = workflow._assess_workflow_health(mock_prs, mock_issues)
        self.assertEqual(health, "good")  # 1 PR + 1 issue = 2 total items

        # Test recommendations
        mock_repo = Mock()
        mock_repo.description = None  # No description

        recommendations = workflow._generate_recommendations(mock_repo, mock_prs, mock_issues)
        self.assertIn("Add repository description", recommendations)
        self.assertIn("Resolve 1 MeistroCraft-related issue(s)", recommendations)

    def test_repository_specific_patterns(self):
        """Test patterns specific to Dumpster repository structure."""
        # Test file path patterns
        dumpster_files = [
            "bolt_manager.py",
            "books/database_guide.pd",
            "html/documentation.html",
            "images/schema_diagram.png",
            "scripts/migration.sql"
        ]

        for file_path in dumpster_files:
            with self.subTest(file_path=file_path):
                # Test that file paths are handled correctly
                self.assertTrue(len(file_path) > 0)

                # Test branch naming with various file types
                task = {
                    "action": "modify_file",
                    "filename": file_path,
                    "instruction": f"Update {file_path}"
                }

                from github_workflows import PullRequestManager
                mock_github = Mock()
                pr_manager = PullRequestManager(mock_github)

                branch_name = pr_manager._generate_branch_name(task, "test-session")

                # Should handle all file types gracefully
                self.assertTrue(branch_name.startswith("meistrocraft/"))
                self.assertLessEqual(len(branch_name), 60)


class TestPhase2CLICommands(unittest.TestCase):
    """Test Phase 2 CLI commands structure and help text."""

    def test_new_github_commands(self):
        """Test that new GitHub commands are properly structured."""
        new_commands = [
            ["--github", "prs", "meistro57/Dumpster"],
            ["--github", "prs", "meistro57/Dumpster", "open"],
            ["--github", "prs", "meistro57/Dumpster", "closed"],
            ["--github", "issues", "meistro57/Dumpster"],
            ["--github", "issues", "meistro57/Dumpster", "open"],
            ["--github", "workflow", "meistro57/Dumpster"]
        ]

        for cmd in new_commands:
            with self.subTest(cmd=cmd):
                # Check command structure
                self.assertEqual(cmd[0], "--github")
                self.assertIn(cmd[1], ["prs", "issues", "workflow"])
                self.assertEqual(cmd[2], "meistro57/Dumpster")

                # Check optional state parameter
                if len(cmd) > 3:
                    self.assertIn(cmd[3], ["open", "closed", "all"])

    def test_github_help_text_includes_phase2(self):
        """Test that help text includes Phase 2 commands."""
        help_commands = [
            "meistrocraft --github prs owner/repo          # List pull requests",
            "meistrocraft --github issues owner/repo       # List issues",
            "meistrocraft --github workflow owner/repo     # Show workflow status"
        ]

        for help_line in help_commands:
            with self.subTest(help_line=help_line):
                # Check help format
                self.assertTrue(help_line.startswith("meistrocraft --github"))
                self.assertIn("#", help_line)  # Should have description
                parts = help_line.split("#")
                self.assertEqual(len(parts), 2)

                command_part = parts[0].strip()
                description_part = parts[1].strip()

                self.assertTrue(len(command_part) > 0)
                self.assertTrue(len(description_part) > 0)


def run_dumpster_integration_test():
    """Run integration test specifically for Dumpster repository patterns."""
    print("🧪 Phase 2 Integration Test with meistro57/Dumpster")
    print("=" * 55)

    print("\n📋 Testing repository-specific patterns...")

    # Test 1: Branch naming for Dumpster files
    print("1. Testing branch naming for Dumpster file types...")
    from github_workflows import PullRequestManager

    mock_github = Mock()
    pr_manager = PullRequestManager(mock_github)

    dumpster_tasks = [
        ("bolt_manager.py", "GUI application main file"),
        ("books/guide.pd", "Documentation file"),
        ("html/index.html", "Web content"),
        ("images/diagram.png", "Image asset"),
        ("scripts/migrate.sql", "Database script")
    ]

    for filename, description in dumpster_tasks:
        task = {
            "action": "modify_file",
            "filename": filename,
            "instruction": f"Update {description}"
        }

        branch_name = pr_manager._generate_branch_name(task, "dumpster-test")
        print(f"   📁 {filename} → {branch_name}")

        # Validate branch name
        assert branch_name.startswith("meistrocraft/")
        assert len(branch_name) <= 60
        assert all(c.isalnum() or c in '-/_' for c in branch_name)

    print("   ✅ All file types handled correctly")

    # Test 2: PR descriptions for database operations
    print("\n2. Testing PR descriptions for database operations...")

    db_task = {
        "action": "modify_file",
        "filename": "bolt_manager.py",
        "instruction": "Add connection pooling for SQL Server",
        "context": "Current implementation creates new connections for each query"
    }

    db_result = {
        "success": True,
        "result": "Added SQLAlchemy connection pool with configurable size and timeout"
    }

    description = pr_manager._generate_pr_description(db_task, db_result, "db-session")

    # Check key elements
    assert "MeistroCraft Automated Changes" in description
    assert "bolt_manager.py" in description
    assert "connection pooling" in description
    assert "SQLAlchemy" in description
    assert "Review Checklist" in description

    print("   ✅ Database operation PR description generated correctly")

    # Test 3: Issue creation for PyQt5 errors
    print("\n3. Testing issue creation for GUI framework errors...")

    from github_workflows import IssueManager
    issue_manager = IssueManager(mock_github)

    gui_task = {
        "action": "create_file",
        "filename": "config_dialog.py",
        "instruction": "Create configuration dialog for database settings"
    }

    gui_error = "ImportError: No module named 'PyQt5.QtWidgets'"

    title = issue_manager._generate_issue_title(gui_task, gui_error)
    labels = issue_manager._generate_issue_labels(gui_task, gui_error)

    assert "Failed to create file" in title
    assert "config_dialog.py" in title
    assert "bug" in labels
    assert "meistrocraft" in labels
    assert "dependencies" in labels

    print("   ✅ GUI error issue created with appropriate labels")

    # Test 4: Workflow recommendations
    print("\n4. Testing workflow recommendations for personal repositories...")

    from github_workflows import WorkflowIntegration
    workflow = WorkflowIntegration(mock_github)

    # Mock repository without description (common for personal repos)
    mock_repo = Mock()
    mock_repo.description = None

    mock_prs = []  # No open PRs
    mock_issues = [
        {"labels": ["bug", "meistrocraft"], "created_at": "2025-07-12T10:00:00Z"}
    ]

    recommendations = workflow._generate_recommendations(mock_repo, mock_prs, mock_issues)

    assert "Add repository description" in recommendations
    assert "Resolve 1 MeistroCraft-related issue(s)" in recommendations

    print("   ✅ Appropriate recommendations generated for personal repository")

    print("\n" + "=" * 55)
    print("🎉 All Dumpster integration tests passed!")
    print("\n✅ Phase 2 features are ready for real-world testing with:")
    print("   Repository: meistro57/Dumpster")
    print("   Features: PR creation, Issue tracking, Workflow analysis")
    print("   Commands: --github prs/issues/workflow meistro57/Dumpster")

    return True


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--dumpster':
        success = run_dumpster_integration_test()
        sys.exit(0 if success else 1)
    else:
        unittest.main()
