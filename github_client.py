"""
GitHub API Client for MeistroCraft
Provides authentication, repository management, and file operations via GitHub API.
"""

import json
import os
import time
import logging
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime
from pathlib import Path

try:
    from github import Github, GithubException, Auth
    from github.Repository import Repository
    from github.ContentFile import ContentFile
    from github.GitRef import GitRef
    from github.Commit import Commit
    PYGITHUB_AVAILABLE = True
except ImportError:
    PYGITHUB_AVAILABLE = False
    # Fallback imports for basic functionality
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
    
    def _make_fallback_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a request to the GitHub API using requests (fallback mode)."""
        if not self._headers:
            raise GitHubAuthenticationError("Not authenticated")
            
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=self._headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self._headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=self._headers, json=data, timeout=30)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=self._headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            if response.status_code >= 400:
                error_data = response.json() if response.content else {}
                raise Exception(f"GitHub API error ({response.status_code}): {error_data.get('message', 'Unknown error')}")
            
            return response.json() if response.content else {}
            
        except requests.exceptions.RequestException as e:
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
        for attempt in range(self._max_retries):
            try:
                return func(*args, **kwargs)
            except (GithubException if PYGITHUB_AVAILABLE else Exception) as e:
                if PYGITHUB_AVAILABLE and isinstance(e, GithubException):
                    is_rate_limit = e.status == 403 and 'rate limit' in str(e).lower()
                else:
                    is_rate_limit = 'rate limit' in str(e).lower()
                
                if is_rate_limit:
                    if attempt < self._max_retries - 1:
                        wait_time = self._rate_limit_delay * (2 ** attempt)
                        self.logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{self._max_retries}")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise GitHubRateLimitError(f"Rate limit exceeded after {self._max_retries} retries")
                else:
                    raise
        
        return func(*args, **kwargs)
    
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