"""
Build Status Monitor for MeistroCraft - Phase 3
Tracks pipeline status, analyzes build results, and provides intelligent insights.
"""

import json
import logging
import time
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

from github_client import GitHubClient
from cicd_integration import GitHubActionsManager, WorkflowStatus, WorkflowConclusion


class BuildStatusType(Enum):
    """Build status enumeration."""
    SUCCESS = "success"
    FAILURE = "failure"
    PENDING = "pending"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class BuildResult:
    """Represents a complete build result with analysis."""
    run_id: int
    status: BuildStatusType
    conclusion: str
    duration: float
    branch: str
    commit_sha: str
    workflow_name: str
    jobs: List[Dict[str, Any]]
    test_results: Optional[Dict[str, Any]] = None
    coverage_data: Optional[Dict[str, Any]] = None
    security_issues: List[Dict[str, Any]] = None
    performance_metrics: Optional[Dict[str, Any]] = None
    created_at: str = None
    html_url: str = None


class BuildStatusMonitor:
    """
    Monitors build status across GitHub Actions workflows.
    Provides intelligent analysis and recommendations for build improvements.
    """
    
    def __init__(self, github_actions: GitHubActionsManager, config: Dict[str, Any] = None):
        """
        Initialize build status monitor.
        
        Args:
            github_actions: GitHub Actions manager instance
            config: Configuration dictionary
        """
        self.github_actions = github_actions
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Build monitoring settings
        self.failure_threshold = self.config.get('failure_threshold', 3)  # consecutive failures
        self.success_rate_threshold = self.config.get('success_rate_threshold', 0.8)  # 80%
        self.performance_degradation_threshold = self.config.get('perf_threshold', 0.3)  # 30% slower
        
        # Cache for build history
        self._build_cache = {}
        self._metrics_cache = {}
    
    def get_build_status(self, repo_name: str, branch: str = None) -> Dict[str, Any]:
        """
        Get current build status for a repository.
        
        Args:
            repo_name: Repository name (owner/repo)
            branch: Specific branch to check (optional)
            
        Returns:
            Build status summary with current state and trends
        """
        try:
            # Use batched request if GitHub client supports it
            if hasattr(self.github_actions.github, 'get_multiple_workflow_runs_batch'):
                batch_results = self.github_actions.github.get_multiple_workflow_runs_batch([repo_name], 50)
                runs = batch_results.get(repo_name, [])
                
                # Filter by branch if specified
                if branch:
                    runs = [run for run in runs if run.get('head_branch') == branch]
            else:
                # Fallback to original method
                runs = self.github_actions.get_workflow_runs(
                    repo_name=repo_name,
                    branch=branch,
                    limit=50
                )
            
            if not runs:
                return {
                    'status': 'no_builds',
                    'message': 'No workflow runs found',
                    'branches': {},
                    'overall_health': 'unknown'
                }
            
            # Analyze builds by branch
            branch_analysis = self._analyze_builds_by_branch(runs)
            
            # Calculate overall health metrics
            health_metrics = self._calculate_health_metrics(runs)
            
            # Detect trends and issues
            trends = self._detect_build_trends(runs)
            
            # Generate recommendations
            recommendations = self._generate_build_recommendations(branch_analysis, health_metrics, trends)
            
            return {
                'status': health_metrics['overall_status'],
                'overall_health': health_metrics['health_score'],
                'branches': branch_analysis,
                'metrics': health_metrics,
                'trends': trends,
                'recommendations': recommendations,
                'last_updated': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get build status: {e}")
            return {
                'status': 'error',
                'message': f'Failed to retrieve build status: {e}',
                'error': str(e)
            }
    
    def analyze_build_failure(self, repo_name: str, run_id: int) -> Dict[str, Any]:
        """
        Analyze a failed build to identify root causes and suggest fixes.
        
        Args:
            repo_name: Repository name (owner/repo)
            run_id: Failed workflow run ID
            
        Returns:
            Detailed failure analysis with suggested fixes
        """
        try:
            # Get workflow run details
            run_details = self.github_actions._get_workflow_run_details(repo_name, run_id)
            
            if run_details.get('conclusion') != WorkflowConclusion.FAILURE.value:
                return {
                    'analysis': 'not_failed',
                    'message': 'Workflow run is not in failed state',
                    'current_status': run_details.get('status'),
                    'current_conclusion': run_details.get('conclusion')
                }
            
            # Get job details and logs
            jobs_analysis = self._analyze_failed_jobs(repo_name, run_id)
            
            # Identify failure patterns
            failure_patterns = self._identify_failure_patterns(jobs_analysis)
            
            # Generate fix suggestions
            fix_suggestions = self._generate_fix_suggestions(failure_patterns, jobs_analysis)
            
            # Check for common issues
            common_issues = self._check_common_issues(jobs_analysis)
            
            return {
                'analysis': 'completed',
                'run_id': run_id,
                'workflow_name': run_details.get('name'),
                'failure_summary': failure_patterns,
                'failed_jobs': jobs_analysis,
                'common_issues': common_issues,
                'fix_suggestions': fix_suggestions,
                'priority': self._calculate_failure_priority(failure_patterns),
                'analyzed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze build failure: {e}")
            return {
                'analysis': 'error',
                'message': f'Failed to analyze build failure: {e}',
                'error': str(e)
            }
    
    def get_build_metrics(
        self, 
        repo_name: str, 
        time_range: int = 30,
        branch: str = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive build metrics for a repository.
        
        Args:
            repo_name: Repository name (owner/repo)
            time_range: Number of days to analyze
            branch: Specific branch to analyze (optional)
            
        Returns:
            Detailed build metrics and performance data
        """
        try:
            # Get workflow runs for the time range
            from datetime import timezone
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=time_range)
            runs = self.github_actions.get_workflow_runs(
                repo_name=repo_name,
                branch=branch,
                limit=200
            )
            
            # Filter by date range
            filtered_runs = [
                run for run in runs
                if self._parse_datetime(run.get('created_at', '')) and self._parse_datetime(run.get('created_at', '')) > cutoff_date
            ]
            
            if not filtered_runs:
                return {
                    'metrics': 'no_data',
                    'message': f'No builds found in the last {time_range} days'
                }
            
            # Calculate metrics
            success_rate = self._calculate_success_rate(filtered_runs)
            average_duration = self._calculate_average_duration(filtered_runs)
            failure_rate = self._calculate_failure_rate(filtered_runs)
            build_frequency = self._calculate_build_frequency(filtered_runs, time_range)
            
            # Performance trends
            performance_trends = self._calculate_performance_trends(filtered_runs)
            
            # Reliability metrics
            reliability_metrics = self._calculate_reliability_metrics(filtered_runs)
            
            # Resource usage analysis
            resource_analysis = self._analyze_resource_usage(filtered_runs)
            
            return {
                'metrics': 'success',
                'time_range_days': time_range,
                'total_builds': len(filtered_runs),
                'success_rate': success_rate,
                'failure_rate': failure_rate,
                'average_duration_minutes': average_duration,
                'build_frequency_per_day': build_frequency,
                'performance_trends': performance_trends,
                'reliability': reliability_metrics,
                'resource_usage': resource_analysis,
                'generated_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get build metrics: {e}")
            return {
                'metrics': 'error',
                'message': f'Failed to calculate build metrics: {e}',
                'error': str(e)
            }
    
    def monitor_build_health(
        self, 
        repo_name: str, 
        alert_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """
        Monitor overall build health and generate alerts for degradation.
        
        Args:
            repo_name: Repository name (owner/repo)
            alert_threshold: Health score threshold for alerts (0.0-1.0)
            
        Returns:
            Health monitoring report with alerts and recommendations
        """
        try:
            # Get recent build status
            status = self.get_build_status(repo_name)
            
            if status.get('status') == 'error':
                return {
                    'health_monitoring': 'error',
                    'message': 'Failed to retrieve build status for health monitoring'
                }
            
            health_score = status.get('overall_health', 0)
            alerts = []
            
            # Check health threshold
            if health_score < alert_threshold:
                alerts.append({
                    'type': 'health_degradation',
                    'severity': 'high' if health_score < 0.5 else 'medium',
                    'message': f'Build health score ({health_score:.2f}) below threshold ({alert_threshold})',
                    'current_score': health_score,
                    'threshold': alert_threshold
                })
            
            # Check for consecutive failures
            metrics = status.get('metrics', {})
            consecutive_failures = metrics.get('consecutive_failures', 0)
            
            if consecutive_failures >= self.failure_threshold:
                alerts.append({
                    'type': 'consecutive_failures',
                    'severity': 'critical',
                    'message': f'{consecutive_failures} consecutive build failures detected',
                    'count': consecutive_failures,
                    'threshold': self.failure_threshold
                })
            
            # Check success rate
            success_rate = metrics.get('success_rate', 1.0)
            if success_rate < self.success_rate_threshold:
                alerts.append({
                    'type': 'low_success_rate',
                    'severity': 'high',
                    'message': f'Success rate ({success_rate:.2f}) below threshold ({self.success_rate_threshold})',
                    'current_rate': success_rate,
                    'threshold': self.success_rate_threshold
                })
            
            # Check for performance degradation
            trends = status.get('trends', {})
            perf_trend = trends.get('duration_trend', 0)
            
            if perf_trend > self.performance_degradation_threshold:
                alerts.append({
                    'type': 'performance_degradation',
                    'severity': 'medium',
                    'message': f'Build duration increased by {perf_trend:.1%}',
                    'trend': perf_trend,
                    'threshold': self.performance_degradation_threshold
                })
            
            # Generate action items based on alerts
            action_items = self._generate_health_action_items(alerts, status)
            
            return {
                'health_monitoring': 'completed',
                'health_score': health_score,
                'alert_threshold': alert_threshold,
                'alerts': alerts,
                'alert_count': len(alerts),
                'action_items': action_items,
                'status_summary': status,
                'monitored_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Failed to monitor build health: {e}")
            return {
                'health_monitoring': 'error',
                'message': f'Failed to monitor build health: {e}',
                'error': str(e)
            }
    
    def _analyze_builds_by_branch(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze builds grouped by branch."""
        branch_data = {}
        
        for run in runs:
            branch = run.get('head_branch', 'unknown')
            
            if branch not in branch_data:
                branch_data[branch] = {
                    'total_builds': 0,
                    'successful_builds': 0,
                    'failed_builds': 0,
                    'last_build': None,
                    'last_success': None,
                    'consecutive_failures': 0
                }
            
            branch_info = branch_data[branch]
            branch_info['total_builds'] += 1
            
            status = run.get('conclusion')
            if status == WorkflowConclusion.SUCCESS.value:
                branch_info['successful_builds'] += 1
                if not branch_info['last_success']:
                    branch_info['last_success'] = run
                branch_info['consecutive_failures'] = 0
            elif status == WorkflowConclusion.FAILURE.value:
                branch_info['failed_builds'] += 1
                branch_info['consecutive_failures'] += 1
            
            if not branch_info['last_build']:
                branch_info['last_build'] = run
        
        # Calculate success rates
        for branch, data in branch_data.items():
            total = data['total_builds']
            data['success_rate'] = data['successful_builds'] / total if total > 0 else 0
            data['failure_rate'] = data['failed_builds'] / total if total > 0 else 0
        
        return branch_data
    
    def _calculate_health_metrics(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall health metrics."""
        if not runs:
            return {'overall_status': 'no_data', 'health_score': 0}
        
        total_runs = len(runs)
        successful = sum(1 for run in runs if run.get('conclusion') == WorkflowConclusion.SUCCESS.value)
        failed = sum(1 for run in runs if run.get('conclusion') == WorkflowConclusion.FAILURE.value)
        
        success_rate = successful / total_runs
        
        # Calculate consecutive failures from most recent builds
        consecutive_failures = 0
        for run in runs:
            if run.get('conclusion') == WorkflowConclusion.FAILURE.value:
                consecutive_failures += 1
            else:
                break
        
        # Calculate health score (0.0 - 1.0)
        health_score = success_rate
        
        # Penalty for consecutive failures
        if consecutive_failures > 0:
            penalty = min(consecutive_failures * 0.1, 0.5)
            health_score = max(0, health_score - penalty)
        
        # Determine overall status
        if health_score >= 0.8:
            overall_status = 'healthy'
        elif health_score >= 0.6:
            overall_status = 'warning'
        else:
            overall_status = 'critical'
        
        return {
            'overall_status': overall_status,
            'health_score': health_score,
            'success_rate': success_rate,
            'total_runs': total_runs,
            'successful_runs': successful,
            'failed_runs': failed,
            'consecutive_failures': consecutive_failures
        }
    
    def _detect_build_trends(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Detect trends in build performance and reliability."""
        if len(runs) < 10:
            return {'trend_analysis': 'insufficient_data', 'message': 'Need at least 10 builds for trend analysis'}
        
        # Split into recent and historical groups
        recent_runs = runs[:10]
        historical_runs = runs[10:20] if len(runs) >= 20 else runs[10:]
        
        if not historical_runs:
            return {'trend_analysis': 'insufficient_historical_data'}
        
        # Calculate duration trends
        recent_avg_duration = self._calculate_average_duration(recent_runs)
        historical_avg_duration = self._calculate_average_duration(historical_runs)
        
        duration_trend = 0
        if historical_avg_duration > 0:
            duration_trend = (recent_avg_duration - historical_avg_duration) / historical_avg_duration
        
        # Calculate success rate trends
        recent_success_rate = self._calculate_success_rate(recent_runs)
        historical_success_rate = self._calculate_success_rate(historical_runs)
        
        success_rate_trend = recent_success_rate - historical_success_rate
        
        return {
            'trend_analysis': 'completed',
            'duration_trend': duration_trend,
            'success_rate_trend': success_rate_trend,
            'recent_avg_duration': recent_avg_duration,
            'historical_avg_duration': historical_avg_duration,
            'recent_success_rate': recent_success_rate,
            'historical_success_rate': historical_success_rate,
            'trend_direction': {
                'duration': 'improving' if duration_trend < -0.1 else 'degrading' if duration_trend > 0.1 else 'stable',
                'success_rate': 'improving' if success_rate_trend > 0.1 else 'degrading' if success_rate_trend < -0.1 else 'stable'
            }
        }
    
    def _generate_build_recommendations(
        self, 
        branch_analysis: Dict[str, Any], 
        health_metrics: Dict[str, Any], 
        trends: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable recommendations for build improvements."""
        recommendations = []
        
        # Health-based recommendations
        health_score = health_metrics.get('health_score', 0)
        if health_score < 0.6:
            recommendations.append({
                'type': 'health_improvement',
                'priority': 'high',
                'title': 'Improve Build Health',
                'description': f'Build health score is {health_score:.2f}. Focus on reducing failures.',
                'actions': [
                    'Review recent failed builds for common patterns',
                    'Update dependencies and fix breaking changes',
                    'Improve test coverage and stability'
                ]
            })
        
        # Consecutive failure recommendations
        consecutive_failures = health_metrics.get('consecutive_failures', 0)
        if consecutive_failures >= 3:
            recommendations.append({
                'type': 'failure_resolution',
                'priority': 'critical',
                'title': 'Resolve Consecutive Failures',
                'description': f'{consecutive_failures} consecutive build failures detected.',
                'actions': [
                    'Immediately investigate the latest failed build',
                    'Consider creating a hotfix branch',
                    'Review recent changes for breaking modifications'
                ]
            })
        
        # Performance recommendations
        if trends.get('trend_analysis') == 'completed':
            duration_trend = trends.get('duration_trend', 0)
            if duration_trend > 0.2:  # 20% slower
                recommendations.append({
                    'type': 'performance_optimization',
                    'priority': 'medium',
                    'title': 'Optimize Build Performance',
                    'description': f'Build duration has increased by {duration_trend:.1%}.',
                    'actions': [
                        'Review and optimize workflow steps',
                        'Consider caching dependencies',
                        'Parallelize independent jobs'
                    ]
                })
        
        # Branch-specific recommendations
        for branch, data in branch_analysis.items():
            if data['success_rate'] < 0.7 and data['total_builds'] >= 5:
                recommendations.append({
                    'type': 'branch_health',
                    'priority': 'medium',
                    'title': f'Improve {branch} Branch Stability',
                    'description': f'Branch {branch} has {data["success_rate"]:.1%} success rate.',
                    'actions': [
                        f'Review failed builds on {branch} branch',
                        'Consider branch protection rules',
                        'Ensure proper testing before merges'
                    ]
                })
        
        return recommendations
    
    def _analyze_failed_jobs(self, repo_name: str, run_id: int) -> List[Dict[str, Any]]:
        """Analyze failed jobs within a workflow run."""
        try:
            # Get jobs for the workflow run
            endpoint = f'/repos/{repo_name}/actions/runs/{run_id}/jobs'
            jobs_response = self.github_actions.github._make_fallback_request('GET', endpoint)
            jobs = jobs_response.get('jobs', [])
            
            failed_jobs = []
            for job in jobs:
                if job.get('conclusion') == WorkflowConclusion.FAILURE.value:
                    job_analysis = {
                        'id': job.get('id'),
                        'name': job.get('name'),
                        'conclusion': job.get('conclusion'),
                        'started_at': job.get('started_at'),
                        'completed_at': job.get('completed_at'),
                        'steps': []
                    }
                    
                    # Analyze failed steps
                    for step in job.get('steps', []):
                        if step.get('conclusion') == WorkflowConclusion.FAILURE.value:
                            step_analysis = {
                                'name': step.get('name'),
                                'conclusion': step.get('conclusion'),
                                'number': step.get('number'),
                                'started_at': step.get('started_at'),
                                'completed_at': step.get('completed_at')
                            }
                            job_analysis['steps'].append(step_analysis)
                    
                    # Get job logs for analysis
                    try:
                        logs = self.github_actions.get_workflow_job_logs(repo_name, job['id'])
                        job_analysis['logs_snippet'] = logs[-1000:] if logs else "No logs available"
                        job_analysis['error_patterns'] = self._extract_error_patterns(logs)
                    except:
                        job_analysis['logs_snippet'] = "Failed to retrieve logs"
                        job_analysis['error_patterns'] = []
                    
                    failed_jobs.append(job_analysis)
            
            return failed_jobs
            
        except Exception as e:
            self.logger.error(f"Failed to analyze failed jobs: {e}")
            return []
    
    def _identify_failure_patterns(self, jobs_analysis: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify common failure patterns from job analysis."""
        patterns = {
            'dependency_issues': 0,
            'test_failures': 0,
            'compilation_errors': 0,
            'timeout_issues': 0,
            'permission_issues': 0,
            'network_issues': 0,
            'configuration_errors': 0
        }
        
        error_keywords = {
            'dependency_issues': ['dependency', 'package not found', 'module not found', 'import error'],
            'test_failures': ['test failed', 'assertion error', 'test assertion', 'failed tests'],
            'compilation_errors': ['compilation failed', 'syntax error', 'build failed'],
            'timeout_issues': ['timeout', 'timed out', 'exceeded time limit'],
            'permission_issues': ['permission denied', 'access denied', 'forbidden'],
            'network_issues': ['connection failed', 'network error', 'connection timeout'],
            'configuration_errors': ['config error', 'configuration', 'missing environment']
        }
        
        for job in jobs_analysis:
            logs = job.get('logs_snippet', '').lower()
            error_patterns = job.get('error_patterns', [])
            
            for pattern_type, keywords in error_keywords.items():
                if any(keyword in logs for keyword in keywords):
                    patterns[pattern_type] += 1
        
        # Determine primary failure cause
        primary_cause = max(patterns.items(), key=lambda x: x[1])
        
        return {
            'patterns': patterns,
            'primary_cause': primary_cause[0] if primary_cause[1] > 0 else 'unknown',
            'primary_cause_count': primary_cause[1],
            'total_jobs_analyzed': len(jobs_analysis)
        }
    
    def _generate_fix_suggestions(
        self, 
        failure_patterns: Dict[str, Any], 
        jobs_analysis: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate specific fix suggestions based on failure patterns."""
        suggestions = []
        primary_cause = failure_patterns.get('primary_cause', 'unknown')
        
        fix_templates = {
            'dependency_issues': {
                'title': 'Fix Dependency Issues',
                'priority': 'high',
                'suggestions': [
                    'Update requirements.txt or package.json with correct versions',
                    'Check for deprecated packages and update to supported versions',
                    'Verify all dependencies are properly declared',
                    'Consider using dependency lock files'
                ]
            },
            'test_failures': {
                'title': 'Resolve Test Failures',
                'priority': 'high',
                'suggestions': [
                    'Review failing test cases and fix underlying issues',
                    'Update test data and mocks if needed',
                    'Check for environment-specific test issues',
                    'Consider improving test isolation'
                ]
            },
            'compilation_errors': {
                'title': 'Fix Compilation Errors',
                'priority': 'critical',
                'suggestions': [
                    'Review syntax errors and code structure',
                    'Check for missing imports or declarations',
                    'Verify compiler/interpreter version compatibility',
                    'Run local build to reproduce and fix issues'
                ]
            },
            'timeout_issues': {
                'title': 'Resolve Timeout Issues',
                'priority': 'medium',
                'suggestions': [
                    'Optimize slow-running operations',
                    'Increase timeout limits if necessary',
                    'Parallelize independent operations',
                    'Consider breaking large operations into smaller chunks'
                ]
            },
            'permission_issues': {
                'title': 'Fix Permission Issues',
                'priority': 'medium',
                'suggestions': [
                    'Check GitHub token permissions',
                    'Verify workflow file permissions',
                    'Review repository secrets and variables',
                    'Update action versions that may have permission changes'
                ]
            },
            'network_issues': {
                'title': 'Resolve Network Issues',
                'priority': 'low',
                'suggestions': [
                    'Add retry logic for network operations',
                    'Use alternative package repositories if available',
                    'Check for rate limiting issues',
                    'Consider caching network resources'
                ]
            }
        }
        
        if primary_cause in fix_templates:
            suggestions.append(fix_templates[primary_cause])
        
        # Add general suggestions
        suggestions.append({
            'title': 'General Debugging Steps',
            'priority': 'low',
            'suggestions': [
                'Review the complete build logs for additional context',
                'Run the build locally to reproduce the issue',
                'Check recent commits for potential breaking changes',
                'Compare with the last successful build'
            ]
        })
        
        return suggestions
    
    def _check_common_issues(self, jobs_analysis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Check for common CI/CD issues."""
        common_issues = []
        
        # Check for multiple job failures
        if len(jobs_analysis) > 1:
            common_issues.append({
                'type': 'multiple_job_failures',
                'severity': 'high',
                'description': f'{len(jobs_analysis)} jobs failed in this workflow',
                'recommendation': 'This suggests a fundamental issue affecting multiple components'
            })
        
        # Check for step failure patterns
        total_failed_steps = sum(len(job.get('steps', [])) for job in jobs_analysis)
        if total_failed_steps > 3:
            common_issues.append({
                'type': 'multiple_step_failures',
                'severity': 'medium',
                'description': f'{total_failed_steps} steps failed across jobs',
                'recommendation': 'Review workflow structure and step dependencies'
            })
        
        return common_issues
    
    def _calculate_failure_priority(self, failure_patterns: Dict[str, Any]) -> str:
        """Calculate priority level for failure resolution."""
        primary_cause = failure_patterns.get('primary_cause', 'unknown')
        
        high_priority_causes = ['compilation_errors', 'dependency_issues', 'test_failures']
        medium_priority_causes = ['timeout_issues', 'permission_issues', 'configuration_errors']
        
        if primary_cause in high_priority_causes:
            return 'high'
        elif primary_cause in medium_priority_causes:
            return 'medium'
        else:
            return 'low'
    
    def _calculate_success_rate(self, runs: List[Dict[str, Any]]) -> float:
        """Calculate success rate for a list of runs."""
        if not runs:
            return 0.0
        
        successful = sum(1 for run in runs if run.get('conclusion') == WorkflowConclusion.SUCCESS.value)
        return successful / len(runs)
    
    def _calculate_failure_rate(self, runs: List[Dict[str, Any]]) -> float:
        """Calculate failure rate for a list of runs."""
        if not runs:
            return 0.0
        
        failed = sum(1 for run in runs if run.get('conclusion') == WorkflowConclusion.FAILURE.value)
        return failed / len(runs)
    
    def _calculate_average_duration(self, runs: List[Dict[str, Any]]) -> float:
        """Calculate average duration in minutes for a list of runs."""
        if not runs:
            return 0.0
        
        total_duration = 0
        count = 0
        
        for run in runs:
            created_at = self._parse_datetime(run.get('created_at', ''))
            updated_at = self._parse_datetime(run.get('updated_at', ''))
            
            if created_at and updated_at:
                duration = (updated_at - created_at).total_seconds() / 60
                total_duration += duration
                count += 1
        
        return total_duration / count if count > 0 else 0.0
    
    def _calculate_build_frequency(self, runs: List[Dict[str, Any]], days: int) -> float:
        """Calculate builds per day for the given time period."""
        return len(runs) / days if days > 0 else 0.0
    
    def _calculate_performance_trends(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate performance trends over time."""
        if len(runs) < 10:
            return {'trend': 'insufficient_data'}
        
        # Split into recent and historical
        recent = runs[:5]
        historical = runs[-5:]
        
        recent_avg = self._calculate_average_duration(recent)
        historical_avg = self._calculate_average_duration(historical)
        
        trend = 0
        if historical_avg > 0:
            trend = (recent_avg - historical_avg) / historical_avg
        
        return {
            'trend': 'improving' if trend < -0.1 else 'degrading' if trend > 0.1 else 'stable',
            'trend_percentage': trend,
            'recent_avg_duration': recent_avg,
            'historical_avg_duration': historical_avg
        }
    
    def _calculate_reliability_metrics(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate reliability metrics."""
        if not runs:
            return {'reliability_score': 0}
        
        # Calculate MTBF (Mean Time Between Failures)
        failures = [i for i, run in enumerate(runs) if run.get('conclusion') == WorkflowConclusion.FAILURE.value]
        
        if len(failures) < 2:
            mtbf = len(runs)  # No failures or only one failure
        else:
            intervals = [failures[i] - failures[i-1] for i in range(1, len(failures))]
            mtbf = sum(intervals) / len(intervals)
        
        success_rate = self._calculate_success_rate(runs)
        reliability_score = min(success_rate + (mtbf / len(runs)), 1.0)
        
        return {
            'reliability_score': reliability_score,
            'mean_time_between_failures': mtbf,
            'total_failures': len(failures),
            'success_rate': success_rate
        }
    
    def _analyze_resource_usage(self, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze resource usage patterns."""
        # For now, return basic analysis
        # In a full implementation, this would analyze job resource consumption
        return {
            'analysis': 'basic',
            'total_runs': len(runs),
            'avg_duration_minutes': self._calculate_average_duration(runs),
            'recommendation': 'Monitor resource usage through GitHub Actions insights'
        }
    
    def _generate_health_action_items(
        self, 
        alerts: List[Dict[str, Any]], 
        status: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate actionable items based on health alerts."""
        action_items = []
        
        for alert in alerts:
            alert_type = alert.get('type')
            severity = alert.get('severity', 'medium')
            
            if alert_type == 'consecutive_failures':
                action_items.append({
                    'priority': 'critical',
                    'action': 'Investigate Latest Failure',
                    'description': 'Analyze the most recent failed build to identify root cause',
                    'timeline': 'immediate'
                })
            
            elif alert_type == 'health_degradation':
                action_items.append({
                    'priority': 'high',
                    'action': 'Review Build Stability',
                    'description': 'Examine recent changes and test coverage',
                    'timeline': 'within 24 hours'
                })
            
            elif alert_type == 'low_success_rate':
                action_items.append({
                    'priority': 'high',
                    'action': 'Improve Test Reliability',
                    'description': 'Focus on fixing flaky tests and improving code quality',
                    'timeline': 'within 48 hours'
                })
            
            elif alert_type == 'performance_degradation':
                action_items.append({
                    'priority': 'medium',
                    'action': 'Optimize Build Performance',
                    'description': 'Review workflow efficiency and dependency management',
                    'timeline': 'within 1 week'
                })
        
        return action_items
    
    def _parse_datetime(self, date_string: str) -> Optional[datetime]:
        """Parse datetime string with various formats."""
        if not date_string:
            return None
        
        try:
            # GitHub API typically returns ISO format
            if date_string.endswith('Z'):
                date_string = date_string[:-1] + '+00:00'
            return datetime.fromisoformat(date_string)
        except:
            try:
                # Handle naive datetime strings
                dt = datetime.strptime(date_string, '%Y-%m-%dT%H:%M:%SZ')
                # Make timezone-aware for consistency
                from datetime import timezone
                return dt.replace(tzinfo=timezone.utc)
            except:
                try:
                    # Handle simple ISO format
                    dt = datetime.fromisoformat(date_string)
                    if dt.tzinfo is None:
                        from datetime import timezone
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except:
                    return None
    
    def _extract_error_patterns(self, logs: str) -> List[str]:
        """Extract error patterns from build logs."""
        if not logs:
            return []
        
        error_patterns = []
        lines = logs.split('\n')
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ['error:', 'failed:', 'exception:', 'fatal:']):
                error_patterns.append(line.strip())
        
        return error_patterns[-10:]  # Return last 10 error patterns
    
    def get_batch_build_status(self, repo_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get build status for multiple repositories using optimized batching.
        
        Args:
            repo_names: List of repository names (owner/repo)
            
        Returns:
            Dictionary mapping repo names to their build status
        """
        if not repo_names:
            return {}
        
        try:
            # Use batched GitHub API requests for better performance
            if hasattr(self.github_actions.github, 'get_multiple_workflow_runs_batch'):
                self.logger.info(f"Using optimized batch request for {len(repo_names)} repositories")
                batch_results = self.github_actions.github.get_multiple_workflow_runs_batch(repo_names, 50)
            else:
                # Fallback to individual requests
                self.logger.info(f"Using individual requests for {len(repo_names)} repositories")
                batch_results = {}
                for repo in repo_names:
                    try:
                        runs = self.github_actions.get_workflow_runs(repo_name=repo, limit=50)
                        batch_results[repo] = runs
                    except Exception as e:
                        self.logger.error(f"Failed to get runs for {repo}: {e}")
                        batch_results[repo] = []
            
            # Process each repository's data
            results = {}
            for repo_name, runs in batch_results.items():
                try:
                    if not runs:
                        results[repo_name] = {
                            'status': 'no_builds',
                            'message': 'No workflow runs found',
                            'overall_health': 'unknown'
                        }
                        continue
                    
                    # Analyze builds by branch
                    branch_analysis = self._analyze_builds_by_branch(runs)
                    
                    # Calculate overall health metrics
                    health_metrics = self._calculate_health_metrics(runs)
                    
                    # Detect trends and issues
                    trends = self._detect_build_trends(runs)
                    
                    results[repo_name] = {
                        'status': health_metrics['overall_status'],
                        'overall_health': health_metrics['health_score'],
                        'branches': branch_analysis,
                        'metrics': health_metrics,
                        'trends': trends,
                        'last_updated': datetime.now().isoformat()
                    }
                    
                except Exception as e:
                    self.logger.error(f"Failed to analyze builds for {repo_name}: {e}")
                    results[repo_name] = {
                        'status': 'error',
                        'message': f'Failed to analyze builds: {e}',
                        'error': str(e)
                    }
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get batch build status: {e}")
            return {repo: {'status': 'error', 'error': str(e)} for repo in repo_names}
    
    async def get_batch_build_status_async(self, repo_names: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get build status for multiple repositories using high-performance async processing.
        
        Args:
            repo_names: List of repository names (owner/repo)
            
        Returns:
            Dictionary mapping repo names to their build status
        """
        if not repo_names:
            return {}
        
        start_time = time.time()
        self.logger.info(f"Starting async batch build status for {len(repo_names)} repositories")
        
        try:
            # Prepare async requests for workflow runs
            requests = []
            for repo_name in repo_names:
                requests.append({
                    'method': 'GET',
                    'endpoint': f'/repos/{repo_name}/actions/runs',
                    'params': {'per_page': 50},
                    'repo_name': repo_name  # Add context for processing
                })
            
            # Execute async batch requests if available
            if hasattr(self.github_actions.github, 'batch_github_requests_async'):
                self.logger.info("Using enhanced async batch processing")
                batch_results = await self.github_actions.github.batch_github_requests_async(
                    requests, max_concurrent=5
                )
                
                # Process async results
                results = {}
                for i, result in enumerate(batch_results):
                    repo_name = requests[i]['repo_name']
                    
                    if result.get('success', False):
                        runs = result.get('data', {}).get('workflow_runs', [])
                        results[repo_name] = await self._analyze_builds_async(repo_name, runs)
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        self.logger.error(f"Failed to get runs for {repo_name}: {error_msg}")
                        results[repo_name] = {
                            'status': 'error',
                            'message': f'Failed to fetch builds: {error_msg}',
                            'error': error_msg
                        }
            else:
                # Fallback to sync batch processing
                self.logger.info("Falling back to sync batch processing")
                results = self.get_batch_build_status(repo_names)
            
            # Log performance metrics
            total_time = time.time() - start_time
            self.logger.info(f"Async batch processing completed in {total_time:.2f}s for {len(repo_names)} repos")
            
            # Record performance metric
            if hasattr(self.github_actions.github, '_record_performance_metric'):
                self.github_actions.github._record_performance_metric(
                    'batch_build_status_time',
                    total_time * 1000,  # Convert to ms
                    {
                        'repo_count': len(repo_names),
                        'file': 'build_monitor.py',
                        'function': 'get_batch_build_status_async'
                    }
                )
            
            return results
            
        except Exception as e:
            self.logger.error(f"Failed to get async batch build status: {e}")
            return {repo: {'status': 'error', 'error': str(e)} for repo in repo_names}
    
    async def _analyze_builds_async(self, repo_name: str, runs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Async version of build analysis for better performance."""
        try:
            if not runs:
                return {
                    'status': 'no_builds',
                    'message': 'No workflow runs found',
                    'overall_health': 'unknown'
                }
            
            # Use existing analysis methods (these are fast and don't need async)
            branch_analysis = self._analyze_builds_by_branch(runs)
            health_metrics = self._calculate_health_metrics(runs)
            trends = self._detect_build_trends(runs)
            
            return {
                'status': health_metrics['overall_status'],
                'overall_health': health_metrics['health_score'],
                'branches': branch_analysis,
                'metrics': health_metrics,
                'trends': trends,
                'last_updated': datetime.now().isoformat(),
                'processed_async': True
            }
            
        except Exception as e:
            self.logger.error(f"Failed to analyze builds for {repo_name}: {e}")
            return {
                'status': 'error',
                'message': f'Failed to analyze builds: {e}',
                'error': str(e)
            }
    
    def get_optimization_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for build monitoring."""
        github_metrics = {}
        if hasattr(self.github_actions.github, 'get_performance_metrics'):
            github_metrics = self.github_actions.github.get_performance_metrics()
        
        return {
            'github_client_metrics': github_metrics,
            'cache_stats': {
                'build_cache_size': len(self._build_cache),
                'metrics_cache_size': len(self._metrics_cache)
            },
            'monitoring_config': {
                'failure_threshold': self.failure_threshold,
                'success_rate_threshold': self.success_rate_threshold,
                'performance_degradation_threshold': self.performance_degradation_threshold
            }
        }