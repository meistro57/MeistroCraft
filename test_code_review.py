#!/usr/bin/env python3
"""
Comprehensive test suite for AI-powered code review functionality.
Tests the CodeReviewAnalyzer and integration with PR workflow.
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch, MagicMock

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestCodeReviewAnalyzer(unittest.TestCase):
    """Test the AI-powered code review analyzer."""

    def setUp(self):
        """Set up test environment."""
        # Mock GitHub client
        self.mock_github = Mock()
        self.mock_github.is_authenticated.return_value = True

        # Test configuration
        self.test_config = {
            'openai_api_key': 'test_openai_key',
            'openai_model': 'gpt-4-0613',
            'enable_ai_review': True
        }

    def test_code_review_analyzer_initialization(self):
        """Test CodeReviewAnalyzer initialization."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        self.assertEqual(analyzer.github, self.mock_github)
        self.assertEqual(analyzer.config, self.test_config)
        self.assertIsNotNone(analyzer.review_categories)
        self.assertIsNotNone(analyzer.language_patterns)

    def test_detect_language_by_extension(self):
        """Test language detection by file extension."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        test_cases = [
            ('test.py', 'print("hello")', 'python'),
            ('app.js', 'console.log("hello")', 'javascript'),
            ('style.css', 'body { color: red; }', 'css'),
            ('README.md', '# Title', 'markdown'),
            ('Dockerfile', 'FROM ubuntu', 'dockerfile'),
            ('unknown.xyz', 'some code', 'unknown')
        ]

        for filename, code, expected_lang in test_cases:
            with self.subTest(filename=filename):
                detected = analyzer._detect_language(filename, code)
                self.assertEqual(detected, expected_lang)

    def test_security_vulnerability_detection(self):
        """Test security vulnerability detection."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test SQL injection detection
        vulnerable_code = '''
        query = "SELECT * FROM users WHERE id = " + user_id
        cursor.execute(query)
        '''

        result = analyzer._scan_security_vulnerabilities(vulnerable_code, 'python')

        self.assertGreater(result['total_vulnerabilities'], 0)
        self.assertTrue(any(v['type'] == 'sql_injection' for v in result['vulnerabilities']))

    def test_hardcoded_secrets_detection(self):
        """Test hardcoded secrets detection."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test hardcoded secret detection
        secret_code = '''
        api_key = "sk-abcd1234567890"
        password = "secretpassword123"
        '''

        result = analyzer._scan_security_vulnerabilities(secret_code, 'python')

        self.assertGreater(result['total_vulnerabilities'], 0)
        self.assertTrue(any(v['type'] == 'hardcoded_secret' for v in result['vulnerabilities']))

    def test_performance_analysis(self):
        """Test performance issue detection."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test performance issues
        slow_code = '''
        result = ""
        for i in range(1000):
            result += str(i)  # Inefficient string concatenation
        '''

        result = analyzer._analyze_performance(slow_code, 'python')

        self.assertGreater(result['total_issues'], 0)
        self.assertTrue(any(issue['type'] == 'string_concatenation' for issue in result['issues']))

    def test_code_quality_assessment(self):
        """Test code quality assessment."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test long function detection
        long_function_code = '''
        def long_function():
        ''' + '    pass\n' * 60  # 60 lines

        result = analyzer._assess_code_quality(long_function_code, 'python')

        self.assertGreater(result['total_issues'], 0)
        self.assertTrue(any(issue['type'] == 'long_function' for issue in result['issues']))

    def test_code_snippet_analysis(self):
        """Test complete code snippet analysis."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        test_code = '''
        def process_data(user_input):
            query = "SELECT * FROM users WHERE name = '" + user_input + "'"
            result = ""
            for i in range(100):
                result += str(i)
            return result
        '''

        result = analyzer.analyze_code_snippet(test_code, 'test.py', 'python')

        # Check structure
        self.assertIn('filename', result)
        self.assertIn('language', result)
        self.assertIn('score', result)
        self.assertIn('security_issues', result)
        self.assertIn('performance_issues', result)
        self.assertIn('quality_issues', result)

        # Should detect security and performance issues
        self.assertGreater(result['security_issues']['total_vulnerabilities'], 0)
        self.assertGreater(result['performance_issues']['total_issues'], 0)

    def test_static_analysis(self):
        """Test static analysis functionality."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test code with various issues
        problematic_code = '''
        def function_with_issues():
            # TODO: Fix this later
            print("Debug statement")  # Debug code
            very_long_line_that_exceeds_the_recommended_character_limit_and_should_be_flagged_by_the_analyzer_as_too_long = 42
        '''

        result = analyzer._perform_static_analysis(problematic_code, 'python')

        self.assertGreater(result['total_issues'], 0)

        # Check for specific issue types
        issue_types = [issue['type'] for issue in result['issues']]
        self.assertIn('todo', issue_types)
        self.assertIn('debug_code', issue_types)

    def test_calculate_score(self):
        """Test score calculation logic."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test with no issues (should be high score)
        static_analysis = {'issues_by_severity': {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}}
        security_issues = {'critical_count': 0, 'high_count': 0}
        performance_issues = {'total_issues': 0}
        quality_issues = {'total_issues': 0}

        score = analyzer._calculate_snippet_score(static_analysis, security_issues, performance_issues, quality_issues)
        self.assertEqual(score, 100)

        # Test with critical security issue (should lower score significantly)
        security_issues = {'critical_count': 1, 'high_count': 0}
        score = analyzer._calculate_snippet_score(static_analysis, security_issues, performance_issues, quality_issues)
        self.assertEqual(score, 75)  # 100 - 25 for critical issue


class TestCodeReviewIntegration(unittest.TestCase):
    """Test integration of code review with PR workflow."""

    def setUp(self):
        """Set up test environment."""
        self.mock_github = Mock()
        self.mock_github.is_authenticated.return_value = True

        self.test_config = {
            'openai_api_key': 'test_openai_key',
            'enable_ai_review': True
        }

    def test_pr_manager_with_code_review(self):
        """Test PullRequestManager with code review integration."""
        from github_workflows import PullRequestManager

        pr_manager = PullRequestManager(self.mock_github, self.test_config)

        # Check that code review analyzer is initialized
        self.assertIsNotNone(pr_manager.code_review_analyzer)

    def test_ai_review_comment_generation(self):
        """Test AI review comment generation."""
        from github_workflows import PullRequestManager

        pr_manager = PullRequestManager(self.mock_github, self.test_config)

        # Mock review analysis
        review_analysis = {
            'overall_score': 75,
            'summary': 'Code quality is good with minor issues',
            'security_concerns': [
                {
                    'filename': 'test.py',
                    'line': 10,
                    'severity': 'high',
                    'message': 'Potential SQL injection',
                    'suggestion': 'Use parameterized queries'
                }
            ],
            'performance_suggestions': [
                {
                    'filename': 'test.py',
                    'line': 15,
                    'message': 'String concatenation in loop',
                    'suggestion': 'Use join() method'
                }
            ],
            'recommendations': ['Review security issues', 'Optimize performance'],
            'ai_insights': 'Overall good code with room for improvement'
        }

        task = {
            'action': 'modify_file',
            'filename': 'test.py',
            'instruction': 'Add error handling'
        }

        result = {'success': True}

        comment = pr_manager._generate_ai_review_comment(review_analysis, task, result)

        # Check comment structure
        self.assertIn('🤖 AI-Powered Code Review', comment)
        self.assertIn('Overall Quality Score**: 75/100', comment)
        self.assertIn('🔒 Security Analysis', comment)
        self.assertIn('⚡ Performance Optimization', comment)
        self.assertIn('🧠 AI Strategic Insights', comment)
        self.assertIn('🎯 MeistroCraft Task Context', comment)
        self.assertIn('✅ Overall Assessment', comment)  # 75 score = good

    def test_different_score_assessments(self):
        """Test different overall assessments based on scores."""
        from github_workflows import PullRequestManager

        pr_manager = PullRequestManager(self.mock_github, self.test_config)

        test_cases = [
            (95, '✨ Overall Assessment', 'Excellent work'),
            (75, '✅ Overall Assessment', 'Good quality code'),
            (55, '⚠️ Overall Assessment', 'Needs attention'),
            (25, '🚨 Overall Assessment', 'Significant issues')
        ]

        for score, expected_icon, expected_text in test_cases:
            with self.subTest(score=score):
                review_analysis = {
                    'overall_score': score,
                    'summary': f'Test with score {score}',
                    'security_concerns': [],
                    'performance_suggestions': [],
                    'recommendations': [],
                    'ai_insights': None
                }

                comment = pr_manager._generate_ai_review_comment(review_analysis)

                self.assertIn(expected_icon, comment)
                self.assertIn(expected_text, comment)


class TestSecurityPatterns(unittest.TestCase):
    """Test security pattern detection."""

    def setUp(self):
        """Set up test environment."""
        self.mock_github = Mock()
        self.test_config = {}

    def test_sql_injection_patterns(self):
        """Test SQL injection pattern detection."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        vulnerable_codes = [
            'SELECT * FROM users WHERE id = " + user_id',
            'query = "DELETE FROM table WHERE name = " + user_name',
            'cursor.execute("INSERT INTO logs VALUES (" + value + ")")'
        ]

        for code in vulnerable_codes:
            with self.subTest(code=code[:30]):
                result = analyzer._scan_security_vulnerabilities(code, 'python')
                self.assertGreater(result['total_vulnerabilities'], 0)

    def test_xss_patterns(self):
        """Test XSS pattern detection."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        vulnerable_codes = [
            'element.innerHTML = userInput + "<br>"',
            'document.write(userData)',
            'eval("user" + "Code")'
        ]

        for code in vulnerable_codes:
            with self.subTest(code=code[:30]):
                result = analyzer._scan_security_vulnerabilities(code, 'javascript')
                self.assertGreater(result['total_vulnerabilities'], 0)

    def test_safe_code_patterns(self):
        """Test that safe code doesn't trigger false positives."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        safe_codes = [
            'cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))',
            'element.textContent = userInput',
            'const result = JSON.parse(validJson)'
        ]

        for code in safe_codes:
            with self.subTest(code=code[:30]):
                result = analyzer._scan_security_vulnerabilities(code, 'python')
                # Should have fewer or no vulnerabilities
                self.assertLessEqual(result['critical_count'], 0)


class TestPerformanceAnalysis(unittest.TestCase):
    """Test performance analysis functionality."""

    def setUp(self):
        """Set up test environment."""
        self.mock_github = Mock()
        self.test_config = {}

    def test_python_performance_patterns(self):
        """Test Python-specific performance pattern detection."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test inefficient patterns
        inefficient_code = '''
        for i in range(len(items)):
            print(items[i])

        result = []
        for item in items:
            result.append(item.upper())

        global_var = "bad"
        '''

        result = analyzer._analyze_performance(inefficient_code, 'python')

        self.assertGreater(result['total_issues'], 0)

        # Check for specific optimization suggestions
        issue_types = [issue['type'] for issue in result['issues']]
        self.assertTrue(any(
            'enumerate' in issue_type or 'list_comprehension' in issue_type or 'global' in issue_type for issue_type in issue_types))

    def test_javascript_performance_patterns(self):
        """Test JavaScript-specific performance pattern detection."""
        from code_review_analyzer import CodeReviewAnalyzer

        analyzer = CodeReviewAnalyzer(self.mock_github, self.test_config)

        # Test inefficient patterns
        inefficient_code = '''
        document.getElementById("myElement").style.color = "red";
        document.getElementById("myElement").style.background = "blue";

        setTimeout(function() { console.log("test"); }, 0);

        for (var key in object) {
            console.log(object[key]);
        }
        '''

        result = analyzer._analyze_performance(inefficient_code, 'javascript')

        self.assertGreater(result['total_issues'], 0)


def run_code_review_tests():
    """Run comprehensive code review tests."""
    print("🧪 AI-Powered Code Review - Comprehensive Test Suite")
    print("=" * 60)

    # Test modules
    test_modules = [
        TestCodeReviewAnalyzer,
        TestCodeReviewIntegration,
        TestSecurityPatterns,
        TestPerformanceAnalysis
    ]

    total_tests = 0
    total_passed = 0

    for test_module in test_modules:
        print(f"\n📋 Running {test_module.__name__}...")
        print("-" * 40)

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
                print(f"      - {test}: {traceback.split('Exception:')[-1].strip()}")

        status = "✅ PASSED" if module_passed == module_tests else "❌ FAILED"
        print(f"   Status: {status}")

    print("\n" + "=" * 60)
    print("📊 Overall Test Results:")
    print(f"   Total Tests: {total_tests}")
    print(f"   Passed: {total_passed}")
    print(f"   Failed: {total_tests - total_passed}")
    print(f"   Success Rate: {(total_passed/total_tests)*100:.1f}%")

    if total_passed == total_tests:
        print("\n🎉 All AI Code Review tests passed!")
        print("\n✅ Features validated:")
        print("   - 🔒 Security vulnerability detection")
        print("   - ⚡ Performance optimization suggestions")
        print("   - 📝 Code quality assessment")
        print("   - 🤖 AI-powered insights integration")
        print("   - 🔗 PR workflow integration")
        print("   - 🎯 MeistroCraft task context")

        print("\n🚀 AI-powered code review is ready for production!")
        return True
    else:
        print(f"\n⚠️  {total_tests - total_passed} tests failed. Please review above.")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--comprehensive':
        success = run_code_review_tests()
        sys.exit(0 if success else 1)
    else:
        # Run standard unittest
        unittest.main()
