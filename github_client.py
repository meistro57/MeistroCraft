"""
GitHub API Client for MeistroCraft
Provides authentication, repository management, and file operations via GitHub API.
"""

import json
import os
import time
import logging
import asyncio
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

try:
    from github import Github, GithubException, Auth
    from github.Repository import Repository
    from github.ContentFile import ContentFile
    from github.GitRef import GitRef
    from github.Commit import Commit
    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False

# Always import requests for fallback functionality
import requests
import base64


class GitHubClientError(Exception):
    """Custom exception for GitHub client errors."""
    pass


class GitHubRateLimitError(GitHubClientError):
    """Exception raised when GitHub rate limit is exceeded."""
    pass


class GitHubAuthenticationError(GitHubClientError):
    """Exception raised when GitHub authentication fails."""
    pass


class GitHubClient:
    """
    GitHub API client with authentication, rate limiting, and error handling.
    
    Supports Personal Access Tokens and provides comprehensive repository
    and file operations for MeistroCraft integration.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize GitHub client with configuration.
        
        Args:
            config: Configuration dictionary containing GitHub settings
        """
        self.config = config
        self.github_config = config.get('github', {})
        self.logger = logging.getLogger(__name__)
        
        # Initialize GitHub client
        self._github = None
        self._authenticated_user = None
        self._rate_limit_delay = self.github_config.get('rate_limit_delay', 1.0)
        self._max_retries = self.github_config.get('max_retries', 3)
        
        # For fallback mode
        self._api_key = None
        self._base_url = "https://api.github.com"
        self._headers = None
        
        # Performance optimization features
        self._request_cache = {}
        self._cache_ttl = self.github_config.get('cache_ttl', 300)  # 5 minutes
        self._batch_queue = defaultdict(list)
        self._batch_timeout = self.github_config.get('batch_timeout', 0.1)  # 100ms
        self._last_rate_limit_reset = None
        self._requests_remaining = 5000
        self._enable_batching = self.github_config.get('enable_batching', True)
        self._enable_caching = self.github_config.get('enable_caching', True)
        
        # Performance tracking
        self._performance_tracker = None
        self._cache_hits = 0
        self._cache_requests = 0
        self._request_times = []
        
        # Initialize authentication
        self._setup_authentication()
    
    def _setup_authentication(self):
        """Setup GitHub authentication using available credentials."""
        github_token = self._get_github_token()
        
        if not github_token:
            self.logger.warning("No GitHub token found. GitHub features will be disabled.")
            return
        
        if PYGITHUB_AVAILABLE:
            self._setup_pygithub_auth(github_token)
        else:
            self._setup_fallback_auth(github_token)
    
    def _setup_pygithub_auth(self, github_token: str):
        """Setup PyGitHub authentication."""
        try:
            # Create authentication object
            auth = Auth.Token(github_token)
            self._github = Github(auth=auth)
            
            # Verify authentication
            self._authenticated_user = self._github.get_user()
            self.logger.info(f"GitHub authentication successful for user: {self._authenticated_user.login}")
            
        except GithubException as e:
            error_msg = f"GitHub authentication failed: {e.data.get('message', str(e))}"
            self.logger.error(error_msg)
            raise GitHubAuthenticationError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during GitHub authentication: {str(e)}"
            self.logger.error(error_msg)
            raise GitHubAuthenticationError(error_msg)
    
    def _setup_fallback_auth(self, github_token: str):
        """Setup fallback authentication using requests."""
        self._api_key = github_token
        self._headers = {
            "Authorization": f"token {github_token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        # Test authentication
        try:
            user_data = self._make_fallback_request("GET", "/user")
            self.logger.info(f"GitHub fallback authentication successful for user: {user_data.get('login')}")
        except Exception as e:
            error_msg = f"GitHub fallback authentication failed: {str(e)}"
            self.logger.error(error_msg)
            raise GitHubAuthenticationError(error_msg)
    
    def _get_github_token(self) -> Optional[str]:
        """
        Get GitHub token from config or environment variables.
        
        Returns:
            GitHub token if found, None otherwise
        """
        # Try config file first
        token = self.config.get('github_api_key')
        if token and token != "ghp_your-github-personal-access-token":
            return token
        
        # Try environment variables
        return os.getenv('GITHUB_API_TOKEN') or os.getenv('GITHUB_TOKEN')
    
    def _make_fallback_request(self, method: str, endpoint: str, data: Optional[Dict] = None, params: Optional[Dict] = None, return_raw: bool = False) -> Dict[str, Any]:
        """Make a request to the GitHub API using requests (fallback mode)."""
        if not self._headers:
            raise GitHubAuthenticationError("Not authenticated")
        
        start_time = time.time()
        cached = False
        
        # Check cache for GET requests
        cache_key = None
        if self._is_cacheable(method, endpoint):
            cache_key = self._get_cache_key(method, endpoint, params)
            cached_response = self._get_cached_response(cache_key)
            if cached_response is not None:
                self._track_request_time(start_time, endpoint, cached=True)
                return cached_response
            
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        
        try:
            # Add params to URL for GET requests
            request_params = params if method.upper() == "GET" else None
            
            if method.upper() == "GET":
                response = requests.get(url, headers=self._headers, params=request_params, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self._headers, json=data, params=request_params, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=self._headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self._headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Track request timing
            self._track_request_time(start_time, endpoint, cached=False)
            
            # Update rate limit tracking from headers
            if 'X-RateLimit-Remaining' in response.headers:
                self._requests_remaining = int(response.headers['X-RateLimit-Remaining'])
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                self._last_rate_limit_reset = datetime.fromtimestamp(reset_time)
            
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise Exception(f"GitHub API error ({response.status_code}): {error_data.get('message', 'Unknown error')}")
            
            # Return raw response for some endpoints (like logs)
            if return_raw:
                return response
            
            result = response.json() if response.content else {}
            
            # Cache successful GET responses
            if cache_key and method.upper() == "GET":
                self._cache_response(cache_key, result)
            
            return result
            
        except requests.exceptions.RequestException as e:
            # Still track failed request timing
            self._track_request_time(start_time, endpoint, cached=False)
            raise Exception(f"Request failed: {str(e)}")
    
    def _retry_on_rate_limit(self, func, *args, **kwargs):
        """
        Execute function with automatic retry on rate limit errors.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            GitHubRateLimitError: If rate limit exceeded after retries
        """
        # Check intelligent rate limiting
        if self._should_delay_request():
            delay = self._calculate_optimal_delay()
            self.logger.info(f"Preemptive rate limit delay: {delay:.2f}s")
            time.sleep(delay)
        
        for attempt in range(self._max_retries):
            try:
                result = func(*args, **kwargs)
                # Update rate limit tracking on successful request
                self._update_rate_limit_tracking()
                return result
            except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
                if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                    is_rate_limit = e.status == 403 and 'rate limit' in str(e).lower()
                    # Extract rate limit info if available
                    if hasattr(e, 'headers') and 'X-RateLimit-Remaining' in e.headers:
                        self._requests_remaining = int(e.headers['X-RateLimit-Remaining'])
                        reset_time = int(e.headers.get('X-RateLimit-Reset', 0))
                        self._last_rate_limit_reset = datetime.fromtimestamp(reset_time)
                else:
                    is_rate_limit = 'rate limit' in str(e).lower()
                
                if is_rate_limit:
                    if attempt < self._max_retries - 1:
                        wait_time = self._calculate_exponential_backoff(attempt)
                        self.logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{self._max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise GitHubRateLimitError(f"Rate limit exceeded after {self._max_retries} retries")
                else:
                    raise
        
        return func(*args, **kwargs)
    
    def _should_delay_request(self) -> bool:
        """Check if we should preemptively delay requests to avoid rate limiting."""
        if self._requests_remaining is None:
            return False
        
        # Delay if we're getting close to rate limit
        return self._requests_remaining < 100
    
    def _calculate_optimal_delay(self) -> float:
        """Calculate optimal delay to spread requests evenly until rate limit reset."""
        if not self._last_rate_limit_reset or not self._requests_remaining:
            return 0.0
        
        now = datetime.now()
        time_until_reset = (self._last_rate_limit_reset - now).total_seconds()
        
        if time_until_reset <= 0:
            return 0.0
        
        # Spread remaining requests evenly over time until reset
        if self._requests_remaining > 0:
            return min(time_until_reset / self._requests_remaining, 2.0)
        
        return min(time_until_reset, 60.0)  # Wait up to 1 minute
    
    def _calculate_exponential_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff delay with jitter."""
        base_delay = self._rate_limit_delay * (2 ** attempt)
        # Add jitter to prevent thundering herd
        jitter = base_delay * 0.1 * (time.time() % 1)  # 0-10% jitter
        return min(base_delay + jitter, 60.0)  # Cap at 1 minute
    
    def _update_rate_limit_tracking(self):
        """Update rate limit tracking after successful request."""
        if self._requests_remaining is not None:
            self._requests_remaining = max(0, self._requests_remaining - 1)
    
    def _get_cache_key(self, method: str, endpoint: str, params: Dict = None) -> str:
        """Generate cache key for request."""
        key_data = f"{method}:{endpoint}:{json.dumps(params or {}, sort_keys=True)}"
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def _is_cacheable(self, method: str, endpoint: str) -> bool:
        """Check if request should be cached."""
        if not self._enable_caching or method.upper() != 'GET':
            return False
        
        # Cache read-only operations
        cacheable_patterns = [
            '/repos/',
            '/user',
            '/rate_limit',
            '/workflows/',
            '/actions/runs'
        ]
        
        return any(pattern in endpoint for pattern in cacheable_patterns)
    
    def _get_cached_response(self, cache_key: str) -> Optional[Any]:
        """Get cached response if valid."""
        if cache_key not in self._request_cache:
            self._track_cache_performance(hit=False)
            return None
        
        cached_data, timestamp = self._request_cache[cache_key]
        
        # Check if cache is still valid
        if datetime.now() - timestamp > timedelta(seconds=self._cache_ttl):
            del self._request_cache[cache_key]
            self._track_cache_performance(hit=False)
            return None
        
        self.logger.debug(f"Cache hit for key: {cache_key[:16]}...")
        self._track_cache_performance(hit=True)
        return cached_data
    
    def _cache_response(self, cache_key: str, response: Any):
        """Cache response data."""
        self._request_cache[cache_key] = (response, datetime.now())
        
        # Cleanup old cache entries if cache gets too large
        if len(self._request_cache) > 1000:
            self._cleanup_cache()
    
    def _cleanup_cache(self):
        """Remove expired cache entries."""
        now = datetime.now()
        expired_keys = [
            key for key, (_, timestamp) in self._request_cache.items()
            if now - timestamp > timedelta(seconds=self._cache_ttl)
        ]
        
        for key in expired_keys:
            del self._request_cache[key]
        
        self.logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def clear_cache(self):
        """Clear all cached responses."""
        self._request_cache.clear()
        self.logger.info("Cleared GitHub API response cache")
    
    def set_performance_tracker(self, tracker):
        """Set performance tracker for self-optimization."""
        self._performance_tracker = tracker
    
    def _record_performance_metric(self, metric_name: str, value: float, context: Dict[str, Any] = None):
        """Record performance metric if tracker is available."""
        if self._performance_tracker:
            self._performance_tracker.record_performance_metric(
                metric_name, value, "ms", context or {}
            )
    
    def _track_request_time(self, start_time: float, endpoint: str, cached: bool = False):
        """Track request timing for performance analysis."""
        request_time = (time.time() - start_time) * 1000  # Convert to ms
        self._request_times.append(request_time)
        
        # Keep only last 100 request times
        if len(self._request_times) > 100:
            self._request_times = self._request_times[-100:]
        
        # Record performance metric
        self._record_performance_metric(
            'github_api_response_time',
            request_time,
            {
                'endpoint': endpoint,
                'cached': cached,
                'file': 'github_client.py',
                'function': '_make_fallback_request'
            }
        )
    
    def _track_cache_performance(self, hit: bool):
        """Track cache hit/miss for performance analysis."""
        self._cache_requests += 1
        if hit:
            self._cache_hits += 1
        
        # Record cache hit rate periodically
        if self._cache_requests % 10 == 0:
            hit_rate = self._cache_hits / self._cache_requests if self._cache_requests > 0 else 0
            self._record_performance_metric(
                'github_cache_hit_rate',
                hit_rate * 100,
                {
                    'file': 'github_client.py',
                    'function': 'get_cached_response',
                    'total_requests': self._cache_requests,
                    'cache_hits': self._cache_hits
                }
            )
    
    def is_authenticated(self) -> bool:
        """Check if GitHub client is authenticated."""
        if PYGITHUB_AVAILABLE:
            return self._github is not None and self._authenticated_user is not None
        else:
            return self._headers is not None
    
    def get_authenticated_user(self) -> Optional[str]:
        """Get the authenticated user's login name."""
        if PYGITHUB_AVAILABLE and self._authenticated_user:
            return self._authenticated_user.login
        elif not PYGITHUB_AVAILABLE and self._headers:
            try:
                user_data = self._make_fallback_request("GET", "/user")
                return user_data.get('login')
            except Exception:
                return None
        return None
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the GitHub API connection."""
        try:
            if PYGITHUB_AVAILABLE and self._authenticated_user:
                return {
                    "success": True,
                    "username": self._authenticated_user.login,
                    "name": self._authenticated_user.name,
                    "message": f"Successfully authenticated as {self._authenticated_user.login}",
                    "using_pygithub": True
                }
            elif not PYGITHUB_AVAILABLE and self._headers:
                user_data = self._make_fallback_request("GET", "/user")
                return {
                    "success": True,
                    "username": user_data.get("login"),
                    "name": user_data.get("name"),
                    "message": f"Successfully authenticated as {user_data.get('login')} (fallback mode)",
                    "using_pygithub": False
                }
            else:
                return {
                    "success": False,
                    "error": "Not authenticated"
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_rate_limit_status(self) -> Dict[str, Any]:
        """
        Get current rate limit status.
        
        Returns:
            Dictionary with rate limit information
        """
        if not self.is_authenticated():
            return {"error": "Not authenticated"}
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                rate_limit = self._retry_on_rate_limit(self._github.get_rate_limit)
                return {
                    "core": {
                        "limit": rate_limit.core.limit,
                        "remaining": rate_limit.core.remaining,
                        "reset": rate_limit.core.reset.isoformat(),
                        "used": rate_limit.core.used
                    },
                    "search": {
                        "limit": rate_limit.search.limit,
                        "remaining": rate_limit.search.remaining,
                        "reset": rate_limit.search.reset.isoformat(),
                        "used": rate_limit.search.used
                    }
                }
            else:
                # Fallback mode - basic rate limit info
                response = self._make_fallback_request("GET", "/rate_limit")
                return response.get("resources", {})
        except Exception as e:
            return {"error": str(e)}
    
    def create_repository(
        self,
        name: str,
        description: str = "",
        private: bool = None,
        auto_init: bool = None,
        gitignore_template: str = None,
        license_template: str = None,
        organization: str = None
    ):
        """
        Create a new GitHub repository.
        
        Args:
            name: Repository name
            description: Repository description
            private: Whether repository should be private
            auto_init: Whether to auto-initialize with README
            gitignore_template: Gitignore template to use
            license_template: License template to use
            organization: Organization to create repo in (optional)
            
        Returns:
            Created repository object or dict
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        # Use defaults from config if not specified
        if private is None:
            private = self.github_config.get('default_visibility', 'private') == 'private'
        if auto_init is None:
            auto_init = self.github_config.get('auto_initialize', True)
        if gitignore_template is None:
            gitignore_template = self.github_config.get('default_gitignore', 'Python')
        if license_template is None:
            license_template = self.github_config.get('default_license', 'MIT')
        if organization is None:
            organization = self.github_config.get('organization', '')
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                if organization:
                    # Create in organization
                    org = self._retry_on_rate_limit(self._github.get_organization, organization)
                    repo = self._retry_on_rate_limit(
                        org.create_repo,
                        name=name,
                        description=description,
                        private=private,
                        auto_init=auto_init,
                        gitignore_template=gitignore_template if gitignore_template else None,
                        license_template=license_template if license_template else None
                    )
                else:
                    # Create in user account
                    repo = self._retry_on_rate_limit(
                        self._authenticated_user.create_repo,
                        name=name,
                        description=description,
                        private=private,
                        auto_init=auto_init,
                        gitignore_template=gitignore_template if gitignore_template else None,
                        license_template=license_template if license_template else None
                    )
                
                self.logger.info(f"Created repository: {repo.full_name}")
                return repo
            else:
                # Fallback mode
                data = {
                    "name": name,
                    "description": description,
                    "private": private,
                    "auto_init": auto_init,
                    "has_issues": True,
                    "has_projects": True,
                    "has_wiki": True
                }
                
                if gitignore_template:
                    data["gitignore_template"] = gitignore_template
                if license_template:
                    data["license_template"] = license_template
                
                if organization:
                    endpoint = f"/orgs/{organization}/repos"
                else:
                    endpoint = "/user/repos"
                
                repo = self._make_fallback_request("POST", endpoint, data)
                self.logger.info(f"Created repository: {repo.get('full_name')}")
                return repo
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to create repository '{name}': {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to create repository '{name}': {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def get_repository(self, repo_name: str):
        """
        Get repository by name.
        
        Args:
            repo_name: Repository name (owner/repo or just repo for authenticated user)
            
        Returns:
            Repository object or dict
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        try:
            if '/' not in repo_name:
                # Assume it's a repo in the authenticated user's account
                username = self.get_authenticated_user()
                repo_name = f"{username}/{repo_name}"
            
            if PYGITHUB_AVAILABLE and self._github:
                repo = self._retry_on_rate_limit(self._github.get_repo, repo_name)
                return repo
            else:
                repo = self._make_fallback_request("GET", f"/repos/{repo_name}")
                return repo
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to get repository '{repo_name}': {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to get repository '{repo_name}': {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def fork_repository(self, repo_name: str, organization: str = None):
        """
        Fork a repository.
        
        Args:
            repo_name: Repository to fork (owner/repo)
            organization: Organization to fork into (optional)
            
        Returns:
            Forked repository object or dict
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                source_repo = self._retry_on_rate_limit(self._github.get_repo, repo_name)
                
                if organization:
                    org = self._retry_on_rate_limit(self._github.get_organization, organization)
                    forked_repo = self._retry_on_rate_limit(source_repo.create_fork, org)
                else:
                    forked_repo = self._retry_on_rate_limit(source_repo.create_fork)
                
                self.logger.info(f"Forked repository: {source_repo.full_name} -> {forked_repo.full_name}")
                return forked_repo
            else:
                # Fallback mode
                data = {}
                if organization:
                    data["organization"] = organization
                
                forked_repo = self._make_fallback_request("POST", f"/repos/{repo_name}/forks", data)
                self.logger.info(f"Forked repository: {repo_name} -> {forked_repo.get('full_name')}")
                return forked_repo
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to fork repository '{repo_name}': {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to fork repository '{repo_name}': {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def list_repositories(self, organization: str = None) -> List:
        """
        List repositories for authenticated user or organization.
        
        Args:
            organization: Organization name (optional)
            
        Returns:
            List of repository objects or dicts
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                if organization:
                    org = self._retry_on_rate_limit(self._github.get_organization, organization)
                    repos = list(self._retry_on_rate_limit(org.get_repos))
                else:
                    repos = list(self._retry_on_rate_limit(self._authenticated_user.get_repos))
                return repos
            else:
                # Fallback mode
                if organization:
                    endpoint = f"/orgs/{organization}/repos"
                else:
                    endpoint = "/user/repos"
                
                repos = self._make_fallback_request("GET", f"{endpoint}?sort=updated&per_page=100")
                return repos
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to list repositories: {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to list repositories: {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def create_branch(self, repo, branch_name: str, source_branch: str = None):
        """
        Create a new branch in repository.
        
        Args:
            repo: Repository object or name
            branch_name: Name of new branch
            source_branch: Source branch to create from (defaults to default branch)
            
        Returns:
            Git reference object or dict for new branch
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                if isinstance(repo, str):
                    repo = self.get_repository(repo)
                
                if source_branch is None:
                    source_branch = repo.default_branch
                
                # Get source branch reference
                source_ref = self._retry_on_rate_limit(repo.get_git_ref, f"heads/{source_branch}")
                
                # Create new branch
                new_ref = self._retry_on_rate_limit(
                    repo.create_git_ref,
                    ref=f"refs/heads/{branch_name}",
                    sha=source_ref.object.sha
                )
                
                self.logger.info(f"Created branch '{branch_name}' in {repo.full_name}")
                return new_ref
            else:
                # Fallback mode
                if isinstance(repo, dict):
                    repo_name = repo.get('full_name')
                else:
                    repo_name = repo
                
                if '/' not in repo_name:
                    username = self.get_authenticated_user()
                    repo_name = f"{username}/{repo_name}"
                
                if source_branch is None:
                    source_branch = "main"  # Default assumption
                
                # Get the SHA of the source branch
                ref_data = self._make_fallback_request("GET", f"/repos/{repo_name}/git/ref/heads/{source_branch}")
                sha = ref_data["object"]["sha"]
                
                # Create the new branch
                data = {
                    "ref": f"refs/heads/{branch_name}",
                    "sha": sha
                }
                new_ref = self._make_fallback_request("POST", f"/repos/{repo_name}/git/refs", data)
                self.logger.info(f"Created branch '{branch_name}' in {repo_name}")
                return new_ref
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to create branch '{branch_name}': {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to create branch '{branch_name}': {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def get_file_content(self, repo, file_path: str, branch: str = None) -> Tuple[str, str]:
        """
        Get file content from repository.
        
        Args:
            repo: Repository object or name
            file_path: Path to file in repository
            branch: Branch to read from (defaults to default branch)
            
        Returns:
            Tuple of (file_content, sha)
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                if isinstance(repo, str):
                    repo = self.get_repository(repo)
                
                if branch:
                    content = self._retry_on_rate_limit(repo.get_contents, file_path, ref=branch)
                else:
                    content = self._retry_on_rate_limit(repo.get_contents, file_path)
                
                if isinstance(content, list):
                    raise GitHubClientError(f"Path '{file_path}' is a directory, not a file")
                
                return content.decoded_content.decode('utf-8'), content.sha
            else:
                # Fallback mode
                if isinstance(repo, dict):
                    repo_name = repo.get('full_name')
                else:
                    repo_name = repo
                
                if '/' not in repo_name:
                    username = self.get_authenticated_user()
                    repo_name = f"{username}/{repo_name}"
                
                endpoint = f"/repos/{repo_name}/contents/{file_path}"
                if branch:
                    endpoint += f"?ref={branch}"
                
                try:
                    result = self._make_fallback_request("GET", endpoint)
                    if result.get("encoding") == "base64":
                        content = base64.b64decode(result["content"]).decode("utf-8")
                        return content, result["sha"]
                    else:
                        return result.get("content", ""), result.get("sha", "")
                except Exception:
                    # Try with 'master' branch if 'main' fails
                    if not branch or branch == "main":
                        endpoint = f"/repos/{repo_name}/contents/{file_path}?ref=master"
                        result = self._make_fallback_request("GET", endpoint)
                        if result.get("encoding") == "base64":
                            content = base64.b64decode(result["content"]).decode("utf-8")
                            return content, result["sha"]
                        else:
                            return result.get("content", ""), result.get("sha", "")
                    raise
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to get file '{file_path}': {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to get file '{file_path}': {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def create_or_update_file(
        self,
        repo,
        file_path: str,
        content: str,
        commit_message: str,
        branch: str = None,
        sha: str = None
    ):
        """
        Create or update a file in repository.
        
        Args:
            repo: Repository object or name
            file_path: Path to file in repository
            content: File content
            commit_message: Commit message
            branch: Branch to commit to (defaults to default branch)
            sha: SHA of existing file (for updates)
            
        Returns:
            Commit object or dict
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                if isinstance(repo, str):
                    repo = self.get_repository(repo)
                
                kwargs = {
                    "path": file_path,
                    "message": commit_message,
                    "content": content.encode('utf-8')
                }
                
                if branch:
                    kwargs["branch"] = branch
                
                if sha:
                    # Update existing file
                    kwargs["sha"] = sha
                    result = self._retry_on_rate_limit(repo.update_file, **kwargs)
                    self.logger.info(f"Updated file '{file_path}' in {repo.full_name}")
                else:
                    # Create new file
                    result = self._retry_on_rate_limit(repo.create_file, **kwargs)
                    self.logger.info(f"Created file '{file_path}' in {repo.full_name}")
                
                return result["commit"]
            else:
                # Fallback mode
                if isinstance(repo, dict):
                    repo_name = repo.get('full_name')
                else:
                    repo_name = repo
                
                if '/' not in repo_name:
                    username = self.get_authenticated_user()
                    repo_name = f"{username}/{repo_name}"
                
                encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
                data = {
                    "message": commit_message,
                    "content": encoded_content
                }
                
                if branch:
                    data["branch"] = branch
                if sha:
                    data["sha"] = sha
                
                result = self._make_fallback_request("PUT", f"/repos/{repo_name}/contents/{file_path}", data)
                
                if sha:
                    self.logger.info(f"Updated file '{file_path}' in {repo_name}")
                else:
                    self.logger.info(f"Created file '{file_path}' in {repo_name}")
                
                return result.get("commit", result)
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to create/update file '{file_path}': {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to create/update file '{file_path}': {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def list_directory(self, repo, path: str = "", branch: str = None) -> List[Dict[str, Any]]:
        """
        List contents of a directory in repository.
        
        Args:
            repo: Repository object or name
            path: Directory path (empty for root)
            branch: Branch to read from (defaults to default branch)
            
        Returns:
            List of file/directory information
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        try:
            if PYGITHUB_AVAILABLE and self._github:
                if isinstance(repo, str):
                    repo = self.get_repository(repo)
                
                if branch:
                    contents = self._retry_on_rate_limit(repo.get_contents, path, ref=branch)
                else:
                    contents = self._retry_on_rate_limit(repo.get_contents, path)
                
                if not isinstance(contents, list):
                    contents = [contents]
                
                result = []
                for item in contents:
                    result.append({
                        "name": item.name,
                        "path": item.path,
                        "type": item.type,
                        "size": item.size,
                        "sha": item.sha,
                        "download_url": item.download_url,
                        "html_url": item.html_url
                    })
                
                return result
            else:
                # Fallback mode
                if isinstance(repo, dict):
                    repo_name = repo.get('full_name')
                else:
                    repo_name = repo
                
                if '/' not in repo_name:
                    username = self.get_authenticated_user()
                    repo_name = f"{username}/{repo_name}"
                
                endpoint = f"/repos/{repo_name}/contents/{path}"
                if branch:
                    endpoint += f"?ref={branch}"
                
                contents = self._make_fallback_request("GET", endpoint)
                
                if not isinstance(contents, list):
                    contents = [contents]
                
                return contents
                
        except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
            if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                error_msg = f"Failed to list directory '{path}': {e.data.get('message', str(e))}"
            else:
                error_msg = f"Failed to list directory '{path}': {str(e)}"
            self.logger.error(error_msg)
            raise GitHubClientError(error_msg)
    
    def get_multiple_workflow_runs_batch(self, repo_names: List[str], limit: int = 20) -> Dict[str, List]:
        """
        Get workflow runs for multiple repositories in a batched request.
        
        Args:
            repo_names: List of repository names (owner/repo)
            limit: Number of runs to retrieve per repository
            
        Returns:
            Dictionary mapping repo names to their workflow runs
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        if not self._enable_batching or len(repo_names) <= 1:
            # Fall back to individual requests
            return {repo: self._get_single_repo_workflow_runs(repo, limit) for repo in repo_names}
        
        results = {}
        batch_size = 5  # Process in smaller batches to avoid overwhelming the API
        
        for i in range(0, len(repo_names), batch_size):
            batch = repo_names[i:i + batch_size]
            batch_results = self._process_workflow_runs_batch(batch, limit)
            results.update(batch_results)
            
            # Small delay between batches
            if i + batch_size < len(repo_names):
                time.sleep(self._batch_timeout)
        
        return results
    
    def _process_workflow_runs_batch(self, repo_names: List[str], limit: int) -> Dict[str, List]:
        """Process a batch of workflow run requests."""
        results = {}
        
        # Use threading for concurrent requests within batch
        
        def fetch_repo_runs(repo_name):
            try:
                return repo_name, self._get_single_repo_workflow_runs(repo_name, limit)
            except Exception as e:
                self.logger.error(f"Failed to get workflow runs for {repo_name}: {e}")
                return repo_name, []
        
        # Execute requests concurrently with controlled concurrency
        max_workers = min(3, len(repo_names))  # Limit concurrent requests
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_repo = {executor.submit(fetch_repo_runs, repo): repo for repo in repo_names}
            
            for future in as_completed(future_to_repo):
                repo_name, runs = future.result()
                results[repo_name] = runs
        
        return results
    
    def _get_single_repo_workflow_runs(self, repo_name: str, limit: int) -> List[Dict[str, Any]]:
        """Get workflow runs for a single repository."""
        try:
            endpoint = f'/repos/{repo_name}/actions/runs'
            params = {'per_page': min(limit, 100)}
            
            # Use caching for this request
            cache_key = self._get_cache_key('GET', endpoint, params)
            cached_result = self._get_cached_response(cache_key)
            
            if cached_result is not None:
                return cached_result.get('workflow_runs', [])
            
            response = self._retry_on_rate_limit(
                self._make_fallback_request, 'GET', endpoint, params=params
            )
            
            result = response.get('workflow_runs', [])
            
            # Cache the result
            self._cache_response(cache_key, response)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to get workflow runs for {repo_name}: {e}")
            return []
    
    async def batch_github_requests_async(self, requests: List[Dict[str, Any]], max_concurrent: int = 5) -> List[Dict[str, Any]]:
        """
        Process multiple GitHub API requests asynchronously for maximum performance.
        
        Args:
            requests: List of request dictionaries with 'method', 'endpoint', 'params', 'data'
            max_concurrent: Maximum number of concurrent requests
            
        Returns:
            List of response dictionaries
        """
        if not AIOHTTP_AVAILABLE:
            self.logger.warning("aiohttp not available, falling back to batch processing")
            return self._fallback_batch_processing(requests)
        
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        # Group requests by type for intelligent batching
        grouped_requests = self._group_requests_by_similarity(requests)
        all_results = []
        
        async with aiohttp.ClientSession(
            headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=max_concurrent)
        ) as session:
            
            for group_name, group_requests in grouped_requests.items():
                self.logger.debug(f"Processing {len(group_requests)} requests in group: {group_name}")
                
                # Process each group with controlled concurrency
                semaphore = asyncio.Semaphore(max_concurrent)
                
                async def process_request(request):
                    async with semaphore:
                        return await self._make_async_request(session, request)
                
                # Execute all requests in this group concurrently
                group_results = await asyncio.gather(
                    *[process_request(req) for req in group_requests],
                    return_exceptions=True
                )
                
                all_results.extend(group_results)
                
                # Small delay between groups to be kind to the API
                if len(grouped_requests) > 1:
                    await asyncio.sleep(0.1)
        
        return all_results
    
    def _fallback_batch_processing(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fallback batch processing using ThreadPoolExecutor when aiohttp unavailable."""
        results = []
        
        def process_single_request(request):
            try:
                method = request.get('method', 'GET')
                endpoint = request.get('endpoint', '')
                params = request.get('params', {})
                data = request.get('data', {})
                
                result = self._make_fallback_request(method, endpoint, data, params)
                return {'success': True, 'data': result, 'cached': False}
            except Exception as e:
                return {'success': False, 'error': str(e), 'endpoint': endpoint}
        
        # Use threading for concurrent processing
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(process_single_request, requests))
        
        return results
    
    def _group_requests_by_similarity(self, requests: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group similar requests together for intelligent batching."""
        groups = defaultdict(list)
        
        for request in requests:
            endpoint = request.get('endpoint', '')
            method = request.get('method', 'GET')
            
            # Group by endpoint pattern and method
            if '/repos/' in endpoint and '/actions/runs' in endpoint:
                group_key = f"{method}_workflow_runs"
            elif '/repos/' in endpoint and method == 'GET':
                group_key = f"{method}_repo_info"
            elif '/user' in endpoint:
                group_key = f"{method}_user_info"
            else:
                group_key = f"{method}_other"
            
            groups[group_key].append(request)
        
        return dict(groups)
    
    async def _make_async_request(self, session: aiohttp.ClientSession, request: Dict[str, Any]) -> Dict[str, Any]:
        """Make an individual async request with caching and error handling."""
        method = request.get('method', 'GET').upper()
        endpoint = request.get('endpoint', '')
        params = request.get('params', {})
        data = request.get('data', {})
        
        start_time = time.time()
        
        # Check cache for GET requests
        cache_key = None
        if self._is_cacheable(method, endpoint):
            cache_key = self._get_cache_key(method, endpoint, params)
            cached_response = self._get_cached_response(cache_key)
            if cached_response is not None:
                self._track_request_time(start_time, endpoint, cached=True)
                return {'success': True, 'data': cached_response, 'cached': True}
        
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        
        try:
            # Add intelligent delay for rate limiting
            if self._should_delay_request():
                delay = self._calculate_optimal_delay()
                if delay > 0:
                    await asyncio.sleep(delay)
            
            # Make the request
            if method == 'GET':
                async with session.get(url, params=params) as response:
                    result = await self._handle_async_response(response, cache_key, method)
            elif method == 'POST':
                async with session.post(url, json=data, params=params) as response:
                    result = await self._handle_async_response(response, cache_key, method)
            elif method == 'PUT':
                async with session.put(url, json=data) as response:
                    result = await self._handle_async_response(response, cache_key, method)
            elif method == 'DELETE':
                async with session.delete(url) as response:
                    result = await self._handle_async_response(response, cache_key, method)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            self._track_request_time(start_time, endpoint, cached=False)
            return {'success': True, 'data': result, 'cached': False}
            
        except Exception as e:
            self._track_request_time(start_time, endpoint, cached=False)
            self.logger.error(f"Async request failed for {endpoint}: {e}")
            return {'success': False, 'error': str(e), 'endpoint': endpoint}
    
    async def _handle_async_response(self, response, cache_key: Optional[str], method: str) -> Dict[str, Any]:
        """Handle async response with rate limit tracking and caching."""
        # Update rate limit tracking from headers
        if 'X-RateLimit-Remaining' in response.headers:
            self._requests_remaining = int(response.headers['X-RateLimit-Remaining'])
            reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
            self._last_rate_limit_reset = datetime.fromtimestamp(reset_time)
        
        if response.status >= 400:
            error_text = await response.text()
            try:
                error_data = json.loads(error_text) if error_text else {}
                error_message = error_data.get('message', 'Unknown error')
            except json.JSONDecodeError:
                error_message = error_text or 'Unknown error'
            raise Exception(f"GitHub API error ({response.status}): {error_message}")
        
        result = await response.json() if response.content_length and response.content_length > 0 else {}
        
        # Cache successful GET responses
        if cache_key and method == 'GET':
            self._cache_response(cache_key, result)
        
        return result
    
    def batch_multiple_repo_operations(self, operations: List[Dict[str, Any]], max_concurrent: int = 3) -> Dict[str, Any]:
        """
        Perform multiple repository operations efficiently using threading.
        
        Args:
            operations: List of operation dictionaries
            max_concurrent: Maximum concurrent operations
            
        Returns:
            Dictionary with results and performance metrics
        """
        if not self.is_authenticated():
            raise GitHubAuthenticationError("Not authenticated with GitHub")
        
        start_time = time.time()
        results = []
        errors = []
        
        def execute_operation(operation):
            try:
                op_type = operation.get('type')
                if op_type == 'get_workflow_runs':
                    return self._get_single_repo_workflow_runs(
                        operation['repo_name'], 
                        operation.get('limit', 20)
                    )
                elif op_type == 'get_repo_info':
                    return self.get_repository_info(operation['repo_name'])
                elif op_type == 'list_files':
                    return self.list_directory(
                        operation['repo_name'], 
                        operation.get('path', ''),
                        operation.get('branch', 'main')
                    )
                else:
                    raise ValueError(f"Unsupported operation type: {op_type}")
            except Exception as e:
                return {'error': str(e), 'operation': operation}
        
        # Use ThreadPoolExecutor for concurrent execution
        with ThreadPoolExecutor(max_workers=min(max_concurrent, len(operations))) as executor:
            future_to_operation = {
                executor.submit(execute_operation, op): op for op in operations
            }
            
            for future in as_completed(future_to_operation):
                operation = future_to_operation[future]
                try:
                    result = future.result()
                    if isinstance(result, dict) and 'error' in result:
                        errors.append(result)
                    else:
                        results.append({
                            'operation': operation,
                            'result': result,
                            'success': True
                        })
                except Exception as e:
                    errors.append({
                        'operation': operation,
                        'error': str(e),
                        'success': False
                    })
        
        total_time = time.time() - start_time
        
        return {
            'results': results,
            'errors': errors,
            'performance': {
                'total_time_seconds': total_time,
                'total_operations': len(operations),
                'successful_operations': len(results),
                'failed_operations': len(errors),
                'operations_per_second': len(operations) / total_time if total_time > 0 else 0
            }
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the GitHub client."""
        # Calculate average request time
        avg_request_time = sum(self._request_times) / len(self._request_times) if self._request_times else 0
        
        cache_stats = {
            'cache_size': len(self._request_cache),
            'cache_hit_rate': self._cache_hits / max(self._cache_requests, 1),
            'cache_hits': self._cache_hits,
            'cache_requests': self._cache_requests,
            'requests_remaining': self._requests_remaining,
            'last_rate_limit_reset': self._last_rate_limit_reset.isoformat() if self._last_rate_limit_reset else None
        }
        
        performance_stats = {
            'avg_request_time_ms': avg_request_time,
            'total_requests': len(self._request_times),
            'recent_request_times': self._request_times[-10:] if self._request_times else []
        }
        
        return {
            'cache_stats': cache_stats,
            'performance_stats': performance_stats,
            'optimization_enabled': {
                'caching': self._enable_caching,
                'batching': self._enable_batching
            },
            'configuration': {
                'cache_ttl': self._cache_ttl,
                'batch_timeout': self._batch_timeout,
                'rate_limit_delay': self._rate_limit_delay
            }
        }


def create_github_client(config: Dict[str, Any]) -> Optional[GitHubClient]:
    """
    Create and return a GitHub client instance.
    
    Args:
        config: Configuration dictionary
        
    Returns:
        GitHubClient instance or None if GitHub is disabled/unavailable
    """
    github_config = config.get('github', {})
    
    if not github_config.get('enabled', True):
        return None
    
    try:
        return GitHubClient(config)
    except GitHubAuthenticationError as e:
        logging.warning(f"GitHub authentication failed: {e}")
        return None
    except Exception as e:
        logging.error(f"Failed to create GitHub client: {e}")
        return None