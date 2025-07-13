"""
CI/CD Pipeline Integration for MeistroCraft - Phase 3
Handles GitHub Actions, build monitoring, and deployment automation.
"""

import json
import os
import time
import logging
import yaml
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum

from github_client import GitHubClient, GitHubClientError, GitHubAuthenticationError


class WorkflowStatus(Enum):
    """GitHub Actions workflow status enumeration."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    REQUESTED = "requested"
    WAITING = "waiting"


class WorkflowConclusion(Enum):
    """GitHub Actions workflow conclusion enumeration."""
    SUCCESS = "success"
    FAILURE = "failure"
    NEUTRAL = "neutral"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"


class CICDIntegrationError(Exception):
    """Custom exception for CI/CD integration errors."""
    pass


class GitHubActionsManager:
    """
    Manages GitHub Actions workflows and build status monitoring.
    Integrates with MeistroCraft's task execution system.
    """
    
    def __init__(self, github_client: GitHubClient, config: Dict[str, Any] = None):
        """
        Initialize GitHub Actions manager.
        
        Args:
            github_client: Authenticated GitHub client instance
            config: Configuration dictionary for CI/CD settings
        """
        self.github = github_client
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Workflow monitoring settings
        self.max_wait_time = self.config.get('max_workflow_wait', 1800)  # 30 minutes
        self.check_interval = self.config.get('workflow_check_interval', 30)  # 30 seconds
        
        # Default workflow templates
        self.workflow_templates = self._load_workflow_templates()
    
    def get_workflow_runs(
        self, 
        repo_name: str, 
        workflow_id: str = None,
        branch: str = None,
        status: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get workflow runs for a repository.
        
        Args:
            repo_name: Repository name (owner/repo)
            workflow_id: Specific workflow ID (optional)
            branch: Filter by branch (optional)
            status: Filter by status (optional)
            limit: Number of runs to retrieve
            
        Returns:
            List of workflow run data
        """
        if not self.github.is_authenticated():
            raise GitHubAuthenticationError("GitHub client not authenticated")
        
        try:
            repo = self.github.get_repository(repo_name)
            
            # Build query parameters
            params = {
                'per_page': min(limit, 100)
            }
            
            if branch:
                params['branch'] = branch
            if status:
                params['status'] = status
            
            if hasattr(repo, 'get_workflow_runs'):  # PyGitHub object
                if workflow_id:
                    workflow = repo.get_workflow(workflow_id)
                    runs = list(workflow.get_runs())[:limit]
                else:
                    runs = list(repo.get_workflow_runs())[:limit]
                
                return [
                    {
                        'id': run.id,
                        'name': run.name,
                        'status': run.status,
                        'conclusion': run.conclusion,
                        'workflow_id': run.workflow_id,
                        'head_branch': run.head_branch,
                        'head_sha': run.head_sha,
                        'run_number': run.run_number,
                        'created_at': run.created_at.isoformat() if run.created_at else None,
                        'updated_at': run.updated_at.isoformat() if run.updated_at else None,
                        'html_url': run.html_url,
                        'jobs_url': run.jobs_url,
                        'logs_url': run.logs_url,
                        'cancel_url': run.cancel_url,
                        'rerun_url': run.rerun_url
                    }
                    for run in runs
                ]
            else:
                # Fallback API mode
                endpoint = f'/repos/{repo_name}/actions/runs'
                if workflow_id:
                    endpoint = f'/repos/{repo_name}/actions/workflows/{workflow_id}/runs'
                
                response = self.github._make_fallback_request('GET', endpoint, params=params)
                return response.get('workflow_runs', [])
                
        except Exception as e:
            self.logger.error(f"Failed to get workflow runs: {e}")
            raise CICDIntegrationError(f"Failed to get workflow runs: {e}")
    
    def trigger_workflow(
        self,
        repo_name: str,
        workflow_id: str,
        ref: str = 'main',
        inputs: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Trigger a GitHub Actions workflow.
        
        Args:
            repo_name: Repository name (owner/repo)
            workflow_id: Workflow ID or filename
            ref: Git reference (branch/tag/commit)
            inputs: Workflow inputs dictionary
            
        Returns:
            Workflow dispatch result
        """
        if not self.github.is_authenticated():
            raise GitHubAuthenticationError("GitHub client not authenticated")
        
        try:
            repo = self.github.get_repository(repo_name)
            
            dispatch_data = {
                'ref': ref,
                'inputs': inputs or {}
            }
            
            if hasattr(repo, 'create_workflow_dispatch'):  # PyGitHub object
                workflow = repo.get_workflow(workflow_id)
                result = workflow.create_dispatch(ref, inputs or {})
                
                return {
                    'success': True,
                    'workflow_id': workflow_id,
                    'ref': ref,
                    'inputs': inputs,
                    'triggered_at': datetime.now().isoformat()
                }
            else:
                # Fallback API mode
                endpoint = f'/repos/{repo_name}/actions/workflows/{workflow_id}/dispatches'
                self.github._make_fallback_request('POST', endpoint, dispatch_data)
                
                return {
                    'success': True,
                    'workflow_id': workflow_id,
                    'ref': ref,
                    'inputs': inputs,
                    'triggered_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            self.logger.error(f"Failed to trigger workflow: {e}")
            raise CICDIntegrationError(f"Failed to trigger workflow: {e}")
    
    def monitor_workflow_run(
        self,
        repo_name: str,
        run_id: int,
        timeout: int = None
    ) -> Dict[str, Any]:
        """
        Monitor a workflow run until completion or timeout.
        
        Args:
            repo_name: Repository name (owner/repo)
            run_id: Workflow run ID
            timeout: Maximum wait time in seconds
            
        Returns:
            Final workflow run status and details
        """
        if not self.github.is_authenticated():
            raise GitHubAuthenticationError("GitHub client not authenticated")
        
        timeout = timeout or self.max_wait_time
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                run_data = self._get_workflow_run_details(repo_name, run_id)
                
                status = run_data.get('status')
                conclusion = run_data.get('conclusion')
                
                # Check if workflow is complete
                if status == WorkflowStatus.COMPLETED.value:
                    return {
                        'completed': True,
                        'success': conclusion == WorkflowConclusion.SUCCESS.value,
                        'conclusion': conclusion,
                        'run_data': run_data,
                        'duration': time.time() - start_time
                    }
                
                # Check for cancelled or failed states
                if status in [WorkflowStatus.CANCELLED.value] or conclusion in [
                    WorkflowConclusion.FAILURE.value,
                    WorkflowConclusion.CANCELLED.value,
                    WorkflowConclusion.TIMED_OUT.value
                ]:
                    return {
                        'completed': True,
                        'success': False,
                        'conclusion': conclusion,
                        'run_data': run_data,
                        'duration': time.time() - start_time
                    }
                
                # Wait before next check
                time.sleep(self.check_interval)
            
            # Timeout reached
            return {
                'completed': False,
                'success': False,
                'conclusion': 'timeout',
                'run_data': self._get_workflow_run_details(repo_name, run_id),
                'duration': timeout
            }
            
        except Exception as e:
            self.logger.error(f"Failed to monitor workflow run: {e}")
            raise CICDIntegrationError(f"Failed to monitor workflow run: {e}")
    
    def get_workflow_job_logs(self, repo_name: str, job_id: int) -> str:
        """
        Get logs for a specific workflow job.
        
        Args:
            repo_name: Repository name (owner/repo)
            job_id: Job ID
            
        Returns:
            Job logs as string
        """
        try:
            endpoint = f'/repos/{repo_name}/actions/jobs/{job_id}/logs'
            
            # Logs endpoint returns plain text
            response = self.github._make_fallback_request('GET', endpoint, return_raw=True)
            return response.text if hasattr(response, 'text') else str(response)
            
        except Exception as e:
            self.logger.error(f"Failed to get job logs: {e}")
            return f"Error retrieving logs: {e}"
    
    def cancel_workflow_run(self, repo_name: str, run_id: int) -> bool:
        """
        Cancel a running workflow.
        
        Args:
            repo_name: Repository name (owner/repo)
            run_id: Workflow run ID
            
        Returns:
            True if cancellation successful
        """
        try:
            endpoint = f'/repos/{repo_name}/actions/runs/{run_id}/cancel'
            self.github._make_fallback_request('POST', endpoint)
            
            self.logger.info(f"Cancelled workflow run {run_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to cancel workflow run: {e}")
            return False
    
    def create_workflow_template(
        self,
        repo_name: str,
        template_name: str,
        language: str,
        project_type: str = 'web'
    ) -> Dict[str, Any]:
        """
        Create a GitHub Actions workflow template for a repository.
        
        Args:
            repo_name: Repository name (owner/repo)
            template_name: Name of the workflow template
            language: Programming language (python, javascript, etc.)
            project_type: Type of project (web, cli, library, etc.)
            
        Returns:
            Created workflow template data
        """
        try:
            # Generate workflow content based on language and project type
            workflow_content = self._generate_workflow_template(
                template_name, language, project_type
            )
            
            # Create .github/workflows directory structure
            workflow_path = f'.github/workflows/{template_name}.yml'
            
            # Create or update workflow file in repository
            result = self._create_workflow_file(repo_name, workflow_path, workflow_content)
            
            return {
                'success': True,
                'workflow_name': template_name,
                'workflow_path': workflow_path,
                'language': language,
                'project_type': project_type,
                'content': workflow_content,
                'created_at': datetime.now().isoformat(),
                'file_result': result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create workflow template: {e}")
            raise CICDIntegrationError(f"Failed to create workflow template: {e}")
    
    def _get_workflow_run_details(self, repo_name: str, run_id: int) -> Dict[str, Any]:
        """Get detailed information about a workflow run."""
        try:
            repo = self.github.get_repository(repo_name)
            
            if hasattr(repo, 'get_workflow_run'):  # PyGitHub object
                run = repo.get_workflow_run(run_id)
                return {
                    'id': run.id,
                    'name': run.name,
                    'status': run.status,
                    'conclusion': run.conclusion,
                    'workflow_id': run.workflow_id,
                    'head_branch': run.head_branch,
                    'head_sha': run.head_sha,
                    'run_number': run.run_number,
                    'created_at': run.created_at.isoformat() if run.created_at else None,
                    'updated_at': run.updated_at.isoformat() if run.updated_at else None,
                    'html_url': run.html_url
                }
            else:
                # Fallback API mode
                endpoint = f'/repos/{repo_name}/actions/runs/{run_id}'
                return self.github._make_fallback_request('GET', endpoint)
                
        except Exception as e:
            self.logger.error(f"Failed to get workflow run details: {e}")
            raise CICDIntegrationError(f"Failed to get workflow run details: {e}")
    
    def _generate_workflow_template(
        self, 
        name: str, 
        language: str, 
        project_type: str
    ) -> str:
        """Generate GitHub Actions workflow YAML content."""
        
        # Base workflow structure
        workflow = {
            'name': f'MeistroCraft {name.upper()}',
            'on': {
                'push': {
                    'branches': ['main', 'master', 'develop']
                },
                'pull_request': {
                    'branches': ['main', 'master']
                },
                'workflow_dispatch': {}
            },
            'jobs': {}
        }
        
        # Language-specific job configurations
        if language.lower() == 'python':
            workflow['jobs'] = self._get_python_workflow_jobs(project_type)
        elif language.lower() in ['javascript', 'typescript', 'node']:
            workflow['jobs'] = self._get_node_workflow_jobs(project_type)
        elif language.lower() in ['java']:
            workflow['jobs'] = self._get_java_workflow_jobs(project_type)
        else:
            # Generic workflow
            workflow['jobs'] = self._get_generic_workflow_jobs(language, project_type)
        
        return yaml.dump(workflow, default_flow_style=False, sort_keys=False)
    
    def _get_python_workflow_jobs(self, project_type: str) -> Dict[str, Any]:
        """Generate Python-specific workflow jobs."""
        return {
            'test': {
                'runs-on': 'ubuntu-latest',
                'strategy': {
                    'matrix': {
                        'python-version': ['3.8', '3.9', '3.10', '3.11']
                    }
                },
                'steps': [
                    {
                        'uses': 'actions/checkout@v4'
                    },
                    {
                        'name': 'Set up Python ${{ matrix.python-version }}',
                        'uses': 'actions/setup-python@v4',
                        'with': {
                            'python-version': '${{ matrix.python-version }}'
                        }
                    },
                    {
                        'name': 'Install dependencies',
                        'run': '\n'.join([
                            'python -m pip install --upgrade pip',
                            'pip install pytest pytest-cov flake8',
                            'if [ -f requirements.txt ]; then pip install -r requirements.txt; fi'
                        ])
                    },
                    {
                        'name': 'Lint with flake8',
                        'run': '\n'.join([
                            'flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics',
                            'flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics'
                        ])
                    },
                    {
                        'name': 'Test with pytest',
                        'run': 'pytest --cov=. --cov-report=xml'
                    },
                    {
                        'name': 'Upload coverage to Codecov',
                        'uses': 'codecov/codecov-action@v3',
                        'with': {
                            'file': './coverage.xml',
                            'flags': 'unittests',
                            'name': 'codecov-umbrella'
                        }
                    }
                ]
            },
            'security': {
                'runs-on': 'ubuntu-latest',
                'steps': [
                    {
                        'uses': 'actions/checkout@v4'
                    },
                    {
                        'name': 'Run security analysis',
                        'uses': 'github/super-linter@v4',
                        'env': {
                            'DEFAULT_BRANCH': 'main',
                            'GITHUB_TOKEN': '${{ secrets.GITHUB_TOKEN }}',
                            'VALIDATE_PYTHON_FLAKE8': 'true',
                            'VALIDATE_PYTHON_PYLINT': 'true'
                        }
                    }
                ]
            }
        }
    
    def _get_node_workflow_jobs(self, project_type: str) -> Dict[str, Any]:
        """Generate Node.js-specific workflow jobs."""
        return {
            'test': {
                'runs-on': 'ubuntu-latest',
                'strategy': {
                    'matrix': {
                        'node-version': ['16.x', '18.x', '20.x']
                    }
                },
                'steps': [
                    {
                        'uses': 'actions/checkout@v4'
                    },
                    {
                        'name': 'Use Node.js ${{ matrix.node-version }}',
                        'uses': 'actions/setup-node@v3',
                        'with': {
                            'node-version': '${{ matrix.node-version }}',
                            'cache': 'npm'
                        }
                    },
                    {
                        'name': 'Install dependencies',
                        'run': 'npm ci'
                    },
                    {
                        'name': 'Run linter',
                        'run': 'npm run lint'
                    },
                    {
                        'name': 'Run tests',
                        'run': 'npm test'
                    },
                    {
                        'name': 'Build project',
                        'run': 'npm run build'
                    }
                ]
            }
        }
    
    def _get_java_workflow_jobs(self, project_type: str) -> Dict[str, Any]:
        """Generate Java-specific workflow jobs."""
        return {
            'test': {
                'runs-on': 'ubuntu-latest',
                'steps': [
                    {
                        'uses': 'actions/checkout@v4'
                    },
                    {
                        'name': 'Set up JDK 11',
                        'uses': 'actions/setup-java@v3',
                        'with': {
                            'java-version': '11',
                            'distribution': 'temurin'
                        }
                    },
                    {
                        'name': 'Cache Maven packages',
                        'uses': 'actions/cache@v3',
                        'with': {
                            'path': '~/.m2',
                            'key': '${{ runner.os }}-m2-${{ hashFiles(\'**/pom.xml\') }}',
                            'restore-keys': '${{ runner.os }}-m2'
                        }
                    },
                    {
                        'name': 'Run tests',
                        'run': 'mvn clean test'
                    },
                    {
                        'name': 'Build project',
                        'run': 'mvn clean package'
                    }
                ]
            }
        }
    
    def _get_generic_workflow_jobs(self, language: str, project_type: str) -> Dict[str, Any]:
        """Generate generic workflow jobs."""
        return {
            'build': {
                'runs-on': 'ubuntu-latest',
                'steps': [
                    {
                        'uses': 'actions/checkout@v4'
                    },
                    {
                        'name': f'Build {language} project',
                        'run': 'echo "Add build commands for your project here"'
                    },
                    {
                        'name': f'Test {language} project',
                        'run': 'echo "Add test commands for your project here"'
                    }
                ]
            }
        }
    
    def _create_workflow_file(
        self, 
        repo_name: str, 
        file_path: str, 
        content: str
    ) -> Dict[str, Any]:
        """Create or update a workflow file in the repository."""
        try:
            repo = self.github.get_repository(repo_name)
            
            # Try to get existing file
            try:
                existing_file = repo.get_contents(file_path)
                # Update existing file
                result = repo.update_file(
                    path=file_path,
                    message=f"Update {file_path} workflow",
                    content=content,
                    sha=existing_file.sha,
                    branch="main"
                )
                action = "updated"
            except:
                # Create new file
                result = repo.create_file(
                    path=file_path,
                    message=f"Add {file_path} workflow",
                    content=content,
                    branch="main"
                )
                action = "created"
            
            return {
                'action': action,
                'path': file_path,
                'sha': result['commit'].sha if hasattr(result.get('commit', {}), 'sha') else 'unknown',
                'success': True
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create workflow file: {e}")
            return {
                'action': 'failed',
                'path': file_path,
                'error': str(e),
                'success': False
            }
    
    def _load_workflow_templates(self) -> Dict[str, str]:
        """Load predefined workflow templates."""
        return {
            'python': 'Python CI/CD with testing and linting',
            'javascript': 'Node.js CI/CD with npm and testing',
            'java': 'Java CI/CD with Maven',
            'generic': 'Generic CI/CD template'
        }


def create_cicd_integration(github_client: GitHubClient, config: Dict[str, Any] = None) -> Optional[GitHubActionsManager]:
    """
    Create and configure CI/CD integration with GitHub client.
    
    Args:
        github_client: Authenticated GitHub client instance
        config: Configuration dictionary
        
    Returns:
        GitHubActionsManager instance or None if GitHub is disabled
    """
    if not github_client or not github_client.is_authenticated():
        return None
        
    try:
        return GitHubActionsManager(github_client, config)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to create CI/CD integration: {e}")
        return None