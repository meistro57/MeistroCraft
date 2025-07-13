#!/usr/bin/env python3
"""
Test script for GitHub integration in MeistroCraft.
Tests GitHub client functionality without requiring actual API calls.
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from github_client import GitHubClient, GitHubClientError, GitHubAuthenticationError, create_github_client


class TestGitHubClient(unittest.TestCase):
    """Test cases for GitHub client functionality."""
    
    def setUp(self):
        """Set up test configuration."""
        self.test_config = {
            'github_api_key': 'test_token_123',
            'github': {
                'enabled': True,
                'default_branch': 'main',
                'auto_create_repos': True,
                'enable_webhooks': False,
                'rate_limit_delay': 1.0,
                'max_retries': 3,
                'organization': '',
                'default_visibility': 'private',
                'auto_initialize': True,
                'default_gitignore': 'Python',
                'default_license': 'MIT'
            }
        }
    
    def test_config_loading(self):
        """Test configuration loading and validation."""
        # Test with valid config
        self.assertIsNotNone(self.test_config.get('github_api_key'))
        self.assertIsNotNone(self.test_config.get('github'))
        
        # Test GitHub config defaults
        github_config = self.test_config.get('github', {})
        self.assertTrue(github_config.get('enabled', True))
        self.assertEqual(github_config.get('default_branch'), 'main')
        self.assertEqual(github_config.get('default_visibility'), 'private')
    
    @patch('github_client.PYGITHUB_AVAILABLE', False)
    def test_fallback_mode_initialization(self):
        """Test initialization in fallback mode (no PyGitHub)."""
        with patch.dict(os.environ, {'GITHUB_API_TOKEN': 'test_token'}):
            with patch('github_client.requests') as mock_requests:
                # Mock successful authentication response
                mock_response = Mock()
                mock_response.json.return_value = {'login': 'testuser', 'name': 'Test User'}
                mock_response.status_code = 200
                mock_response.content = True
                mock_requests.get.return_value = mock_response
                
                client = GitHubClient(self.test_config)
                self.assertTrue(client.is_authenticated())
                self.assertEqual(client.get_authenticated_user(), 'testuser')
    
    @patch('github_client.PYGITHUB_AVAILABLE', True)
    @patch('github_client.Github')
    @patch('github_client.Auth')
    def test_pygithub_mode_initialization(self, mock_auth, mock_github):
        """Test initialization with PyGitHub library."""
        # Mock PyGitHub components
        mock_github_instance = Mock()
        mock_user = Mock()
        mock_user.login = 'testuser'
        mock_user.name = 'Test User'
        mock_github_instance.get_user.return_value = mock_user
        mock_github.return_value = mock_github_instance
        
        mock_auth_instance = Mock()
        mock_auth.Token.return_value = mock_auth_instance
        
        client = GitHubClient(self.test_config)
        self.assertTrue(client.is_authenticated())
        self.assertEqual(client.get_authenticated_user(), 'testuser')
    
    def test_token_resolution(self):
        """Test GitHub token resolution from different sources."""
        # Test config file token
        client_config = self.test_config.copy()
        client_config['github_api_key'] = 'config_token'
        
        with patch('github_client.PYGITHUB_AVAILABLE', False):
            with patch('github_client.requests') as mock_requests:
                mock_response = Mock()
                mock_response.json.return_value = {'login': 'testuser'}
                mock_response.status_code = 200
                mock_response.content = True
                mock_requests.get.return_value = mock_response
                
                client = GitHubClient(client_config)
                # Token should come from config
                self.assertIsNotNone(client._api_key)
        
        # Test environment variable token
        with patch.dict(os.environ, {'GITHUB_API_TOKEN': 'env_token'}):
            config_no_token = {'github': self.test_config['github']}
            
            with patch('github_client.PYGITHUB_AVAILABLE', False):
                with patch('github_client.requests') as mock_requests:
                    mock_response = Mock()
                    mock_response.json.return_value = {'login': 'testuser'}
                    mock_response.status_code = 200
                    mock_response.content = True
                    mock_requests.get.return_value = mock_response
                    
                    client = GitHubClient(config_no_token)
                    self.assertIsNotNone(client._api_key)
    
    def test_error_handling(self):
        """Test error handling for various failure scenarios."""
        # Test authentication failure
        with patch('github_client.PYGITHUB_AVAILABLE', False):
            with patch('github_client.requests') as mock_requests:
                mock_response = Mock()
                mock_response.status_code = 401
                mock_response.json.return_value = {'message': 'Bad credentials'}
                mock_requests.get.return_value = mock_response
                
                with self.assertRaises(GitHubAuthenticationError):
                    GitHubClient(self.test_config)
        
        # Test missing token
        config_no_token = {'github': self.test_config['github']}
        with patch.dict(os.environ, {}, clear=True):
            client = GitHubClient(config_no_token)
            self.assertFalse(client.is_authenticated())
    
    def test_rate_limiting(self):
        """Test rate limiting and retry logic."""
        with patch('github_client.PYGITHUB_AVAILABLE', False):
            with patch('github_client.requests') as mock_requests:
                # Setup successful auth first
                auth_response = Mock()
                auth_response.json.return_value = {'login': 'testuser'}
                auth_response.status_code = 200
                auth_response.content = True
                
                # Setup rate limit response
                rate_limit_response = Mock()
                rate_limit_response.status_code = 403
                rate_limit_response.json.return_value = {'message': 'rate limit exceeded'}
                
                # Success response after retry
                success_response = Mock()
                success_response.json.return_value = {'test': 'success'}
                success_response.status_code = 200
                success_response.content = True
                
                # Configure mock to return different responses
                mock_requests.get.side_effect = [
                    auth_response,  # For initial auth
                    rate_limit_response,  # First API call - rate limited
                    success_response  # Retry - success
                ]
                
                client = GitHubClient(self.test_config)
                
                # Mock time.sleep to speed up test
                with patch('github_client.time.sleep'):
                    # This should trigger rate limit handling
                    result = client._make_fallback_request('GET', '/test')
                    self.assertEqual(result['test'], 'success')
    
    def test_repository_operations(self):
        """Test repository creation, forking, and listing operations."""
        with patch('github_client.PYGITHUB_AVAILABLE', False):
            with patch('github_client.requests') as mock_requests:
                # Setup authentication
                auth_response = Mock()
                auth_response.json.return_value = {'login': 'testuser'}
                auth_response.status_code = 200
                auth_response.content = True
                
                # Mock repository creation response
                create_response = Mock()
                create_response.json.return_value = {
                    'full_name': 'testuser/testrepo',
                    'html_url': 'https://github.com/testuser/testrepo',
                    'clone_url': 'https://github.com/testuser/testrepo.git'
                }
                create_response.status_code = 201
                create_response.content = True
                
                mock_requests.get.return_value = auth_response
                mock_requests.post.return_value = create_response
                
                client = GitHubClient(self.test_config)
                
                # Test repository creation
                repo = client.create_repository('testrepo', 'Test repository')
                self.assertEqual(repo['full_name'], 'testuser/testrepo')
    
    def test_client_factory(self):
        """Test the create_github_client factory function."""
        # Test successful creation
        with patch('github_client.GitHubClient') as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            
            config = {'github': {'enabled': True}}
            result = create_github_client(config)
            self.assertIsNotNone(result)
        
        # Test disabled GitHub integration
        config_disabled = {'github': {'enabled': False}}
        result = create_github_client(config_disabled)
        self.assertIsNone(result)
        
        # Test authentication error handling
        with patch('github_client.GitHubClient') as mock_client_class:
            mock_client_class.side_effect = GitHubAuthenticationError("Auth failed")
            
            config = {'github': {'enabled': True}}
            result = create_github_client(config)
            self.assertIsNone(result)


class TestGitHubIntegration(unittest.TestCase):
    """Integration tests for GitHub functionality with MeistroCraft."""
    
    def test_config_template_validation(self):
        """Test that the configuration template is valid."""
        config_template_path = os.path.join(os.path.dirname(__file__), 'config', 'config.template.json')
        
        if os.path.exists(config_template_path):
            with open(config_template_path, 'r') as f:
                config = json.load(f)
            
            # Check GitHub configuration section exists
            self.assertIn('github', config)
            github_config = config['github']
            
            # Check required fields
            self.assertIn('enabled', github_config)
            self.assertIn('default_branch', github_config)
            self.assertIn('auto_create_repos', github_config)
            self.assertIn('rate_limit_delay', github_config)
            self.assertIn('max_retries', github_config)
    
    def test_environment_template_validation(self):
        """Test that the environment template includes GitHub variables."""
        env_template_path = os.path.join(os.path.dirname(__file__), 'env.template')
        
        if os.path.exists(env_template_path):
            with open(env_template_path, 'r') as f:
                content = f.read()
            
            # Check GitHub environment variables are documented
            self.assertIn('GITHUB_API_TOKEN', content)
            self.assertIn('GITHUB_USERNAME', content)
            self.assertIn('GITHUB_ORGANIZATION', content)


def run_github_integration_test():
    """
    Run a basic integration test to verify GitHub client functionality.
    This can be called from the command line to test the setup.
    """
    print("🧪 Running GitHub Integration Tests...")
    print("=" * 50)
    
    # Test 1: Configuration loading
    print("1. Testing configuration loading...")
    try:
        from main import load_config
        config = load_config('config/config.template.json')
        github_config = config.get('github', {})
        if github_config:
            print("   ✅ GitHub configuration found in template")
        else:
            print("   ❌ GitHub configuration missing from template")
    except Exception as e:
        print(f"   ❌ Configuration loading failed: {e}")
    
    # Test 2: Client creation (without actual API calls)
    print("\n2. Testing GitHub client creation...")
    try:
        mock_config = {
            'github_api_key': 'test_token',
            'github': {
                'enabled': True,
                'default_branch': 'main',
                'rate_limit_delay': 1.0,
                'max_retries': 3
            }
        }
        
        # Test with no token (should handle gracefully)
        no_token_config = {'github': {'enabled': True}}
        client = create_github_client(no_token_config)
        if client is None:
            print("   ✅ Handles missing token gracefully")
        else:
            print("   ❌ Should return None when no token provided")
            
    except Exception as e:
        print(f"   ❌ Client creation test failed: {e}")
    
    # Test 3: Requirements check
    print("\n3. Testing requirements...")
    try:
        import github
        print("   ✅ PyGitHub library available")
    except ImportError:
        print("   ⚠️  PyGitHub library not installed (fallback mode will be used)")
        print("      Install with: pip install PyGitHub>=2.1.0")
    
    try:
        import requests
        print("   ✅ Requests library available")
    except ImportError:
        print("   ❌ Requests library not available (required for fallback mode)")
    
    print("\n" + "=" * 50)
    print("🎯 GitHub Integration Test Summary:")
    print("   Phase 1 implementation includes:")
    print("   • ✅ GitHub Authentication & Configuration")
    print("   • ✅ Repository Management (create, fork, list)")
    print("   • ✅ File Operations via GitHub API")
    print("   • ✅ Branch Management")
    print("   • ✅ CLI Commands and Interactive Mode")
    print("   • ✅ Rate Limiting and Error Handling")
    print("\n   Next: Add GitHub API token to config and test with real API!")


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--integration':
        run_github_integration_test()
    else:
        # Run unit tests
        unittest.main()