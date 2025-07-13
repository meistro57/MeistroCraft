#!/usr/bin/env python3
"""
Comprehensive test suite for Phase 3: CI/CD Pipeline Integration.
Tests GitHub Actions integration, build monitoring, and deployment automation.
"""

import json
import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestGitHubActionsManager(unittest.TestCase):
    """Test the GitHub Actions Manager for CI/CD integration."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock GitHub client
        self.mock_github = Mock()
        self.mock_github.is_authenticated.return_value = True
        self.mock_github.get_repository.return_value = Mock()
        
        # Test configuration
        self.test_config = {
            'max_workflow_wait': 1800,
            'workflow_check_interval': 30,
            'openai_api_key': 'test_key'
        }
    
    def test_github_actions_manager_initialization(self):
        """Test GitHubActionsManager initialization."""
        from cicd_integration import GitHubActionsManager
        
        manager = GitHubActionsManager(self.mock_github, self.test_config)
        
        self.assertEqual(manager.github, self.mock_github)
        self.assertEqual(manager.config, self.test_config)
        self.assertEqual(manager.max_wait_time, 1800)
        self.assertEqual(manager.check_interval, 30)
        self.assertIsNotNone(manager.workflow_templates)
    
    def test_get_workflow_runs(self):
        """Test getting workflow runs."""
        from cicd_integration import GitHubActionsManager
        
        manager = GitHubActionsManager(self.mock_github, self.test_config)
        
        # Mock workflow runs data
        mock_runs = [
            {
                'id': 123,
                'name': 'CI',
                'status': 'completed',
                'conclusion': 'success',
                'workflow_id': 456,
                'head_branch': 'main',
                'head_sha': 'abc123',
                'run_number': 1,
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:05:00Z',
                'html_url': 'https://github.com/test/repo/actions/runs/123'
            }
        ]
        
        # Mock repository
        mock_repo = Mock()
        manager.github.get_repository.return_value = mock_repo
        
        # Test with fallback mode (no PyGitHub) - mock the hasattr check
        with patch('cicd_integration.hasattr', return_value=False):
            manager.github._make_fallback_request = Mock(return_value={'workflow_runs': mock_runs})
            
            runs = manager.get_workflow_runs('test/repo', limit=10)
        
        self.assertEqual(len(runs), 1)
        self.assertEqual(runs[0]['id'], 123)
        self.assertEqual(runs[0]['status'], 'completed')
        self.assertEqual(runs[0]['conclusion'], 'success')
    
    def test_trigger_workflow(self):
        """Test triggering a workflow."""
        from cicd_integration import GitHubActionsManager
        
        manager = GitHubActionsManager(self.mock_github, self.test_config)
        
        # Mock successful trigger
        manager.github._make_fallback_request = Mock()
        
        result = manager.trigger_workflow(
            repo_name='test/repo',
            workflow_id='ci.yml',
            ref='main',
            inputs={'test': 'value'}
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['workflow_id'], 'ci.yml')
        self.assertEqual(result['ref'], 'main')
        self.assertEqual(result['inputs'], {'test': 'value'})
    
    def test_workflow_template_generation(self):
        """Test workflow template generation."""
        from cicd_integration import GitHubActionsManager
        
        manager = GitHubActionsManager(self.mock_github, self.test_config)
        
        # Test Python workflow template
        template = manager._generate_workflow_template('ci', 'python', 'web')
        
        self.assertIn('name: MeistroCraft CI', template)
        self.assertIn('python-version', template)
        self.assertIn('pytest', template)
        self.assertIn('flake8', template)
        
        # Test Node.js workflow template
        template = manager._generate_workflow_template('ci', 'javascript', 'web')
        
        self.assertIn('name: MeistroCraft CI', template)
        self.assertIn('node-version', template)
        self.assertIn('npm ci', template)
        
        # Test Java workflow template
        template = manager._generate_workflow_template('ci', 'java', 'web')
        
        self.assertIn('name: MeistroCraft CI', template)
        self.assertIn('java-version', template)
        self.assertIn('mvn', template)
    
    def test_create_workflow_template(self):
        """Test creating workflow template in repository."""
        from cicd_integration import GitHubActionsManager
        
        manager = GitHubActionsManager(self.mock_github, self.test_config)
        
        # Mock repository and file operations
        mock_repo = Mock()
        manager.github.get_repository.return_value = mock_repo
        mock_repo.create_file.return_value = {'commit': Mock(sha='abc123')}
        
        result = manager.create_workflow_template(
            repo_name='test/repo',
            template_name='ci',
            language='python',
            project_type='web'
        )
        
        self.assertTrue(result['success'])
        self.assertEqual(result['workflow_name'], 'ci')
        self.assertEqual(result['language'], 'python')
        self.assertEqual(result['project_type'], 'web')
        self.assertIn('content', result)


class TestBuildStatusMonitor(unittest.TestCase):
    """Test the Build Status Monitor functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock GitHub Actions manager
        self.mock_actions = Mock()
        self.mock_actions.get_workflow_runs.return_value = []
        
        # Test configuration
        self.test_config = {
            'failure_threshold': 3,
            'success_rate_threshold': 0.8,
            'perf_threshold': 0.3
        }
    
    def test_build_monitor_initialization(self):
        """Test BuildStatusMonitor initialization."""
        from build_monitor import BuildStatusMonitor
        
        monitor = BuildStatusMonitor(self.mock_actions, self.test_config)
        
        self.assertEqual(monitor.github_actions, self.mock_actions)
        self.assertEqual(monitor.config, self.test_config)
        self.assertEqual(monitor.failure_threshold, 3)
        self.assertEqual(monitor.success_rate_threshold, 0.8)
        self.assertEqual(monitor.performance_degradation_threshold, 0.3)
    
    def test_get_build_status_no_builds(self):
        """Test getting build status with no builds."""
        from build_monitor import BuildStatusMonitor
        
        monitor = BuildStatusMonitor(self.mock_actions, self.test_config)
        
        # Mock empty workflow runs
        self.mock_actions.get_workflow_runs.return_value = []
        
        status = monitor.get_build_status('test/repo')
        
        self.assertEqual(status['status'], 'no_builds')
        self.assertEqual(status['overall_health'], 'unknown')
    
    def test_get_build_status_with_builds(self):
        """Test getting build status with successful builds."""
        from build_monitor import BuildStatusMonitor
        
        monitor = BuildStatusMonitor(self.mock_actions, self.test_config)
        
        # Mock successful workflow runs
        mock_runs = [
            {
                'conclusion': 'success',
                'head_branch': 'main',
                'created_at': '2024-01-01T00:00:00Z',
                'updated_at': '2024-01-01T00:05:00Z'
            },
            {
                'conclusion': 'success',
                'head_branch': 'main',
                'created_at': '2024-01-01T01:00:00Z',
                'updated_at': '2024-01-01T01:05:00Z'
            }
        ]
        
        self.mock_actions.get_workflow_runs.return_value = mock_runs
        
        status = monitor.get_build_status('test/repo')
        
        self.assertEqual(status['status'], 'healthy')
        self.assertGreater(status['overall_health'], 0.8)
        self.assertIn('branches', status)
        self.assertIn('metrics', status)
    
    def test_analyze_build_failure(self):
        """Test analyzing build failures."""
        from build_monitor import BuildStatusMonitor
        
        monitor = BuildStatusMonitor(self.mock_actions, self.test_config)
        
        # Mock failed workflow run details
        mock_run_details = {
            'conclusion': 'failure',
            'name': 'CI',
            'status': 'completed'
        }
        
        monitor.github_actions._get_workflow_run_details = Mock(return_value=mock_run_details)
        monitor.github_actions.github._make_fallback_request = Mock(return_value={'jobs': []})
        
        analysis = monitor.analyze_build_failure('test/repo', 123)
        
        self.assertEqual(analysis['analysis'], 'completed')
        self.assertEqual(analysis['run_id'], 123)
        self.assertIn('failure_summary', analysis)
        self.assertIn('fix_suggestions', analysis)
    
    def test_build_metrics_calculation(self):
        """Test build metrics calculation."""
        from build_monitor import BuildStatusMonitor
        
        monitor = BuildStatusMonitor(self.mock_actions, self.test_config)
        
        # Mock workflow runs with mixed results (all timezone-aware)
        from datetime import datetime, timezone
        base_time = datetime.now(timezone.utc)
        
        mock_runs = [
            {
                'conclusion': 'success',
                'created_at': (base_time - timedelta(hours=2)).isoformat(),
                'updated_at': (base_time - timedelta(hours=2) + timedelta(minutes=5)).isoformat()
            },
            {
                'conclusion': 'failure',
                'created_at': (base_time - timedelta(hours=1)).isoformat(),
                'updated_at': (base_time - timedelta(hours=1) + timedelta(minutes=3)).isoformat()
            },
            {
                'conclusion': 'success',
                'created_at': base_time.isoformat(),
                'updated_at': (base_time + timedelta(minutes=7)).isoformat()
            }
        ]
        
        self.mock_actions.get_workflow_runs.return_value = mock_runs
        
        metrics = monitor.get_build_metrics('test/repo', time_range=7)
        
        self.assertEqual(metrics['metrics'], 'success')
        self.assertEqual(metrics['total_builds'], 3)
        self.assertAlmostEqual(metrics['success_rate'], 2/3, places=2)
        self.assertAlmostEqual(metrics['failure_rate'], 1/3, places=2)
        self.assertGreater(metrics['average_duration_minutes'], 0)
    
    def test_health_monitoring_alerts(self):
        """Test health monitoring with alerts."""
        from build_monitor import BuildStatusMonitor
        
        monitor = BuildStatusMonitor(self.mock_actions, self.test_config)
        
        # Mock failing builds to trigger alerts
        mock_runs = [
            {'conclusion': 'failure', 'head_branch': 'main'},
            {'conclusion': 'failure', 'head_branch': 'main'},
            {'conclusion': 'failure', 'head_branch': 'main'}
        ]
        
        self.mock_actions.get_workflow_runs.return_value = mock_runs
        
        health = monitor.monitor_build_health('test/repo', alert_threshold=0.7)
        
        self.assertEqual(health['health_monitoring'], 'completed')
        self.assertLess(health['health_score'], 0.7)
        self.assertGreater(len(health['alerts']), 0)
        self.assertIn('action_items', health)


class TestDeploymentAutomation(unittest.TestCase):
    """Test the Deployment Automation functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Mock dependencies
        self.mock_actions = Mock()
        self.mock_build_monitor = Mock()
        
        # Test configuration
        self.test_config = {
            'max_concurrent_deployments': 3,
            'deployment_timeout': 1800,
            'auto_approve_production': False,
            'environments': {
                'staging': {
                    'auto_deploy': True,
                    'requires_approval': False,
                    'quality_gates': ['tests_pass']
                }
            }
        }
    
    def test_deployment_automation_initialization(self):
        """Test DeploymentAutomation initialization."""
        from deployment_automation import DeploymentAutomation
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        self.assertEqual(automation.github_actions, self.mock_actions)
        self.assertEqual(automation.build_monitor, self.mock_build_monitor)
        self.assertEqual(automation.config, self.test_config)
        self.assertEqual(automation.max_concurrent_deployments, 3)
        self.assertEqual(automation.deployment_timeout, 1800)
    
    def test_environment_configurations(self):
        """Test environment configuration loading."""
        from deployment_automation import DeploymentAutomation, EnvironmentType
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        # Check default environments
        dev_config = automation._get_environment_config(EnvironmentType.DEVELOPMENT.value)
        self.assertIsNotNone(dev_config)
        self.assertTrue(dev_config.auto_deploy)
        self.assertFalse(dev_config.requires_approval)
        
        prod_config = automation._get_environment_config(EnvironmentType.PRODUCTION.value)
        self.assertIsNotNone(prod_config)
        self.assertFalse(prod_config.auto_deploy)
        self.assertTrue(prod_config.requires_approval)
        
        # Check custom environment from config
        staging_config = automation._get_environment_config('staging')
        self.assertIsNotNone(staging_config)
        self.assertTrue(staging_config.auto_deploy)
        self.assertFalse(staging_config.requires_approval)
    
    def test_quality_gates_checking(self):
        """Test quality gates validation."""
        from deployment_automation import DeploymentAutomation, DeploymentConfig
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        # Mock build monitor to return good status
        self.mock_build_monitor.get_build_status.return_value = {
            'metrics': {'success_rate': 0.9}
        }
        
        env_config = DeploymentConfig(
            environment='test',
            quality_gates=['tests_pass', 'code_quality']
        )
        
        result = automation._check_quality_gates('test/repo', 'main', env_config)
        
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['failed_gates']), 0)
        self.assertIn('gate_results', result)
    
    def test_create_deployment_success(self):
        """Test successful deployment creation."""
        from deployment_automation import DeploymentAutomation
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        # Mock quality gates passing
        automation._check_quality_gates = Mock(return_value={'passed': True, 'failed_gates': []})
        automation._request_deployment_approval = Mock(return_value={'approved': True})
        automation._create_github_deployment = Mock(return_value={'id': 123, 'environment': 'staging'})
        automation._start_deployment_process = Mock(return_value={'status': 'started'})
        
        result = automation.create_deployment(
            repo_name='test/repo',
            environment='staging',
            ref='main'
        )
        
        self.assertEqual(result['deployment'], 'created')
        self.assertEqual(result['deployment_id'], 123)
        self.assertEqual(result['environment'], 'staging')
    
    def test_create_deployment_blocked_by_quality_gates(self):
        """Test deployment blocked by quality gates."""
        from deployment_automation import DeploymentAutomation
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        # Mock quality gates failing
        automation._check_quality_gates = Mock(return_value={
            'passed': False, 
            'failed_gates': ['tests_pass']
        })
        
        result = automation.create_deployment(
            repo_name='test/repo',
            environment='staging',
            ref='main'
        )
        
        self.assertEqual(result['deployment'], 'blocked')
        self.assertEqual(result['reason'], 'quality_gates_failed')
        self.assertIn('tests_pass', result['failed_gates'])
    
    def test_rollback_deployment(self):
        """Test deployment rollback functionality."""
        from deployment_automation import DeploymentAutomation
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        # Mock successful rollback
        automation._find_last_successful_deployment = Mock(return_value='abc123')
        automation._validate_rollback_target = Mock(return_value={'valid': True})
        automation.create_deployment = Mock(return_value={
            'deployment': 'created',
            'deployment_id': 456
        })
        automation.monitor_deployment = Mock(return_value={
            'monitoring': 'completed',
            'final_status': 'success'
        })
        
        result = automation.rollback_deployment(
            repo_name='test/repo',
            environment='production'
        )
        
        self.assertEqual(result['rollback'], 'completed')
        self.assertEqual(result['target_version'], 'abc123')
        self.assertEqual(result['deployment_id'], 456)
    
    def test_deployment_history_analysis(self):
        """Test deployment history analysis."""
        from deployment_automation import DeploymentAutomation
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        # Mock deployment history
        mock_deployments = [
            {
                'id': 1,
                'environment': 'production',
                'statuses': [{'state': 'success'}]
            },
            {
                'id': 2,
                'environment': 'staging',
                'statuses': [{'state': 'failure'}]
            },
            {
                'id': 3,
                'environment': 'production',
                'statuses': [{'state': 'success'}]
            }
        ]
        
        automation._get_github_deployments = Mock(return_value=mock_deployments)
        
        history = automation.get_deployment_history('test/repo')
        
        self.assertEqual(history['history'], 'success')
        self.assertEqual(history['total_deployments'], 3)
        self.assertIn('analysis', history)
        self.assertIn('metrics', history)
        
        # Check analysis results
        analysis = history['analysis']
        self.assertEqual(analysis['total_deployments'], 3)
        self.assertIn('deployments_by_environment', analysis)
        self.assertIn('success_rates_by_environment', analysis)
    
    def test_environment_management(self):
        """Test environment management operations."""
        from deployment_automation import DeploymentAutomation
        
        automation = DeploymentAutomation(
            self.mock_actions, 
            self.mock_build_monitor, 
            self.test_config
        )
        
        # Test creating environment
        result = automation.manage_environment(
            repo_name='test/repo',
            environment='test-env',
            action='create',
            config={
                'auto_deploy': True,
                'requires_approval': False,
                'quality_gates': ['tests_pass']
            }
        )
        
        self.assertEqual(result['environment_management'], 'created')
        self.assertEqual(result['environment'], 'test-env')
        
        # Verify environment was added
        env_config = automation._get_environment_config('test-env')
        self.assertIsNotNone(env_config)
        self.assertTrue(env_config.auto_deploy)
        self.assertFalse(env_config.requires_approval)
        
        # Test updating environment
        result = automation.manage_environment(
            repo_name='test/repo',
            environment='test-env',
            action='update',
            config={'auto_deploy': False}
        )
        
        self.assertEqual(result['environment_management'], 'updated')
        
        # Test deleting environment
        result = automation.manage_environment(
            repo_name='test/repo',
            environment='test-env',
            action='delete'
        )
        
        self.assertEqual(result['environment_management'], 'deleted')


class TestPhase3Integration(unittest.TestCase):
    """Test Phase 3 integration with main MeistroCraft system."""
    
    def setUp(self):
        """Set up test environment."""
        self.mock_github = Mock()
        self.mock_github.is_authenticated.return_value = True
        
        self.test_config = {
            'github_token': 'test_token',
            'openai_api_key': 'test_openai_key',
            'max_workflow_wait': 1800
        }
    
    def test_cicd_integration_creation(self):
        """Test CI/CD integration factory function."""
        from cicd_integration import create_cicd_integration
        
        # Test with valid GitHub client
        integration = create_cicd_integration(self.mock_github, self.test_config)
        self.assertIsNotNone(integration)
        
        # Test with None GitHub client
        integration = create_cicd_integration(None, self.test_config)
        self.assertIsNone(integration)
        
        # Test with unauthenticated GitHub client
        self.mock_github.is_authenticated.return_value = False
        integration = create_cicd_integration(self.mock_github, self.test_config)
        self.assertIsNone(integration)
    
    def test_deployment_automation_creation(self):
        """Test deployment automation factory function."""
        from deployment_automation import create_deployment_automation
        from cicd_integration import GitHubActionsManager
        from build_monitor import BuildStatusMonitor
        
        # Create dependencies
        actions_manager = GitHubActionsManager(self.mock_github, self.test_config)
        build_monitor = BuildStatusMonitor(actions_manager, self.test_config)
        
        # Test with valid dependencies
        automation = create_deployment_automation(actions_manager, build_monitor, self.test_config)
        self.assertIsNotNone(automation)
        
        # Test with None dependencies
        automation = create_deployment_automation(None, None, self.test_config)
        self.assertIsNone(automation)
    
    def test_phase3_workflow_template_types(self):
        """Test different workflow template types."""
        from cicd_integration import GitHubActionsManager
        
        manager = GitHubActionsManager(self.mock_github, self.test_config)
        
        # Test different language templates
        languages = ['python', 'javascript', 'java']
        project_types = ['web', 'cli', 'library']
        
        for language in languages:
            for project_type in project_types:
                template = manager._generate_workflow_template('ci', language, project_type)
                
                # Verify basic template structure
                self.assertIn('name:', template)
                self.assertIn('on:', template)
                self.assertIn('jobs:', template)
                self.assertIn('runs-on: ubuntu-latest', template)
                
                # Verify language-specific content
                if language == 'python':
                    self.assertIn('python-version', template)
                elif language in ['javascript', 'typescript', 'node']:
                    self.assertIn('node-version', template)
                elif language == 'java':
                    self.assertIn('java-version', template)


def run_phase3_tests():
    """Run comprehensive Phase 3 CI/CD tests."""
    print("🧪 Phase 3: CI/CD Pipeline Integration - Comprehensive Test Suite")
    print("=" * 70)
    
    # Test modules
    test_modules = [
        TestGitHubActionsManager,
        TestBuildStatusMonitor,
        TestDeploymentAutomation,
        TestPhase3Integration
    ]
    
    total_tests = 0
    total_passed = 0
    
    for test_module in test_modules:
        print(f"\n📋 Running {test_module.__name__}...")
        print("-" * 50)
        
        suite = unittest.TestLoader().loadTestsFromTestCase(test_module)
        runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, 'w'))
        result = runner.run(suite)
        
        module_tests = result.testsRun
        module_passed = module_tests - len(result.failures) - len(result.errors)
        
        total_tests += module_tests
        total_passed += module_passed
        
        print(f"   Tests run: {module_tests}")
        print(f"   Passed: {module_passed}")
        print(f"   Failed: {len(result.failures)}")
        print(f"   Errors: {len(result.errors)}")
        
        if result.failures:
            print("   ❌ Failures:")
            for test, traceback in result.failures:
                print(f"      - {test}: {traceback.split('AssertionError:')[-1].strip()}")
        
        if result.errors:
            print("   💥 Errors:")
            for test, traceback in result.errors:
                error_msg = traceback.split('\n')[-2] if traceback.split('\n') else str(traceback)
                print(f"      - {test}: {error_msg}")
        
        status = "✅ PASSED" if module_passed == module_tests else "❌ FAILED"
        print(f"   Status: {status}")
    
    print("\n" + "=" * 70)
    print("📊 Overall Phase 3 Test Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {total_passed}")
    print(f"   Failed: {total_tests - total_passed}")
    print(f"   Success Rate: {(total_passed/total_tests)*100:.1f}%")
    
    if total_passed == total_tests:
        print("\n🎉 All Phase 3 CI/CD tests passed!")
        print("\n✅ Features validated:")
        print("   - 🚀 GitHub Actions workflow management")
        print("   - 📊 Build status monitoring and analytics")
        print("   - 🏗️  Deployment automation with quality gates")
        print("   - 🔄 Rollback and environment management")
        print("   - 🎯 Integration with MeistroCraft task system")
        print("   - 📈 Health monitoring and alerting")
        
        print("\n🚀 Phase 3: CI/CD Pipeline Integration is ready for production!")
        return True
    else:
        print(f"\n⚠️  {total_tests - total_passed} tests failed. Please review above.")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--comprehensive':
        success = run_phase3_tests()
        sys.exit(0 if success else 1)
    else:
        # Run standard unittest
        unittest.main()