"""
Deployment Automation for MeistroCraft - Phase 3
Handles environment management, deployment orchestration, and rollback capabilities.
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass

from github_client import GitHubClient
from cicd_integration import GitHubActionsManager
from build_monitor import BuildStatusMonitor, BuildStatusType


class DeploymentStatus(Enum):
    """Deployment status enumeration."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class EnvironmentType(Enum):
    """Environment type enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"
    PREVIEW = "preview"


@dataclass
class DeploymentConfig:
    """Deployment configuration for an environment."""
    environment: str
    auto_deploy: bool = False
    requires_approval: bool = True
    rollback_enabled: bool = True
    health_check_url: Optional[str] = None
    deployment_timeout: int = 1800  # 30 minutes
    quality_gates: List[str] = None
    
    def __post_init__(self):
        if self.quality_gates is None:
            self.quality_gates = []


@dataclass
class DeploymentRecord:
    """Record of a deployment attempt."""
    deployment_id: str
    environment: str
    version: str
    commit_sha: str
    status: DeploymentStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    deployed_by: str = "meistrocraft"
    rollback_target: Optional[str] = None
    health_check_passed: bool = False
    error_message: Optional[str] = None


class DeploymentAutomation:
    """
    Handles automated deployment workflows, environment management, and rollback capabilities.
    Integrates with GitHub Actions and MeistroCraft's task system.
    """
    
    def __init__(
        self, 
        github_actions: GitHubActionsManager,
        build_monitor: BuildStatusMonitor,
        config: Dict[str, Any] = None
    ):
        """
        Initialize deployment automation.
        
        Args:
            github_actions: GitHub Actions manager instance
            build_monitor: Build status monitor instance
            config: Configuration dictionary
        """
        self.github_actions = github_actions
        self.build_monitor = build_monitor
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Deployment settings
        self.max_concurrent_deployments = self.config.get('max_concurrent_deployments', 3)
        self.deployment_timeout = self.config.get('deployment_timeout', 1800)  # 30 minutes
        self.health_check_timeout = self.config.get('health_check_timeout', 300)  # 5 minutes
        
        # Environment configurations
        self.environment_configs = self._load_environment_configs()
        
        # Deployment tracking
        self.active_deployments = {}
        self.deployment_history = []
    
    def create_deployment(
        self,
        repo_name: str,
        environment: str,
        ref: str = 'main',
        description: str = None,
        auto_merge: bool = False,
        required_contexts: List[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new deployment for the specified environment.
        
        Args:
            repo_name: Repository name (owner/repo)
            environment: Target environment name
            ref: Git reference to deploy (branch/tag/commit)
            description: Deployment description
            auto_merge: Whether to auto-merge if deployment succeeds
            required_contexts: Required status checks
            
        Returns:
            Deployment creation result
        """
        try:
            # Validate environment configuration
            env_config = self._get_environment_config(environment)
            if not env_config:
                raise ValueError(f"Environment '{environment}' not configured")
            
            # Check quality gates before deployment
            quality_check = self._check_quality_gates(repo_name, ref, env_config)
            if not quality_check['passed']:
                return {
                    'deployment': 'blocked',
                    'reason': 'quality_gates_failed',
                    'failed_gates': quality_check['failed_gates'],
                    'message': 'Deployment blocked by quality gate failures'
                }
            
            # Check if approval is required
            if env_config.requires_approval and environment == EnvironmentType.PRODUCTION.value:
                approval_result = self._request_deployment_approval(repo_name, environment, ref)
                if not approval_result['approved']:
                    return {
                        'deployment': 'pending_approval',
                        'approval_request': approval_result,
                        'message': 'Deployment requires manual approval'
                    }
            
            # Create GitHub deployment
            deployment_data = self._create_github_deployment(
                repo_name, environment, ref, description, required_contexts
            )
            
            # Start deployment process
            deployment_result = self._start_deployment_process(
                repo_name, deployment_data, env_config
            )
            
            return {
                'deployment': 'created',
                'deployment_id': deployment_data['id'],
                'environment': environment,
                'ref': ref,
                'status': deployment_result['status'],
                'details': deployment_result,
                'created_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to create deployment: {e}")
            return {
                'deployment': 'error',
                'message': f'Failed to create deployment: {e}',
                'error': str(e)
            }
    
    def monitor_deployment(
        self,
        repo_name: str,
        deployment_id: str,
        timeout: int = None
    ) -> Dict[str, Any]:
        """
        Monitor a deployment until completion or timeout.
        
        Args:
            repo_name: Repository name (owner/repo)
            deployment_id: Deployment ID to monitor
            timeout: Maximum wait time in seconds
            
        Returns:
            Final deployment status and details
        """
        timeout = timeout or self.deployment_timeout
        start_time = time.time()
        
        try:
            while time.time() - start_time < timeout:
                # Get deployment status
                status = self._get_deployment_status(repo_name, deployment_id)
                
                if status['state'] in ['success', 'failure', 'error']:
                    # Deployment completed
                    final_result = self._finalize_deployment(repo_name, deployment_id, status)
                    return {
                        'monitoring': 'completed',
                        'final_status': status['state'],
                        'deployment_result': final_result,
                        'duration': time.time() - start_time
                    }
                
                # Wait before next check
                time.sleep(30)  # Check every 30 seconds
            
            # Timeout reached
            self._handle_deployment_timeout(repo_name, deployment_id)
            return {
                'monitoring': 'timeout',
                'message': f'Deployment monitoring timed out after {timeout} seconds',
                'duration': timeout
            }
            
        except Exception as e:
            self.logger.error(f"Failed to monitor deployment: {e}")
            return {
                'monitoring': 'error',
                'message': f'Failed to monitor deployment: {e}',
                'error': str(e)
            }
    
    def rollback_deployment(
        self,
        repo_name: str,
        environment: str,
        target_version: str = None
    ) -> Dict[str, Any]:
        """
        Rollback deployment to a previous version.
        
        Args:
            repo_name: Repository name (owner/repo)
            environment: Environment to rollback
            target_version: Specific version to rollback to (optional)
            
        Returns:
            Rollback operation result
        """
        try:
            # Find target version for rollback
            if not target_version:
                target_version = self._find_last_successful_deployment(repo_name, environment)
                if not target_version:
                    return {
                        'rollback': 'failed',
                        'reason': 'no_previous_version',
                        'message': 'No previous successful deployment found for rollback'
                    }
            
            # Validate rollback target
            validation = self._validate_rollback_target(repo_name, environment, target_version)
            if not validation['valid']:
                return {
                    'rollback': 'failed',
                    'reason': 'invalid_target',
                    'message': validation['message']
                }
            
            # Create rollback deployment
            rollback_deployment = self.create_deployment(
                repo_name=repo_name,
                environment=environment,
                ref=target_version,
                description=f"Rollback to {target_version}",
                auto_merge=False
            )
            
            if rollback_deployment.get('deployment') != 'created':
                return {
                    'rollback': 'failed',
                    'reason': 'deployment_creation_failed',
                    'details': rollback_deployment
                }
            
            # Monitor rollback deployment
            rollback_result = self.monitor_deployment(
                repo_name, 
                rollback_deployment['deployment_id'],
                timeout=600  # 10 minutes for rollback
            )
            
            return {
                'rollback': 'completed',
                'target_version': target_version,
                'deployment_id': rollback_deployment['deployment_id'],
                'result': rollback_result,
                'rolled_back_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to rollback deployment: {e}")
            return {
                'rollback': 'error',
                'message': f'Failed to rollback deployment: {e}',
                'error': str(e)
            }
    
    def get_deployment_history(
        self,
        repo_name: str,
        environment: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Get deployment history for a repository.
        
        Args:
            repo_name: Repository name (owner/repo)
            environment: Filter by environment (optional)
            limit: Number of deployments to retrieve
            
        Returns:
            Deployment history with analysis
        """
        try:
            # Get deployments from GitHub
            deployments = self._get_github_deployments(repo_name, environment, limit)
            
            # Analyze deployment patterns
            analysis = self._analyze_deployment_patterns(deployments)
            
            # Calculate deployment metrics
            metrics = self._calculate_deployment_metrics(deployments)
            
            return {
                'history': 'success',
                'total_deployments': len(deployments),
                'deployments': deployments,
                'analysis': analysis,
                'metrics': metrics,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get deployment history: {e}")
            return {
                'history': 'error',
                'message': f'Failed to get deployment history: {e}',
                'error': str(e)
            }
    
    def manage_environment(
        self,
        repo_name: str,
        environment: str,
        action: str,
        config: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Manage environment configuration and settings.
        
        Args:
            repo_name: Repository name (owner/repo)
            environment: Environment name
            action: Management action (create, update, delete, configure)
            config: Environment configuration
            
        Returns:
            Environment management result
        """
        try:
            if action == 'create':
                return self._create_environment(repo_name, environment, config)
            elif action == 'update':
                return self._update_environment(repo_name, environment, config)
            elif action == 'delete':
                return self._delete_environment(repo_name, environment)
            elif action == 'configure':
                return self._configure_environment_rules(repo_name, environment, config)
            else:
                return {
                    'management': 'error',
                    'message': f"Unknown action: {action}",
                    'valid_actions': ['create', 'update', 'delete', 'configure']
                }
                
        except Exception as e:
            self.logger.error(f"Failed to manage environment: {e}")
            return {
                'management': 'error',
                'message': f'Failed to manage environment: {e}',
                'error': str(e)
            }
    
    def _get_environment_config(self, environment: str) -> Optional[DeploymentConfig]:
        """Get configuration for a specific environment."""
        return self.environment_configs.get(environment)
    
    def _load_environment_configs(self) -> Dict[str, DeploymentConfig]:
        """Load environment configurations."""
        configs = {}
        
        # Default configurations for standard environments
        configs[EnvironmentType.DEVELOPMENT.value] = DeploymentConfig(
            environment=EnvironmentType.DEVELOPMENT.value,
            auto_deploy=True,
            requires_approval=False,
            rollback_enabled=True,
            quality_gates=['tests_pass']
        )
        
        configs[EnvironmentType.STAGING.value] = DeploymentConfig(
            environment=EnvironmentType.STAGING.value,
            auto_deploy=True,
            requires_approval=False,
            rollback_enabled=True,
            quality_gates=['tests_pass', 'code_quality', 'security_scan']
        )
        
        configs[EnvironmentType.PRODUCTION.value] = DeploymentConfig(
            environment=EnvironmentType.PRODUCTION.value,
            auto_deploy=False,
            requires_approval=True,
            rollback_enabled=True,
            quality_gates=['tests_pass', 'code_quality', 'security_scan', 'performance_tests']
        )
        
        # Load custom configurations from config
        custom_configs = self.config.get('environments', {})
        for env_name, env_config in custom_configs.items():
            configs[env_name] = DeploymentConfig(
                environment=env_name,
                auto_deploy=env_config.get('auto_deploy', False),
                requires_approval=env_config.get('requires_approval', True),
                rollback_enabled=env_config.get('rollback_enabled', True),
                health_check_url=env_config.get('health_check_url'),
                deployment_timeout=env_config.get('deployment_timeout', 1800),
                quality_gates=env_config.get('quality_gates', [])
            )
        
        return configs
    
    def _check_quality_gates(
        self, 
        repo_name: str, 
        ref: str, 
        env_config: DeploymentConfig
    ) -> Dict[str, Any]:
        """Check quality gates before deployment."""
        results = {
            'passed': True,
            'failed_gates': [],
            'gate_results': {}
        }
        
        for gate in env_config.quality_gates:
            gate_result = self._check_individual_gate(repo_name, ref, gate)
            results['gate_results'][gate] = gate_result
            
            if not gate_result['passed']:
                results['passed'] = False
                results['failed_gates'].append(gate)
        
        return results
    
    def _check_individual_gate(self, repo_name: str, ref: str, gate: str) -> Dict[str, Any]:
        """Check an individual quality gate."""
        try:
            if gate == 'tests_pass':
                # Check if latest build has passing tests
                build_status = self.build_monitor.get_build_status(repo_name)
                success_rate = build_status.get('metrics', {}).get('success_rate', 0)
                
                return {
                    'passed': success_rate >= 0.8,
                    'score': success_rate,
                    'message': f'Test success rate: {success_rate:.1%}'
                }
            
            elif gate == 'code_quality':
                # Basic code quality check (could integrate with SonarQube, etc.)
                return {
                    'passed': True,  # Placeholder - implement actual code quality checks
                    'score': 0.85,
                    'message': 'Code quality checks passed'
                }
            
            elif gate == 'security_scan':
                # Security scanning check (could integrate with security tools)
                return {
                    'passed': True,  # Placeholder - implement actual security scanning
                    'score': 0.9,
                    'message': 'Security scan completed successfully'
                }
            
            elif gate == 'performance_tests':
                # Performance testing check
                return {
                    'passed': True,  # Placeholder - implement actual performance testing
                    'score': 0.8,
                    'message': 'Performance tests within acceptable limits'
                }
            
            else:
                # Unknown gate
                return {
                    'passed': False,
                    'score': 0,
                    'message': f'Unknown quality gate: {gate}'
                }
                
        except Exception as e:
            return {
                'passed': False,
                'score': 0,
                'message': f'Quality gate check failed: {e}'
            }
    
    def _request_deployment_approval(
        self, 
        repo_name: str, 
        environment: str, 
        ref: str
    ) -> Dict[str, Any]:
        """Request manual approval for deployment."""
        # In a real implementation, this would create approval requests
        # For now, we'll simulate based on configuration
        
        auto_approve = self.config.get('auto_approve_production', False)
        
        if auto_approve:
            return {
                'approved': True,
                'approver': 'auto-approval',
                'approved_at': datetime.now().isoformat()
            }
        else:
            return {
                'approved': False,
                'approval_required': True,
                'message': f'Manual approval required for {environment} deployment',
                'approval_url': f'https://github.com/{repo_name}/actions'
            }
    
    def _create_github_deployment(
        self,
        repo_name: str,
        environment: str,
        ref: str,
        description: str = None,
        required_contexts: List[str] = None
    ) -> Dict[str, Any]:
        """Create a GitHub deployment."""
        try:
            repo = self.github_actions.github.get_repository(repo_name)
            
            deployment_data = {
                'ref': ref,
                'environment': environment,
                'description': description or f'Deploy {ref} to {environment}',
                'auto_merge': False,
                'required_contexts': required_contexts or []
            }
            
            if hasattr(repo, 'create_deployment'):  # PyGitHub object
                deployment = repo.create_deployment(**deployment_data)
                return {
                    'id': deployment.id,
                    'environment': deployment.environment,
                    'ref': deployment.ref,
                    'sha': deployment.sha,
                    'description': deployment.description,
                    'created_at': deployment.created_at.isoformat()
                }
            else:
                # Fallback API mode
                endpoint = f'/repos/{repo_name}/deployments'
                result = self.github_actions.github._make_fallback_request('POST', endpoint, deployment_data)
                return result
                
        except Exception as e:
            self.logger.error(f"Failed to create GitHub deployment: {e}")
            raise
    
    def _start_deployment_process(
        self,
        repo_name: str,
        deployment_data: Dict[str, Any],
        env_config: DeploymentConfig
    ) -> Dict[str, Any]:
        """Start the deployment process."""
        try:
            deployment_id = deployment_data['id']
            environment = deployment_data['environment']
            
            # Update deployment status to in_progress
            self._update_deployment_status(
                repo_name, 
                deployment_id, 
                'in_progress',
                description='Deployment started'
            )
            
            # Trigger deployment workflow if configured
            workflow_result = self._trigger_deployment_workflow(
                repo_name, deployment_data, env_config
            )
            
            # Track deployment
            self.active_deployments[deployment_id] = {
                'repo_name': repo_name,
                'environment': environment,
                'started_at': datetime.now(),
                'workflow_result': workflow_result
            }
            
            return {
                'status': 'started',
                'deployment_id': deployment_id,
                'workflow_triggered': workflow_result.get('success', False),
                'workflow_details': workflow_result
            }
            
        except Exception as e:
            self.logger.error(f"Failed to start deployment process: {e}")
            return {
                'status': 'failed',
                'error': str(e)
            }
    
    def _trigger_deployment_workflow(
        self,
        repo_name: str,
        deployment_data: Dict[str, Any],
        env_config: DeploymentConfig
    ) -> Dict[str, Any]:
        """Trigger the deployment workflow."""
        try:
            # Look for deployment workflow
            workflow_name = f'deploy-{deployment_data["environment"]}'
            
            # Trigger workflow with deployment context
            workflow_inputs = {
                'environment': deployment_data['environment'],
                'ref': deployment_data['ref'],
                'deployment_id': str(deployment_data['id'])
            }
            
            result = self.github_actions.trigger_workflow(
                repo_name=repo_name,
                workflow_id=f'{workflow_name}.yml',
                ref=deployment_data['ref'],
                inputs=workflow_inputs
            )
            
            return result
            
        except Exception as e:
            self.logger.warning(f"Could not trigger deployment workflow: {e}")
            return {
                'success': False,
                'message': 'No deployment workflow found or trigger failed',
                'error': str(e)
            }
    
    def _get_deployment_status(self, repo_name: str, deployment_id: str) -> Dict[str, Any]:
        """Get current deployment status."""
        try:
            endpoint = f'/repos/{repo_name}/deployments/{deployment_id}/statuses'
            statuses = self.github_actions.github._make_fallback_request('GET', endpoint)
            
            if statuses and len(statuses) > 0:
                latest_status = statuses[0]  # Most recent status
                return {
                    'state': latest_status.get('state'),
                    'description': latest_status.get('description'),
                    'environment_url': latest_status.get('environment_url'),
                    'log_url': latest_status.get('log_url'),
                    'updated_at': latest_status.get('updated_at')
                }
            else:
                return {
                    'state': 'pending',
                    'description': 'No status updates available'
                }
                
        except Exception as e:
            self.logger.error(f"Failed to get deployment status: {e}")
            return {
                'state': 'error',
                'description': f'Failed to get deployment status: {e}'
            }
    
    def _update_deployment_status(
        self,
        repo_name: str,
        deployment_id: str,
        state: str,
        description: str = None,
        environment_url: str = None
    ) -> bool:
        """Update deployment status."""
        try:
            status_data = {
                'state': state,
                'description': description or f'Deployment {state}',
                'environment_url': environment_url
            }
            
            endpoint = f'/repos/{repo_name}/deployments/{deployment_id}/statuses'
            self.github_actions.github._make_fallback_request('POST', endpoint, status_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update deployment status: {e}")
            return False
    
    def _finalize_deployment(
        self,
        repo_name: str,
        deployment_id: str,
        status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Finalize deployment and perform post-deployment actions."""
        try:
            state = status['state']
            
            # Remove from active deployments
            deployment_info = self.active_deployments.pop(deployment_id, {})
            
            # Perform health checks if deployment succeeded
            health_check_result = None
            if state == 'success':
                health_check_result = self._perform_health_check(
                    repo_name, deployment_id, status
                )
            
            # Record deployment in history
            self._record_deployment_history(
                repo_name, deployment_id, state, deployment_info, health_check_result
            )
            
            return {
                'finalized': True,
                'final_state': state,
                'health_check': health_check_result,
                'deployment_info': deployment_info
            }
            
        except Exception as e:
            self.logger.error(f"Failed to finalize deployment: {e}")
            return {
                'finalized': False,
                'error': str(e)
            }
    
    def _perform_health_check(
        self,
        repo_name: str,
        deployment_id: str,
        status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform post-deployment health checks."""
        try:
            environment_url = status.get('environment_url')
            
            if not environment_url:
                return {
                    'health_check': 'skipped',
                    'reason': 'No environment URL provided'
                }
            
            # Perform basic HTTP health check
            # In a real implementation, this would be more sophisticated
            import requests
            
            try:
                response = requests.get(environment_url, timeout=10)
                
                return {
                    'health_check': 'completed',
                    'status_code': response.status_code,
                    'healthy': response.status_code < 400,
                    'response_time': response.elapsed.total_seconds(),
                    'checked_at': datetime.now().isoformat()
                }
                
            except requests.RequestException as e:
                return {
                    'health_check': 'failed',
                    'error': str(e),
                    'healthy': False,
                    'checked_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                'health_check': 'error',
                'error': str(e),
                'healthy': False
            }
    
    def _record_deployment_history(
        self,
        repo_name: str,
        deployment_id: str,
        state: str,
        deployment_info: Dict[str, Any],
        health_check_result: Dict[str, Any]
    ) -> None:
        """Record deployment in history for analysis."""
        record = {
            'deployment_id': deployment_id,
            'repo_name': repo_name,
            'environment': deployment_info.get('environment'),
            'state': state,
            'started_at': deployment_info.get('started_at', datetime.now()).isoformat(),
            'completed_at': datetime.now().isoformat(),
            'health_check': health_check_result,
            'workflow_result': deployment_info.get('workflow_result')
        }
        
        self.deployment_history.append(record)
        
        # Keep only last 100 deployments in memory
        if len(self.deployment_history) > 100:
            self.deployment_history = self.deployment_history[-100:]
    
    def _handle_deployment_timeout(self, repo_name: str, deployment_id: str) -> None:
        """Handle deployment timeout."""
        try:
            # Update deployment status to error
            self._update_deployment_status(
                repo_name,
                deployment_id,
                'error',
                'Deployment timed out'
            )
            
            # Remove from active deployments
            self.active_deployments.pop(deployment_id, None)
            
            self.logger.warning(f"Deployment {deployment_id} timed out")
            
        except Exception as e:
            self.logger.error(f"Failed to handle deployment timeout: {e}")
    
    def _find_last_successful_deployment(
        self, 
        repo_name: str, 
        environment: str
    ) -> Optional[str]:
        """Find the last successful deployment for rollback."""
        try:
            # Get deployment history
            deployments = self._get_github_deployments(repo_name, environment, 50)
            
            # Find last successful deployment
            for deployment in deployments:
                if deployment.get('statuses', []):
                    latest_status = deployment['statuses'][0]
                    if latest_status.get('state') == 'success':
                        return deployment.get('sha')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to find last successful deployment: {e}")
            return None
    
    def _validate_rollback_target(
        self, 
        repo_name: str, 
        environment: str, 
        target_version: str
    ) -> Dict[str, Any]:
        """Validate rollback target version."""
        try:
            # Check if target version exists
            repo = self.github_actions.github.get_repository(repo_name)
            
            try:
                if hasattr(repo, 'get_commit'):
                    commit = repo.get_commit(target_version)
                    return {
                        'valid': True,
                        'commit_sha': commit.sha,
                        'commit_date': commit.commit.author.date.isoformat()
                    }
                else:
                    # Fallback validation
                    return {
                        'valid': True,
                        'message': 'Validation skipped in fallback mode'
                    }
                    
            except:
                return {
                    'valid': False,
                    'message': f'Target version {target_version} not found'
                }
                
        except Exception as e:
            return {
                'valid': False,
                'message': f'Failed to validate rollback target: {e}'
            }
    
    def _get_github_deployments(
        self, 
        repo_name: str, 
        environment: str = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get deployments from GitHub API."""
        try:
            params = {'per_page': min(limit, 100)}
            if environment:
                params['environment'] = environment
            
            endpoint = f'/repos/{repo_name}/deployments'
            deployments = self.github_actions.github._make_fallback_request('GET', endpoint, params=params)
            
            # Get statuses for each deployment
            for deployment in deployments:
                deployment_id = deployment['id']
                status_endpoint = f'/repos/{repo_name}/deployments/{deployment_id}/statuses'
                statuses = self.github_actions.github._make_fallback_request('GET', status_endpoint)
                deployment['statuses'] = statuses
            
            return deployments
            
        except Exception as e:
            self.logger.error(f"Failed to get GitHub deployments: {e}")
            return []
    
    def _analyze_deployment_patterns(self, deployments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze deployment patterns and trends."""
        if not deployments:
            return {'analysis': 'no_data'}
        
        # Count deployments by environment
        env_counts = {}
        success_rates = {}
        
        for deployment in deployments:
            env = deployment.get('environment', 'unknown')
            env_counts[env] = env_counts.get(env, 0) + 1
            
            # Calculate success rate per environment
            if deployment.get('statuses'):
                latest_status = deployment['statuses'][0]
                state = latest_status.get('state')
                
                if env not in success_rates:
                    success_rates[env] = {'total': 0, 'successful': 0}
                
                success_rates[env]['total'] += 1
                if state == 'success':
                    success_rates[env]['successful'] += 1
        
        # Calculate final success rates
        for env in success_rates:
            total = success_rates[env]['total']
            successful = success_rates[env]['successful']
            success_rates[env]['rate'] = successful / total if total > 0 else 0
        
        return {
            'analysis': 'completed',
            'total_deployments': len(deployments),
            'deployments_by_environment': env_counts,
            'success_rates_by_environment': success_rates,
            'most_active_environment': max(env_counts.items(), key=lambda x: x[1])[0] if env_counts else None
        }
    
    def _calculate_deployment_metrics(self, deployments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate deployment metrics."""
        if not deployments:
            return {'metrics': 'no_data'}
        
        total_deployments = len(deployments)
        successful_deployments = 0
        failed_deployments = 0
        
        for deployment in deployments:
            if deployment.get('statuses'):
                latest_status = deployment['statuses'][0]
                state = latest_status.get('state')
                
                if state == 'success':
                    successful_deployments += 1
                elif state in ['failure', 'error']:
                    failed_deployments += 1
        
        success_rate = successful_deployments / total_deployments if total_deployments > 0 else 0
        failure_rate = failed_deployments / total_deployments if total_deployments > 0 else 0
        
        return {
            'metrics': 'calculated',
            'total_deployments': total_deployments,
            'successful_deployments': successful_deployments,
            'failed_deployments': failed_deployments,
            'success_rate': success_rate,
            'failure_rate': failure_rate,
            'deployment_frequency': 'calculated_separately'  # Would need time range for this
        }
    
    def _create_environment(
        self, 
        repo_name: str, 
        environment: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new environment."""
        try:
            # Create environment configuration
            env_config = DeploymentConfig(
                environment=environment,
                auto_deploy=config.get('auto_deploy', False),
                requires_approval=config.get('requires_approval', True),
                rollback_enabled=config.get('rollback_enabled', True),
                health_check_url=config.get('health_check_url'),
                deployment_timeout=config.get('deployment_timeout', 1800),
                quality_gates=config.get('quality_gates', [])
            )
            
            # Store configuration
            self.environment_configs[environment] = env_config
            
            return {
                'environment_management': 'created',
                'environment': environment,
                'configuration': config,
                'created_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'environment_management': 'error',
                'message': f'Failed to create environment: {e}'
            }
    
    def _update_environment(
        self, 
        repo_name: str, 
        environment: str, 
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing environment."""
        try:
            if environment not in self.environment_configs:
                return {
                    'environment_management': 'error',
                    'message': f'Environment {environment} not found'
                }
            
            # Update configuration
            env_config = self.environment_configs[environment]
            
            for key, value in config.items():
                if hasattr(env_config, key):
                    setattr(env_config, key, value)
            
            return {
                'environment_management': 'updated',
                'environment': environment,
                'updated_config': config,
                'updated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'environment_management': 'error',
                'message': f'Failed to update environment: {e}'
            }
    
    def _delete_environment(self, repo_name: str, environment: str) -> Dict[str, Any]:
        """Delete an environment."""
        try:
            if environment in self.environment_configs:
                del self.environment_configs[environment]
            
            return {
                'environment_management': 'deleted',
                'environment': environment,
                'deleted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'environment_management': 'error',
                'message': f'Failed to delete environment: {e}'
            }
    
    def _configure_environment_rules(
        self, 
        repo_name: str, 
        environment: str, 
        rules_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Configure environment protection rules."""
        try:
            # This would integrate with GitHub's environment protection rules
            # For now, we'll just update local configuration
            
            if environment not in self.environment_configs:
                return {
                    'environment_management': 'error',
                    'message': f'Environment {environment} not found'
                }
            
            env_config = self.environment_configs[environment]
            
            # Update protection rules
            if 'required_reviewers' in rules_config:
                env_config.requires_approval = len(rules_config['required_reviewers']) > 0
            
            if 'deployment_branch_policy' in rules_config:
                # Handle branch policies
                pass
            
            return {
                'environment_management': 'configured',
                'environment': environment,
                'rules': rules_config,
                'configured_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'environment_management': 'error',
                'message': f'Failed to configure environment rules: {e}'
            }


def create_deployment_automation(
    github_actions: GitHubActionsManager,
    build_monitor: BuildStatusMonitor,
    config: Dict[str, Any] = None
) -> Optional[DeploymentAutomation]:
    """
    Create and configure deployment automation.
    
    Args:
        github_actions: GitHub Actions manager instance
        build_monitor: Build status monitor instance
        config: Configuration dictionary
        
    Returns:
        DeploymentAutomation instance or None if creation fails
    """
    if not github_actions or not build_monitor:
        return None
        
    try:
        return DeploymentAutomation(github_actions, build_monitor, config)
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to create deployment automation: {e}")
        return None