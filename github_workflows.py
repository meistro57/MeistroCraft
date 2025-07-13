"""
GitHub Workflow Automation for MeistroCraft - Phase 2
Handles pull requests, issues, and workflow automation for development.
"""

import json
import os
import time
import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path

from github_client import GitHubClient, GitHubClientError, GitHubAuthenticationError

try:
    from code_review_analyzer import CodeReviewAnalyzer, create_code_review_analyzer
except ImportError:
    CodeReviewAnalyzer = None
    create_code_review_analyzer = None


class GitHubWorkflowError(Exception):
    """Custom exception for GitHub workflow errors."""
    pass


class PullRequestManager:
    """
    Manages automated pull request creation and management.
    Designed for MeistroCraft integration with real repositories.
    """
    
    def __init__(self, github_client: GitHubClient, config: Dict[str, Any] = None):
        """
        Initialize PR manager with GitHub client.
        
        Args:
            github_client: Authenticated GitHub client instance
            config: Configuration dictionary for AI features
        """
        self.github = github_client
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize code review analyzer if available
        self.code_review_analyzer = None
        if create_code_review_analyzer:
            self.code_review_analyzer = create_code_review_analyzer(github_client, config)
    
    def create_pr_from_task(
        self,
        repo_name: str,
        task: Dict[str, Any],
        result: Dict[str, Any],
        session_id: str,
        branch_name: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a pull request from a completed MeistroCraft task.
        
        Args:
            repo_name: Repository name (owner/repo)
            task: MeistroCraft task that was completed
            result: Task execution result
            session_id: MeistroCraft session ID
            branch_name: Optional branch name (auto-generated if not provided)
            
        Returns:
            Pull request data or None if creation failed
        """
        if not self.github.is_authenticated():
            raise GitHubAuthenticationError("GitHub client not authenticated")
        
        try:
            repo = self.github.get_repository(repo_name)
            
            # Generate branch name if not provided
            if not branch_name:
                branch_name = self._generate_branch_name(task, session_id)
            
            # Create feature branch
            try:
                branch_ref = self.github.create_branch(repo, branch_name)
                self.logger.info(f"Created branch '{branch_name}' for task")
            except GitHubClientError as e:
                if "already exists" in str(e).lower():
                    self.logger.warning(f"Branch '{branch_name}' already exists, using existing branch")
                else:
                    raise
            
            # Generate PR title and description
            pr_title = self._generate_pr_title(task)
            pr_description = self._generate_pr_description(task, result, session_id)
            
            # Create pull request
            if hasattr(repo, 'create_pull'):  # PyGitHub object
                pr = repo.create_pull(
                    title=pr_title,
                    body=pr_description,
                    head=branch_name,
                    base=repo.default_branch
                )
                
                pr_data = {
                    "number": pr.number,
                    "title": pr.title,
                    "html_url": pr.html_url,
                    "state": pr.state,
                    "branch": branch_name,
                    "created_at": pr.created_at.isoformat()
                }
            else:
                # Fallback mode - direct API call
                pr_data_raw = {
                    "title": pr_title,
                    "body": pr_description,
                    "head": branch_name,
                    "base": repo.get("default_branch", "main")
                }
                
                pr = self.github._make_fallback_request(
                    "POST", 
                    f"/repos/{repo_name}/pulls", 
                    pr_data_raw
                )
                
                pr_data = {
                    "number": pr.get("number"),
                    "title": pr.get("title"),
                    "html_url": pr.get("html_url"),
                    "state": pr.get("state"),
                    "branch": branch_name,
                    "created_at": pr.get("created_at")
                }
            
            self.logger.info(f"Created PR #{pr_data['number']}: {pr_title}")
            
            # Add AI code review if enabled
            if self.code_review_analyzer and self.config.get('enable_ai_review', True):
                try:
                    self._add_ai_code_review(repo_name, pr_data['number'], task, result)
                except Exception as e:
                    self.logger.warning(f"Failed to add AI code review: {e}")
            
            return pr_data
            
        except Exception as e:
            self.logger.error(f"Failed to create PR: {e}")
            raise GitHubWorkflowError(f"PR creation failed: {e}")
    
    def _generate_branch_name(self, task: Dict[str, Any], session_id: str) -> str:
        """Generate a descriptive branch name for the task."""
        action = task.get('action', 'task')
        filename = task.get('filename', '')
        
        # Extract meaningful parts
        if filename:
            # Use filename without extension
            file_base = Path(filename).stem.replace('_', '-').replace(' ', '-')
            branch_base = f"{action}-{file_base}"
        else:
            # Use action type
            branch_base = f"{action}-update"
        
        # Add session prefix for uniqueness
        session_short = session_id[:8] if session_id else "manual"
        branch_name = f"meistrocraft/{session_short}/{branch_base}"
        
        # Clean up branch name
        branch_name = branch_name.lower()
        branch_name = ''.join(c for c in branch_name if c.isalnum() or c in '-/_')
        
        # Ensure reasonable length
        if len(branch_name) > 60:
            branch_name = branch_name[:57] + "..."
        
        return branch_name
    
    def _generate_pr_title(self, task: Dict[str, Any]) -> str:
        """Generate a descriptive PR title."""
        action = task.get('action', 'update')
        filename = task.get('filename', '')
        instruction = task.get('instruction', '')
        
        # Create title based on action type
        if action == 'create_file' and filename:
            title = f"Add {filename}"
        elif action == 'modify_file' and filename:
            title = f"Update {filename}"
        elif action == 'debug_code':
            title = "Fix code issues"
        elif action == 'refactor_code':
            title = "Refactor code structure"
        elif action == 'run_tests':
            title = "Add/update tests"
        else:
            title = f"MeistroCraft: {action.replace('_', ' ').title()}"
        
        # Add context from instruction if title is generic
        if len(title) < 20 and instruction:
            # Extract first meaningful part of instruction
            instruction_words = instruction.split()[:5]
            context = " ".join(instruction_words)
            if len(context) < 50:
                title += f" - {context}"
        
        return title
    
    def _generate_pr_description(
        self, 
        task: Dict[str, Any], 
        result: Dict[str, Any], 
        session_id: str
    ) -> str:
        """Generate a comprehensive PR description."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        description = f"""## MeistroCraft Automated Changes

### 📋 Task Summary
- **Action**: {task.get('action', 'unknown')}
- **File**: {task.get('filename', 'N/A')}
- **Session**: {session_id[:8] if session_id else 'manual'}
- **Timestamp**: {timestamp}

### 🎯 Task Description
{task.get('instruction', 'No description provided')}

### ✅ Execution Result
"""
        
        if result.get('success'):
            description += f"""**Status**: ✅ Success

**Changes Made**:
{result.get('result', 'Task completed successfully')[:500]}{'...' if len(result.get('result', '')) > 500 else ''}
"""
        else:
            description += f"""**Status**: ❌ Failed

**Error Details**:
{result.get('error', 'Unknown error occurred')}
"""
        
        # Add context if available
        if task.get('context'):
            description += f"""

### 📝 Additional Context
{task['context'][:300]}{'...' if len(task['context']) > 300 else ''}
"""
        
        # Add checklist for review
        description += """

### 🔍 Review Checklist
- [ ] Code changes are correct and functional
- [ ] No sensitive information is exposed
- [ ] Code follows project conventions
- [ ] Documentation is updated if needed
- [ ] Tests pass (if applicable)

### 🤖 Generated by MeistroCraft
This pull request was automatically created by MeistroCraft's AI coding assistant.
Review the changes carefully before merging.
"""
        
        return description
    
    def list_repository_prs(
        self, 
        repo_name: str, 
        state: str = "open"
    ) -> List[Dict[str, Any]]:
        """
        List pull requests for a repository.
        
        Args:
            repo_name: Repository name (owner/repo)
            state: PR state ("open", "closed", "all")
            
        Returns:
            List of pull request data
        """
        try:
            repo = self.github.get_repository(repo_name)
            
            if hasattr(repo, 'get_pulls'):  # PyGitHub object
                pulls = list(repo.get_pulls(state=state))
                return [
                    {
                        "number": pr.number,
                        "title": pr.title,
                        "state": pr.state,
                        "html_url": pr.html_url,
                        "created_at": pr.created_at.isoformat(),
                        "user": pr.user.login,
                        "branch": pr.head.ref,
                        "base": pr.base.ref
                    }
                    for pr in pulls
                ]
            else:
                # Fallback mode
                pulls = self.github._make_fallback_request(
                    "GET", 
                    f"/repos/{repo_name}/pulls?state={state}"
                )
                return [
                    {
                        "number": pr.get("number"),
                        "title": pr.get("title"),
                        "state": pr.get("state"),
                        "html_url": pr.get("html_url"),
                        "created_at": pr.get("created_at"),
                        "user": pr.get("user", {}).get("login"),
                        "branch": pr.get("head", {}).get("ref"),
                        "base": pr.get("base", {}).get("ref")
                    }
                    for pr in pulls
                ]
                
        except Exception as e:
            self.logger.error(f"Failed to list PRs: {e}")
            raise GitHubWorkflowError(f"Failed to list PRs: {e}")
    
    def _add_ai_code_review(
        self, 
        repo_name: str, 
        pr_number: int,
        task: Dict[str, Any] = None,
        result: Dict[str, Any] = None
    ) -> None:
        """
        Add AI-powered code review comments to a pull request.
        
        Args:
            repo_name: Repository name (owner/repo)
            pr_number: Pull request number
            task: MeistroCraft task that created the PR (optional)
            result: Task execution result (optional)
        """
        if not self.code_review_analyzer:
            return
        
        try:
            # Analyze the pull request
            review_analysis = self.code_review_analyzer.analyze_pull_request(repo_name, pr_number)
            
            # Generate review comment
            review_comment = self._generate_ai_review_comment(review_analysis, task, result)
            
            # Post review comment
            self._post_pr_review_comment(repo_name, pr_number, review_comment)
            
            self.logger.info(f"Added AI code review to PR #{pr_number}")
            
        except Exception as e:
            self.logger.error(f"Failed to add AI code review: {e}")
            # Don't re-raise - this is optional functionality
    
    def _generate_ai_review_comment(
        self, 
        review_analysis: Dict[str, Any],
        task: Dict[str, Any] = None,
        result: Dict[str, Any] = None
    ) -> str:
        """Generate AI review comment from analysis results."""
        overall_score = review_analysis.get('overall_score', 0)
        summary = review_analysis.get('summary', '')
        security_concerns = review_analysis.get('security_concerns', [])
        performance_suggestions = review_analysis.get('performance_suggestions', [])
        recommendations = review_analysis.get('recommendations', [])
        ai_insights = review_analysis.get('ai_insights')
        
        # Build review comment
        comment = f"""## 🤖 AI-Powered Code Review
        
**Overall Quality Score**: {overall_score}/100

{summary}

"""
        
        # Add security section if issues found
        if security_concerns:
            comment += "### 🔒 Security Analysis\n"
            critical_security = [c for c in security_concerns if c['severity'] == 'critical']
            
            if critical_security:
                comment += "⚠️ **CRITICAL SECURITY ISSUES FOUND**\n\n"
                for concern in critical_security[:3]:  # Limit to top 3
                    comment += f"- **{concern['filename']}:{concern['line']}** - {concern['message']}\n"
                    comment += f"  💡 *{concern['suggestion']}*\n\n"
            else:
                high_security = [c for c in security_concerns if c['severity'] == 'high']
                if high_security:
                    comment += "⚠️ **High Priority Security Issues**\n\n"
                    for concern in high_security[:2]:  # Limit to top 2
                        comment += f"- **{concern['filename']}:{concern['line']}** - {concern['message']}\n\n"
        
        # Add performance section if suggestions found
        if performance_suggestions:
            comment += "### ⚡ Performance Optimization\n"
            for suggestion in performance_suggestions[:3]:  # Limit to top 3
                comment += f"- **{suggestion['filename']}:{suggestion['line']}** - {suggestion['message']}\n"
                comment += f"  💡 *{suggestion['suggestion']}*\n\n"
        
        # Add AI insights if available
        if ai_insights:
            comment += f"### 🧠 AI Strategic Insights\n{ai_insights}\n\n"
        
        # Add recommendations
        if recommendations:
            comment += "### 📋 Recommendations\n"
            for rec in recommendations:
                comment += f"- {rec}\n"
            comment += "\n"
        
        # Add task context if available
        if task:
            comment += f"""### 🎯 MeistroCraft Task Context
- **Action**: {task.get('action', 'unknown')}
- **File**: {task.get('filename', 'N/A')}
- **Task**: {task.get('instruction', 'No description')[:100]}{'...' if len(task.get('instruction', '')) > 100 else ''}

"""
        
        # Add overall assessment
        if overall_score >= 90:
            comment += "### ✨ Overall Assessment\n🎉 **Excellent work!** This code meets high quality standards.\n\n"
        elif overall_score >= 70:
            comment += "### ✅ Overall Assessment\n👍 **Good quality code** with minor areas for improvement.\n\n"
        elif overall_score >= 50:
            comment += "### ⚠️ Overall Assessment\n🔧 **Needs attention** - several issues should be addressed.\n\n"
        else:
            comment += "### 🚨 Overall Assessment\n⛔ **Significant issues found** - review and refactor recommended.\n\n"
        
        comment += """---
*This review was automatically generated by MeistroCraft's AI-powered code analysis.*
*Review the suggestions carefully and apply improvements as appropriate.*"""
        
        return comment
    
    def _post_pr_review_comment(self, repo_name: str, pr_number: int, comment: str) -> None:
        """Post a review comment to a pull request."""
        try:
            repo = self.github.get_repository(repo_name)
            
            if hasattr(repo, 'get_pull'):  # PyGitHub object
                pr = repo.get_pull(pr_number)
                pr.create_issue_comment(comment)
            else:
                # Fallback mode
                comment_data = {"body": comment}
                self.github._make_fallback_request(
                    "POST",
                    f"/repos/{repo_name}/issues/{pr_number}/comments",
                    comment_data
                )
            
            self.logger.info(f"Posted AI review comment to PR #{pr_number}")
            
        except Exception as e:
            self.logger.error(f"Failed to post review comment: {e}")
            raise


class IssueManager:
    """
    Manages GitHub issue creation and tracking for MeistroCraft.
    Automatically creates issues for task failures and tracks progress.
    """
    
    def __init__(self, github_client: GitHubClient):
        """
        Initialize issue manager with GitHub client.
        
        Args:
            github_client: Authenticated GitHub client instance
        """
        self.github = github_client
        self.logger = logging.getLogger(__name__)
    
    def create_issue_from_failure(
        self,
        repo_name: str,
        task: Dict[str, Any],
        error: str,
        session_id: str,
        labels: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Create a GitHub issue from a failed MeistroCraft task.
        
        Args:
            repo_name: Repository name (owner/repo)
            task: Failed MeistroCraft task
            error: Error message from task failure
            session_id: MeistroCraft session ID
            labels: Optional labels for the issue
            
        Returns:
            Issue data or None if creation failed
        """
        if not self.github.is_authenticated():
            raise GitHubAuthenticationError("GitHub client not authenticated")
        
        try:
            repo = self.github.get_repository(repo_name)
            
            # Generate issue title and description
            issue_title = self._generate_issue_title(task, error)
            issue_description = self._generate_issue_description(task, error, session_id)
            
            # Default labels
            if not labels:
                labels = self._generate_issue_labels(task, error)
            
            # Create issue
            if hasattr(repo, 'create_issue'):  # PyGitHub object
                issue = repo.create_issue(
                    title=issue_title,
                    body=issue_description,
                    labels=labels
                )
                
                issue_data = {
                    "number": issue.number,
                    "title": issue.title,
                    "html_url": issue.html_url,
                    "state": issue.state,
                    "labels": [label.name for label in issue.labels],
                    "created_at": issue.created_at.isoformat()
                }
            else:
                # Fallback mode
                issue_data_raw = {
                    "title": issue_title,
                    "body": issue_description,
                    "labels": labels
                }
                
                issue = self.github._make_fallback_request(
                    "POST",
                    f"/repos/{repo_name}/issues",
                    issue_data_raw
                )
                
                issue_data = {
                    "number": issue.get("number"),
                    "title": issue.get("title"),
                    "html_url": issue.get("html_url"),
                    "state": issue.get("state"),
                    "labels": [label.get("name") for label in issue.get("labels", [])],
                    "created_at": issue.get("created_at")
                }
            
            self.logger.info(f"Created issue #{issue_data['number']}: {issue_title}")
            return issue_data
            
        except Exception as e:
            self.logger.error(f"Failed to create issue: {e}")
            raise GitHubWorkflowError(f"Issue creation failed: {e}")
    
    def _generate_issue_title(self, task: Dict[str, Any], error: str) -> str:
        """Generate a descriptive issue title."""
        action = task.get('action', 'task')
        filename = task.get('filename', '')
        
        if filename:
            title = f"Failed to {action.replace('_', ' ')}: {filename}"
        else:
            title = f"MeistroCraft task failed: {action.replace('_', ' ')}"
        
        # Add error context if title is too generic
        if "error" in error.lower() or "failed" in error.lower():
            error_words = error.split()[:3]
            error_context = " ".join(error_words)
            if len(error_context) < 30:
                title += f" ({error_context})"
        
        return title
    
    def _generate_issue_description(
        self,
        task: Dict[str, Any],
        error: str,
        session_id: str
    ) -> str:
        """Generate a comprehensive issue description."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        description = f"""## 🐛 MeistroCraft Task Failure

### 📋 Task Details
- **Action**: {task.get('action', 'unknown')}
- **File**: {task.get('filename', 'N/A')}
- **Session**: {session_id[:8] if session_id else 'manual'}
- **Timestamp**: {timestamp}

### 🎯 Task Instruction
{task.get('instruction', 'No instruction provided')}

### ❌ Error Details
```
{error}
```

### 🔍 Context
"""
        
        if task.get('context'):
            description += f"{task['context']}\n\n"
        else:
            description += "No additional context provided.\n\n"
        
        description += """### 🛠️ Suggested Actions
- [ ] Review the error message and identify the root cause
- [ ] Check if the target file exists and is accessible
- [ ] Verify that all dependencies are installed
- [ ] Ensure the task instruction is clear and achievable
- [ ] Test the fix manually before closing this issue

### 🔄 Reproduction Steps
1. Run MeistroCraft with the same task configuration
2. Use session ID: `{}`
3. Execute the failed action: `{}`

### 🤖 Auto-generated Issue
This issue was automatically created by MeistroCraft when a task failed.
Please investigate and resolve the underlying problem.
""".format(session_id[:8] if session_id else 'manual', task.get('action', 'unknown'))
        
        return description
    
    def _generate_issue_labels(self, task: Dict[str, Any], error: str) -> List[str]:
        """Generate appropriate labels for the issue."""
        labels = ["bug", "meistrocraft"]
        
        # Add action-specific labels
        action = task.get('action', '').lower()
        if 'create' in action:
            labels.append("creation-failure")
        elif 'modify' in action or 'update' in action:
            labels.append("modification-failure")
        elif 'debug' in action:
            labels.append("debug-failure")
        elif 'test' in action:
            labels.append("test-failure")
        
        # Add error-specific labels
        error_lower = error.lower()
        if 'permission' in error_lower or 'access' in error_lower:
            labels.append("permissions")
        elif 'network' in error_lower or 'connection' in error_lower:
            labels.append("network")
        elif 'syntax' in error_lower or 'parse' in error_lower:
            labels.append("syntax")
        elif 'import' in error_lower or 'module' in error_lower:
            labels.append("dependencies")
        
        return labels
    
    def close_issue_on_success(
        self,
        repo_name: str,
        issue_number: int,
        resolution_comment: str = None
    ) -> bool:
        """
        Close an issue when a related task succeeds.
        
        Args:
            repo_name: Repository name (owner/repo)
            issue_number: Issue number to close
            resolution_comment: Optional comment explaining the resolution
            
        Returns:
            True if issue was closed successfully
        """
        try:
            repo = self.github.get_repository(repo_name)
            
            # Add resolution comment if provided
            if resolution_comment:
                if hasattr(repo, 'get_issue'):  # PyGitHub object
                    issue = repo.get_issue(issue_number)
                    issue.create_comment(resolution_comment)
                    issue.edit(state='closed')
                else:
                    # Fallback mode
                    comment_data = {"body": resolution_comment}
                    self.github._make_fallback_request(
                        "POST",
                        f"/repos/{repo_name}/issues/{issue_number}/comments",
                        comment_data
                    )
                    
                    update_data = {"state": "closed"}
                    self.github._make_fallback_request(
                        "PATCH",
                        f"/repos/{repo_name}/issues/{issue_number}",
                        update_data
                    )
            else:
                if hasattr(repo, 'get_issue'):  # PyGitHub object
                    issue = repo.get_issue(issue_number)
                    issue.edit(state='closed')
                else:
                    update_data = {"state": "closed"}
                    self.github._make_fallback_request(
                        "PATCH",
                        f"/repos/{repo_name}/issues/{issue_number}",
                        update_data
                    )
            
            self.logger.info(f"Closed issue #{issue_number}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to close issue #{issue_number}: {e}")
            return False
    
    def list_repository_issues(
        self,
        repo_name: str,
        state: str = "open",
        labels: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List issues for a repository.
        
        Args:
            repo_name: Repository name (owner/repo)
            state: Issue state ("open", "closed", "all")
            labels: Optional list of labels to filter by
            
        Returns:
            List of issue data
        """
        try:
            repo = self.github.get_repository(repo_name)
            
            if hasattr(repo, 'get_issues'):  # PyGitHub object
                kwargs = {"state": state}
                if labels:
                    kwargs["labels"] = labels
                
                issues = list(repo.get_issues(**kwargs))
                return [
                    {
                        "number": issue.number,
                        "title": issue.title,
                        "state": issue.state,
                        "html_url": issue.html_url,
                        "created_at": issue.created_at.isoformat(),
                        "user": issue.user.login,
                        "labels": [label.name for label in issue.labels],
                        "assignees": [assignee.login for assignee in issue.assignees]
                    }
                    for issue in issues
                ]
            else:
                # Fallback mode
                endpoint = f"/repos/{repo_name}/issues?state={state}"
                if labels:
                    endpoint += "&labels=" + ",".join(labels)
                
                issues = self.github._make_fallback_request("GET", endpoint)
                return [
                    {
                        "number": issue.get("number"),
                        "title": issue.get("title"),
                        "state": issue.get("state"),
                        "html_url": issue.get("html_url"),
                        "created_at": issue.get("created_at"),
                        "user": issue.get("user", {}).get("login"),
                        "labels": [label.get("name") for label in issue.get("labels", [])],
                        "assignees": [assignee.get("login") for assignee in issue.get("assignees", [])]
                    }
                    for issue in issues
                ]
                
        except Exception as e:
            self.logger.error(f"Failed to list issues: {e}")
            raise GitHubWorkflowError(f"Failed to list issues: {e}")


class WorkflowIntegration:
    """
    Integrates MeistroCraft with GitHub workflows and development processes.
    Coordinates PR and issue management for seamless development flow.
    """
    
    def __init__(self, github_client: GitHubClient):
        """
        Initialize workflow integration.
        
        Args:
            github_client: Authenticated GitHub client instance
        """
        self.github = github_client
        self.pr_manager = PullRequestManager(github_client)
        self.issue_manager = IssueManager(github_client)
        self.logger = logging.getLogger(__name__)
    
    def process_task_result(
        self,
        repo_name: str,
        task: Dict[str, Any],
        result: Dict[str, Any],
        session_id: str,
        auto_create_pr: bool = True,
        auto_create_issue: bool = True
    ) -> Dict[str, Any]:
        """
        Process a MeistroCraft task result and create appropriate GitHub objects.
        
        Args:
            repo_name: Repository name (owner/repo)
            task: MeistroCraft task that was executed
            result: Task execution result
            session_id: MeistroCraft session ID
            auto_create_pr: Whether to automatically create PRs for successful tasks
            auto_create_issue: Whether to automatically create issues for failed tasks
            
        Returns:
            Dictionary with created GitHub objects
        """
        workflow_result = {
            "success": result.get("success", False),
            "pr_created": None,
            "issue_created": None,
            "actions_taken": []
        }
        
        try:
            if result.get("success") and auto_create_pr:
                # Task succeeded - create pull request
                try:
                    pr_data = self.pr_manager.create_pr_from_task(
                        repo_name, task, result, session_id
                    )
                    workflow_result["pr_created"] = pr_data
                    workflow_result["actions_taken"].append("pr_created")
                    self.logger.info(f"Created PR for successful task: {task.get('action')}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to create PR: {e}")
                    workflow_result["actions_taken"].append("pr_creation_failed")
            
            elif not result.get("success") and auto_create_issue:
                # Task failed - create issue
                try:
                    issue_data = self.issue_manager.create_issue_from_failure(
                        repo_name, task, result.get("error", "Unknown error"), session_id
                    )
                    workflow_result["issue_created"] = issue_data
                    workflow_result["actions_taken"].append("issue_created")
                    self.logger.info(f"Created issue for failed task: {task.get('action')}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to create issue: {e}")
                    workflow_result["actions_taken"].append("issue_creation_failed")
            
            return workflow_result
            
        except Exception as e:
            self.logger.error(f"Workflow processing failed: {e}")
            workflow_result["actions_taken"].append("workflow_error")
            return workflow_result
    
    def get_repository_status(self, repo_name: str) -> Dict[str, Any]:
        """
        Get comprehensive status of a repository's development workflow.
        
        Args:
            repo_name: Repository name (owner/repo)
            
        Returns:
            Repository status including PRs, issues, and recommendations
        """
        try:
            # Get repository info
            repo = self.github.get_repository(repo_name)
            
            # Get PRs and issues
            open_prs = self.pr_manager.list_repository_prs(repo_name, "open")
            open_issues = self.issue_manager.list_repository_issues(repo_name, "open")
            
            # Count MeistroCraft-related items
            meistrocraft_prs = [pr for pr in open_prs if "meistrocraft" in pr.get("branch", "").lower()]
            meistrocraft_issues = [
                issue for issue in open_issues 
                if any("meistrocraft" in label.lower() for label in issue.get("labels", []))
            ]
            
            status = {
                "repository": repo_name,
                "total_open_prs": len(open_prs),
                "total_open_issues": len(open_issues),
                "meistrocraft_prs": len(meistrocraft_prs),
                "meistrocraft_issues": len(meistrocraft_issues),
                "recent_prs": open_prs[:5],  # Most recent 5
                "recent_issues": open_issues[:5],  # Most recent 5
                "workflow_health": self._assess_workflow_health(open_prs, open_issues),
                "recommendations": self._generate_recommendations(repo, open_prs, open_issues)
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"Failed to get repository status: {e}")
            return {
                "repository": repo_name,
                "error": str(e),
                "workflow_health": "unknown"
            }
    
    def _assess_workflow_health(self, prs: List[Dict], issues: List[Dict]) -> str:
        """Assess the health of the repository's workflow."""
        total_items = len(prs) + len(issues)
        
        if total_items == 0:
            return "excellent"
        elif total_items <= 5:
            return "good"
        elif total_items <= 15:
            return "moderate"
        else:
            return "needs_attention"
    
    def _generate_recommendations(
        self, 
        repo: Any, 
        prs: List[Dict], 
        issues: List[Dict]
    ) -> List[str]:
        """Generate workflow improvement recommendations."""
        recommendations = []
        
        # Check for stale PRs
        stale_prs = [
            pr for pr in prs 
            if self._is_stale(pr.get("created_at", ""))
        ]
        if stale_prs:
            recommendations.append(f"Review {len(stale_prs)} stale pull request(s)")
        
        # Check for many open issues
        if len(issues) > 10:
            recommendations.append("Consider prioritizing issue resolution")
        
        # Check for MeistroCraft-specific recommendations
        meistrocraft_issues = [
            issue for issue in issues 
            if any("meistrocraft" in label.lower() for label in issue.get("labels", []))
        ]
        if meistrocraft_issues:
            recommendations.append(f"Resolve {len(meistrocraft_issues)} MeistroCraft-related issue(s)")
        
        # Repository-specific recommendations
        if hasattr(repo, 'description') and not repo.description:
            recommendations.append("Add repository description")
        
        return recommendations
    
    def _is_stale(self, created_at: str, days: int = 7) -> bool:
        """Check if an item is stale (older than specified days)."""
        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            cutoff = datetime.now().replace(tzinfo=created.tzinfo) - timedelta(days=days)
            return created < cutoff
        except:
            return False


def create_workflow_integration(github_client: GitHubClient, config: Dict[str, Any] = None) -> Optional[WorkflowIntegration]:
    """
    Create and configure workflow integration with GitHub client.
    
    Args:
        github_client: Authenticated GitHub client instance
        config: Configuration dictionary
        
    Returns:
        WorkflowIntegration instance or None if GitHub is disabled
    """
    if not github_client or not github_client.is_authenticated():
        return None
        
    try:
        return WorkflowIntegration(github_client, config)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to create workflow integration: {e}")
        return None
