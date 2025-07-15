"""
AI-Powered Code Review Analyzer for MeistroCraft - Phase 2 Polish
Provides intelligent code analysis, security scanning, and optimization suggestions.
"""

import json
import re
import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from github_client import GitHubClient, GitHubClientError


class CodeReviewError(Exception):
    """Custom exception for code review errors."""
    pass


class CodeReviewAnalyzer:
    """
    AI-powered code review analyzer that provides intelligent suggestions
    for code quality, security, performance, and best practices.
    """

    def __init__(self, github_client: GitHubClient, config: Dict[str, Any] = None):
        """
        Initialize code review analyzer.

        Args:
            github_client: Authenticated GitHub client instance
            config: Configuration dictionary with OpenAI settings
        """
        self.github = github_client
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Initialize OpenAI client if available
        self.openai_client = None
        if OpenAI and self.config.get('openai_api_key'):
            try:
                self.openai_client = OpenAI(api_key=self.config['openai_api_key'])
            except Exception as e:
                self.logger.warning(f"Failed to initialize OpenAI client: {e}")

        # Review categories and their priorities
        self.review_categories = {
            'security': {'priority': 'critical', 'enabled': True},
            'performance': {'priority': 'high', 'enabled': True},
            'code_quality': {'priority': 'medium', 'enabled': True},
            'best_practices': {'priority': 'medium', 'enabled': True},
            'documentation': {'priority': 'low', 'enabled': True}
        }

        # Language-specific patterns and rules
        self.language_patterns = self._load_language_patterns()

    def analyze_pull_request(
        self,
        repo_name: str,
        pr_number: int,
        focus_areas: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a pull request and provide comprehensive code review.

        Args:
            repo_name: Repository name (owner/repo)
            pr_number: Pull request number
            focus_areas: Specific areas to focus on (security, performance, etc.)

        Returns:
            Dictionary with review results and suggestions
        """
        try:
            # Get PR details and file changes
            pr_data = self._get_pr_details(repo_name, pr_number)
            file_changes = self._get_pr_file_changes(repo_name, pr_number)

            # Analyze each changed file
            file_analyses = []
            for file_change in file_changes:
                analysis = self._analyze_file_change(file_change, repo_name)
                if analysis:
                    file_analyses.append(analysis)

            # Generate overall review summary
            review_summary = self._generate_review_summary(file_analyses, pr_data)

            # AI-powered insights (if OpenAI available)
            ai_insights = None
            if self.openai_client:
                ai_insights = self._generate_ai_insights(file_analyses, pr_data)

            return {
                'pr_number': pr_number,
                'repository': repo_name,
                'review_timestamp': datetime.now().isoformat(),
                'overall_score': self._calculate_overall_score(file_analyses),
                'summary': review_summary,
                'file_analyses': file_analyses,
                'ai_insights': ai_insights,
                'recommendations': self._generate_recommendations(file_analyses),
                'security_concerns': self._extract_security_concerns(file_analyses),
                'performance_suggestions': self._extract_performance_suggestions(file_analyses)
            }

        except Exception as e:
            self.logger.error(f"Failed to analyze PR {pr_number}: {e}")
            raise CodeReviewError(f"PR analysis failed: {e}")

    def analyze_code_snippet(
        self,
        code: str,
        filename: str = "unknown",
        language: str = None
    ) -> Dict[str, Any]:
        """
        Analyze a code snippet for issues and improvements.

        Args:
            code: Code content to analyze
            filename: Name of the file (for context)
            language: Programming language (auto-detected if not provided)

        Returns:
            Dictionary with analysis results
        """
        try:
            # Detect language if not provided
            if not language:
                language = self._detect_language(filename, code)

            # Perform static analysis
            static_analysis = self._perform_static_analysis(code, language)

            # Security vulnerability scan
            security_issues = self._scan_security_vulnerabilities(code, language)

            # Performance analysis
            performance_issues = self._analyze_performance(code, language)

            # Code quality assessment
            quality_issues = self._assess_code_quality(code, language)

            # AI-powered suggestions (if available)
            ai_suggestions = None
            if self.openai_client:
                ai_suggestions = self._get_ai_suggestions(code, language, filename)

            return {
                'filename': filename,
                'language': language,
                'analysis_timestamp': datetime.now().isoformat(),
                'score': self._calculate_snippet_score(
                    static_analysis,
                    security_issues,
                    performance_issues,
                    quality_issues),
                'static_analysis': static_analysis,
                'security_issues': security_issues,
                'performance_issues': performance_issues,
                'quality_issues': quality_issues,
                'ai_suggestions': ai_suggestions,
                'lines_analyzed': len(
                    code.splitlines())}

        except Exception as e:
            self.logger.error(f"Failed to analyze code snippet: {e}")
            raise CodeReviewError(f"Code analysis failed: {e}")

    def _get_pr_details(self, repo_name: str, pr_number: int) -> Dict[str, Any]:
        """Get pull request details from GitHub."""
        try:
            repo = self.github.get_repository(repo_name)

            if hasattr(repo, 'get_pull'):  # PyGitHub object
                pr = repo.get_pull(pr_number)
                return {
                    'title': pr.title,
                    'body': pr.body or '',
                    'user': pr.user.login,
                    'created_at': pr.created_at.isoformat(),
                    'additions': pr.additions,
                    'deletions': pr.deletions,
                    'changed_files': pr.changed_files,
                    'base_branch': pr.base.ref,
                    'head_branch': pr.head.ref
                }
            else:
                # Fallback mode
                pr = self.github._make_fallback_request('GET', f'/repos/{repo_name}/pulls/{pr_number}')
                return {
                    'title': pr.get('title', ''),
                    'body': pr.get('body', ''),
                    'user': pr.get('user', {}).get('login', 'unknown'),
                    'created_at': pr.get('created_at', ''),
                    'additions': pr.get('additions', 0),
                    'deletions': pr.get('deletions', 0),
                    'changed_files': pr.get('changed_files', 0),
                    'base_branch': pr.get('base', {}).get('ref', 'main'),
                    'head_branch': pr.get('head', {}).get('ref', 'unknown')
                }

        except Exception as e:
            self.logger.error(f"Failed to get PR details: {e}")
            return {}

    def _get_pr_file_changes(self, repo_name: str, pr_number: int) -> List[Dict[str, Any]]:
        """Get file changes from a pull request."""
        try:
            repo = self.github.get_repository(repo_name)

            if hasattr(repo, 'get_pull'):  # PyGitHub object
                pr = repo.get_pull(pr_number)
                files = list(pr.get_files())

                return [
                    {
                        'filename': file.filename,
                        'status': file.status,
                        'additions': file.additions,
                        'deletions': file.deletions,
                        'changes': file.changes,
                        'patch': file.patch or ''
                    }
                    for file in files
                ]
            else:
                # Fallback mode
                files = self.github._make_fallback_request('GET', f'/repos/{repo_name}/pulls/{pr_number}/files')

                return [
                    {
                        'filename': file.get('filename', ''),
                        'status': file.get('status', 'modified'),
                        'additions': file.get('additions', 0),
                        'deletions': file.get('deletions', 0),
                        'changes': file.get('changes', 0),
                        'patch': file.get('patch', '')
                    }
                    for file in files
                ]

        except Exception as e:
            self.logger.error(f"Failed to get PR file changes: {e}")
            return []

    def _analyze_file_change(self, file_change: Dict[str, Any], repo_name: str) -> Optional[Dict[str, Any]]:
        """Analyze a single file change from a PR."""
        filename = file_change.get('filename', '')
        patch = file_change.get('patch', '')

        if not patch:
            return None

        # Extract added/modified lines from patch
        added_lines = self._extract_added_lines(patch)

        if not added_lines:
            return None

        # Analyze the added code
        language = self._detect_language(filename, '\n'.join(added_lines))
        analysis = self.analyze_code_snippet('\n'.join(added_lines), filename, language)

        # Add file change context
        analysis.update({
            'file_change': {
                'status': file_change.get('status', 'modified'),
                'additions': file_change.get('additions', 0),
                'deletions': file_change.get('deletions', 0),
                'total_changes': file_change.get('changes', 0)
            }
        })

        return analysis

    def _extract_added_lines(self, patch: str) -> List[str]:
        """Extract added lines from a git patch."""
        added_lines = []

        for line in patch.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                # Remove the + prefix and add to list
                added_lines.append(line[1:])

        return added_lines

    def _detect_language(self, filename: str, code: str) -> str:
        """Detect programming language from filename and code content."""
        # Language detection by file extension
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.cs': 'csharp',
            '.php': 'php',
            '.rb': 'ruby',
            '.go': 'go',
            '.rs': 'rust',
            '.kt': 'kotlin',
            '.swift': 'swift',
            '.sql': 'sql',
            '.sh': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sass': 'sass',
            '.md': 'markdown',
            '.dockerfile': 'dockerfile'
        }

        # Check file extension
        for ext, lang in ext_map.items():
            if filename.lower().endswith(ext):
                return lang

        # Check filename patterns
        if 'dockerfile' in filename.lower():
            return 'dockerfile'
        if 'makefile' in filename.lower():
            return 'makefile'

        # Basic content-based detection
        if '#!/usr/bin/env python' in code or 'import ' in code or 'def ' in code:
            return 'python'
        if 'function ' in code or 'const ' in code or 'let ' in code:
            return 'javascript'
        if 'class ' in code and ('public ' in code or 'private ' in code):
            return 'java'

        return 'unknown'

    def _perform_static_analysis(self, code: str, language: str) -> Dict[str, Any]:
        """Perform static code analysis."""
        issues = []

        # Generic code issues
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Long lines
            if len(line) > 120:
                issues.append({
                    'type': 'code_style',
                    'severity': 'low',
                    'line': i,
                    'message': f'Line too long ({len(line)} characters)',
                    'suggestion': 'Consider breaking long lines for better readability'
                })

            # TODO/FIXME comments
            if any(keyword in line_stripped.upper() for keyword in ['TODO', 'FIXME', 'HACK', 'BUG']):
                issues.append({
                    'type': 'todo',
                    'severity': 'info',
                    'line': i,
                    'message': 'TODO/FIXME comment found',
                    'suggestion': 'Consider creating a GitHub issue for this TODO'
                })

            # Potential debug code
            if any(debug in line_stripped.lower() for debug in ['print(', 'console.log(', 'debugger', 'alert(']):
                issues.append({
                    'type': 'debug_code',
                    'severity': 'medium',
                    'line': i,
                    'message': 'Potential debug code found',
                    'suggestion': 'Remove debug statements before production'
                })

        # Language-specific analysis
        if language in self.language_patterns:
            language_issues = self._analyze_language_specific(code, language)
            issues.extend(language_issues)

        return {
            'total_issues': len(issues),
            'issues_by_severity': self._group_by_severity(issues),
            'issues': issues
        }

    def _scan_security_vulnerabilities(self, code: str, language: str) -> Dict[str, Any]:
        """Scan for security vulnerabilities."""
        vulnerabilities = []

        # SQL Injection patterns
        sql_injection_patterns = [
            r'SELECT.*\+.*',
            r'INSERT.*\+.*',
            r'UPDATE.*\+.*',
            r'DELETE.*\+.*',
            r'exec\s*\(',
            r'eval\s*\(',
            r'f".*{.*}.*".*sql',  # Python f-strings in SQL
        ]

        for pattern in sql_injection_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                vulnerabilities.append({
                    'type': 'sql_injection',
                    'severity': 'critical',
                    'line': line_num,
                    'message': 'Potential SQL injection vulnerability',
                    'suggestion': 'Use parameterized queries or prepared statements'
                })

        # Hardcoded secrets
        secret_patterns = [
            r'password\s*=\s*["\'][^"\']+["\']',
            r'api_key\s*=\s*["\'][^"\']+["\']',
            r'secret\s*=\s*["\'][^"\']+["\']',
            r'token\s*=\s*["\'][^"\']+["\']',
            r'["\'][A-Za-z0-9+/]{20,}["\']',  # Base64-like strings
        ]

        for pattern in secret_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                vulnerabilities.append({
                    'type': 'hardcoded_secret',
                    'severity': 'critical',
                    'line': line_num,
                    'message': 'Potential hardcoded secret or credential',
                    'suggestion': 'Use environment variables or secure configuration'
                })

        # Cross-site scripting (XSS) patterns
        if language in ['javascript', 'html', 'php']:
            xss_patterns = [
                r'innerHTML\s*=.*\+',
                r'outerHTML\s*=.*\+',
                r'document\.write\s*\(',
                r'eval\s*\(',
                r'setTimeout\s*\(.*\+',
            ]

            for pattern in xss_patterns:
                matches = re.finditer(pattern, code, re.IGNORECASE)
                for match in matches:
                    line_num = code[:match.start()].count('\n') + 1
                    vulnerabilities.append({
                        'type': 'xss',
                        'severity': 'high',
                        'line': line_num,
                        'message': 'Potential XSS vulnerability',
                        'suggestion': 'Sanitize user input and use safe DOM manipulation methods'
                    })

        # Unsafe file operations
        unsafe_file_patterns = [
            r'open\s*\(.*\+',  # Python file operations with concatenation
            r'exec\s*\(',
            r'os\.system\s*\(',
            r'subprocess\.call\s*\(.*shell\s*=\s*True',
        ]

        for pattern in unsafe_file_patterns:
            matches = re.finditer(pattern, code, re.IGNORECASE)
            for match in matches:
                line_num = code[:match.start()].count('\n') + 1
                vulnerabilities.append({
                    'type': 'unsafe_operation',
                    'severity': 'high',
                    'line': line_num,
                    'message': 'Potentially unsafe file or system operation',
                    'suggestion': 'Validate and sanitize all inputs, avoid shell execution with user input'
                })

        return {
            'total_vulnerabilities': len(vulnerabilities),
            'critical_count': len([v for v in vulnerabilities if v['severity'] == 'critical']),
            'high_count': len([v for v in vulnerabilities if v['severity'] == 'high']),
            'vulnerabilities': vulnerabilities
        }

    def _analyze_performance(self, code: str, language: str) -> Dict[str, Any]:
        """Analyze code for performance issues."""
        performance_issues = []

        # Generic performance patterns
        lines = code.split('\n')

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Nested loops
            if 'for ' in line_stripped and any('for ' in lines[j] for j in range(
                    max(0, i - 5), min(len(lines), i + 5)) if j != i - 1):
                performance_issues.append({
                    'type': 'nested_loops',
                    'severity': 'medium',
                    'line': i,
                    'message': 'Nested loops detected',
                    'suggestion': 'Consider algorithm optimization or data structure improvements'
                })

            # Large string concatenation
            if '+=' in line_stripped and ('str' in line_stripped or '"' in line_stripped):
                performance_issues.append({
                    'type': 'string_concatenation',
                    'severity': 'low',
                    'line': i,
                    'message': 'String concatenation in loop may be inefficient',
                    'suggestion': 'Consider using join() method or string formatting'
                })

        # Language-specific performance patterns
        if language == 'python':
            # Python-specific performance issues
            python_patterns = [
                (r'\.append\(.*\)\s*in\s+.*for', 'list_comprehension', 'Consider using list comprehension'),
                (r'range\s*\(\s*len\s*\(', 'enumerate', 'Consider using enumerate() instead of range(len())'),
                (r'global\s+\w+', 'global_vars', 'Global variables can impact performance and maintainability'),
            ]

            for pattern, issue_type, suggestion in python_patterns:
                matches = re.finditer(pattern, code, re.IGNORECASE)
                for match in matches:
                    line_num = code[:match.start()].count('\n') + 1
                    performance_issues.append({
                        'type': issue_type,
                        'severity': 'low',
                        'line': line_num,
                        'message': f'Performance optimization opportunity: {issue_type}',
                        'suggestion': suggestion
                    })

        elif language == 'javascript':
            # JavaScript-specific performance issues
            js_patterns = [
                (r'document\.getElementById', 'dom_query', 'Cache DOM queries for better performance'),
                (r'setTimeout\s*\(\s*.*\s*,\s*0\s*\)', 'settimeout_zero', 'setTimeout with 0 delay may indicate design issues'),
                (r'for\s*\(.*in.*\)', 'for_in_loop', 'for...in loops can be slow, consider for...of or forEach'),
            ]

            for pattern, issue_type, suggestion in js_patterns:
                matches = re.finditer(pattern, code, re.IGNORECASE)
                for match in matches:
                    line_num = code[:match.start()].count('\n') + 1
                    performance_issues.append({
                        'type': issue_type,
                        'severity': 'low',
                        'line': line_num,
                        'message': f'Performance optimization opportunity: {issue_type}',
                        'suggestion': suggestion
                    })

        return {
            'total_issues': len(performance_issues),
            'issues_by_type': self._group_by_type(performance_issues),
            'issues': performance_issues
        }

    def _assess_code_quality(self, code: str, language: str) -> Dict[str, Any]:
        """Assess code quality and style issues."""
        quality_issues = []
        lines = code.split('\n')

        # Function/method length analysis
        function_lines = 0
        in_function = False
        function_start = 0

        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()

            # Function start detection (basic)
            if any(keyword in line_stripped for keyword in ['def ', 'function ', 'class ']):
                if in_function and function_lines > 50:
                    quality_issues.append({
                        'type': 'long_function',
                        'severity': 'medium',
                        'line': function_start,
                        'message': f'Function/method is {function_lines} lines long',
                        'suggestion': 'Consider breaking down large functions into smaller, focused functions'
                    })

                in_function = True
                function_start = i
                function_lines = 0

            if in_function:
                function_lines += 1

        # Final function check
        if in_function and function_lines > 50:
            quality_issues.append({
                'type': 'long_function',
                'severity': 'medium',
                'line': function_start,
                'message': f'Function/method is {function_lines} lines long',
                'suggestion': 'Consider breaking down large functions into smaller, focused functions'
            })

        # Magic numbers
        magic_number_pattern = r'\b\d{2,}\b'
        matches = re.finditer(magic_number_pattern, code)
        for match in matches:
            line_num = code[:match.start()].count('\n') + 1
            number = match.group()

            # Skip common non-magic numbers
            if number not in ['100', '200', '404', '500', '1000', '1024']:
                quality_issues.append({
                    'type': 'magic_number',
                    'severity': 'low',
                    'line': line_num,
                    'message': f'Magic number {number} found',
                    'suggestion': 'Consider using named constants for magic numbers'
                })

        # Commented out code
        for i, line in enumerate(lines, 1):
            line_stripped = line.strip()
            if (line_stripped.startswith('#') or line_stripped.startswith('//')) and \
               any(keyword in line_stripped for keyword in ['def ', 'function ', 'class ', 'if ', 'for ', 'while ']):
                quality_issues.append({
                    'type': 'commented_code',
                    'severity': 'low',
                    'line': i,
                    'message': 'Commented out code found',
                    'suggestion': 'Remove commented code or use version control instead'
                })

        # Missing documentation
        if not any(line.strip().startswith('"""') or line.strip().startswith('/*') for line in lines):
            quality_issues.append({
                'type': 'missing_docs',
                'severity': 'low',
                'line': 1,
                'message': 'No documentation found',
                'suggestion': 'Add docstrings or comments to explain the code purpose'
            })

        return {
            'total_issues': len(quality_issues),
            'maintainability_score': max(0, 100 - len(quality_issues) * 5),
            'issues': quality_issues
        }

    def _get_ai_suggestions(self, code: str, language: str, filename: str) -> Optional[Dict[str, Any]]:
        """Get AI-powered code improvement suggestions."""
        if not self.openai_client:
            return None

        try:
            prompt = """
            Please analyze this {language} code and provide suggestions for improvement:

            Filename: {filename}
            Language: {language}

            Code:
            ```{language}
            {code[:2000]}  # Limit to first 2000 chars
            ```

            Please provide suggestions in the following categories:
            1. Code Quality & Style
            2. Performance Optimizations
            3. Security Considerations
            4. Best Practices
            5. Potential Bugs

            Format your response as JSON with this structure:
            {
                "overall_assessment": "Brief overall assessment",
                "suggestions": [
                    {
                        "category": "category_name",
                        "priority": "high|medium|low",
                        "description": "Description of the issue",
                        "suggestion": "Specific improvement suggestion",
                        "example": "Optional code example"
                    }
                ]
            }
            """

            response = self.openai_client.chat.completions.create(
                model=self.config.get('openai_model', 'gpt-4-0613'),
                messages=[
                    {"role": "system", "content": "You are an expert code reviewer. Provide concise, actionable suggestions."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1500,
                temperature=0.3
            )

            # Parse AI response
            ai_response = response.choices[0].message.content

            # Try to extract JSON from response
            try:
                # Look for JSON block
                json_start = ai_response.find('{')
                json_end = ai_response.rfind('}') + 1

                if json_start != -1 and json_end != -1:
                    json_str = ai_response[json_start:json_end]
                    return json.loads(json_str)
            except json.JSONDecodeError:
                pass

            # Fallback: return raw response
            return {
                "overall_assessment": "AI analysis completed",
                "suggestions": [{
                    "category": "ai_analysis",
                    "priority": "medium",
                    "description": "AI-powered code review",
                    "suggestion": ai_response[:500] + "..." if len(ai_response) > 500 else ai_response
                }]
            }

        except Exception as e:
            self.logger.error(f"AI suggestion generation failed: {e}")
            return {
                "overall_assessment": "AI analysis unavailable",
                "error": str(e)
            }

    def _load_language_patterns(self) -> Dict[str, Any]:
        """Load language-specific analysis patterns."""
        return {
            'python': {
                'imports': ['import os', 'import sys', 'import json'],
                'conventions': ['snake_case', 'PEP8'],
                'security_patterns': ['eval(', 'exec(', 'input(', '__import__']
            },
            'javascript': {
                'imports': ['require(', 'import ', 'from '],
                'conventions': ['camelCase', 'ESLint'],
                'security_patterns': ['eval(', 'innerHTML', 'document.write']
            },
            'java': {
                'imports': ['import ', 'package '],
                'conventions': ['CamelCase', 'checkstyle'],
                'security_patterns': ['Runtime.exec', 'System.exit', 'reflection']
            }
        }

    def _analyze_language_specific(self, code: str, language: str) -> List[Dict[str, Any]]:
        """Perform language-specific analysis."""
        issues = []
        patterns = self.language_patterns.get(language, {})

        # Check for language-specific security patterns
        security_patterns = patterns.get('security_patterns', [])
        for pattern in security_patterns:
            if pattern in code:
                line_num = code.find(pattern)
                line_num = code[:line_num].count('\n') + 1 if line_num != -1 else 1

                issues.append({
                    'type': 'security_pattern',
                    'severity': 'high',
                    'line': line_num,
                    'message': f'Potentially unsafe {language} pattern: {pattern}',
                    'suggestion': f'Review usage of {pattern} for security implications'
                })

        return issues

    def _group_by_severity(self, issues: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group issues by severity level."""
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}

        for issue in issues:
            severity = issue.get('severity', 'low')
            if severity in severity_counts:
                severity_counts[severity] += 1

        return severity_counts

    def _group_by_type(self, issues: List[Dict[str, Any]]) -> Dict[str, int]:
        """Group issues by type."""
        type_counts = {}

        for issue in issues:
            issue_type = issue.get('type', 'unknown')
            type_counts[issue_type] = type_counts.get(issue_type, 0) + 1

        return type_counts

    def _calculate_overall_score(self, file_analyses: List[Dict[str, Any]]) -> int:
        """Calculate overall code quality score."""
        if not file_analyses:
            return 100

        total_score = 0
        for analysis in file_analyses:
            score = analysis.get('score', 50)
            total_score += score

        return int(total_score / len(file_analyses))

    def _calculate_snippet_score(self, static_analysis: Dict, security_issues: Dict,
                                 performance_issues: Dict, quality_issues: Dict) -> int:
        """Calculate code quality score for a snippet."""
        base_score = 100

        # Deduct points for issues
        deductions = 0
        deductions += security_issues.get('critical_count', 0) * 25
        deductions += security_issues.get('high_count', 0) * 15
        deductions += static_analysis.get('issues_by_severity', {}).get('high', 0) * 10
        deductions += static_analysis.get('issues_by_severity', {}).get('medium', 0) * 5
        deductions += performance_issues.get('total_issues', 0) * 3
        deductions += quality_issues.get('total_issues', 0) * 2

        return max(0, base_score - deductions)

    def _generate_review_summary(self, file_analyses: List[Dict[str, Any]], pr_data: Dict[str, Any]) -> str:
        """Generate a comprehensive review summary."""
        if not file_analyses:
            return "No code changes to analyze."

        total_files = len(file_analyses)
        total_issues = sum(
            analysis.get('static_analysis', {}).get('total_issues', 0) +
            analysis.get('security_issues', {}).get('total_vulnerabilities', 0) +
            analysis.get('performance_issues', {}).get('total_issues', 0) +
            analysis.get('quality_issues', {}).get('total_issues', 0)
            for analysis in file_analyses
        )

        overall_score = self._calculate_overall_score(file_analyses)

        # Security assessment
        critical_security = sum(
            analysis.get('security_issues', {}).get('critical_count', 0)
            for analysis in file_analyses
        )

        summary = """
## 🔍 Code Review Summary

**Overall Quality Score**: {overall_score}/100
**Files Analyzed**: {total_files}
**Total Issues Found**: {total_issues}

### Security Assessment
- **Critical Vulnerabilities**: {critical_security}
- **Security Status**: {'⚠️ NEEDS ATTENTION' if critical_security > 0 else '✅ NO CRITICAL ISSUES'}

### Code Quality
- **Maintainability**: {'Good' if overall_score >= 80 else 'Needs Improvement' if overall_score >= 60 else 'Poor'}
- **Performance**: {'Optimized' if sum(a.get('performance_issues', {}).get('total_issues', 0) for a in file_analyses) == 0 else 'Has Optimization Opportunities'}

### Recommendations
"""

        if critical_security > 0:
            summary += "- 🚨 **URGENT**: Address critical security vulnerabilities before merging\n"

        if overall_score < 70:
            summary += "- 📝 Consider refactoring to improve code quality\n"

        if total_issues > 10:
            summary += "- 🔧 Multiple issues found - prioritize high-severity items\n"

        if overall_score >= 90:
            summary += "- ✨ Excellent code quality! Great work!\n"

        return summary.strip()

    def _generate_ai_insights(self, file_analyses: List[Dict[str, Any]], pr_data: Dict[str, Any]) -> Optional[str]:
        """Generate AI-powered insights about the PR."""
        if not self.openai_client or not file_analyses:
            return None

        try:
            # Prepare context for AI
            issues_summary = []
            for analysis in file_analyses:
                filename = analysis.get('filename', 'unknown')
                score = analysis.get('score', 0)
                security_count = analysis.get('security_issues', {}).get('total_vulnerabilities', 0)

                issues_summary.append(f"- {filename}: Score {score}/100, {security_count} security issues")

            prompt = """
            Analyze this pull request and provide high-level insights:

            PR Title: {pr_data.get('title', 'Unknown')}
            Files Changed: {len(file_analyses)}

            File Analysis Summary:
            {chr(10).join(issues_summary[:10])}  # Limit to first 10 files

            Provide a brief, insightful summary focusing on:
            1. Overall code quality trends
            2. Risk assessment
            3. Strategic recommendations

            Keep it concise (2-3 sentences max).
            """

            response = self.openai_client.chat.completions.create(
                model=self.config.get('openai_model', 'gpt-4-0613'),
                messages=[
                    {"role": "system", "content": "You are a senior code reviewer providing strategic insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            self.logger.error(f"AI insights generation failed: {e}")
            return None

    def _generate_recommendations(self, file_analyses: List[Dict[str, Any]]) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Security recommendations
        critical_security = sum(
            analysis.get('security_issues', {}).get('critical_count', 0)
            for analysis in file_analyses
        )

        if critical_security > 0:
            recommendations.append("🚨 Address critical security vulnerabilities immediately")

        # Performance recommendations
        performance_issues = sum(
            analysis.get('performance_issues', {}).get('total_issues', 0)
            for analysis in file_analyses
        )

        if performance_issues > 5:
            recommendations.append("⚡ Review performance optimization opportunities")

        # Code quality recommendations
        overall_score = self._calculate_overall_score(file_analyses)

        if overall_score < 60:
            recommendations.append("📝 Consider significant refactoring to improve maintainability")
        elif overall_score < 80:
            recommendations.append("🔧 Minor improvements needed for better code quality")

        # AI suggestions
        ai_suggestions_count = sum(
            1 for analysis in file_analyses
            if analysis.get('ai_suggestions') and analysis['ai_suggestions'].get('suggestions')
        )

        if ai_suggestions_count > 0:
            recommendations.append("🤖 Review AI-powered suggestions for additional improvements")

        return recommendations if recommendations else ["✅ Code looks good overall!"]

    def _extract_security_concerns(self, file_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract all security concerns from analyses."""
        security_concerns = []

        for analysis in file_analyses:
            filename = analysis.get('filename', 'unknown')
            vulnerabilities = analysis.get('security_issues', {}).get('vulnerabilities', [])

            for vuln in vulnerabilities:
                security_concerns.append({
                    'filename': filename,
                    'type': vuln.get('type'),
                    'severity': vuln.get('severity'),
                    'line': vuln.get('line'),
                    'message': vuln.get('message'),
                    'suggestion': vuln.get('suggestion')
                })

        # Sort by severity
        severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
        security_concerns.sort(key=lambda x: severity_order.get(x['severity'], 4))

        return security_concerns

    def _extract_performance_suggestions(self, file_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract all performance suggestions from analyses."""
        performance_suggestions = []

        for analysis in file_analyses:
            filename = analysis.get('filename', 'unknown')
            issues = analysis.get('performance_issues', {}).get('issues', [])

            for issue in issues:
                performance_suggestions.append({
                    'filename': filename,
                    'type': issue.get('type'),
                    'line': issue.get('line'),
                    'message': issue.get('message'),
                    'suggestion': issue.get('suggestion')
                })

        return performance_suggestions


def create_code_review_analyzer(github_client: GitHubClient,
                                config: Dict[str, Any] = None) -> Optional[CodeReviewAnalyzer]:
    """
    Create a code review analyzer instance.

    Args:
        github_client: Authenticated GitHub client
        config: Configuration dictionary

    Returns:
        CodeReviewAnalyzer instance or None if not available
    """
    if not github_client or not github_client.is_authenticated():
        return None

    return CodeReviewAnalyzer(github_client, config)
