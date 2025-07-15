#!/usr/bin/env python3
"""
Fix critical linting issues that are breaking the build
"""

import os
import re

def fix_main_py():
    """Fix main.py critical issues"""
    with open('./main.py', 'r') as f:
        content = f.read()
    
    # Fix undefined timedelta
    if 'from datetime import timedelta' not in content:
        content = content.replace('from datetime import datetime', 'from datetime import datetime, timedelta')
    
    # Fix f-strings without placeholders
    content = re.sub(r'f"([^{]*)"', r'"\1"', content)
    content = re.sub(r"f'([^{]*)'", r"'\1'", content)
    
    with open('./main.py', 'w') as f:
        f.write(content)
    print("✅ Fixed main.py")

def fix_async_input():
    """Fix async_input.py"""
    with open('./async_input.py', 'r') as f:
        content = f.read()
    
    # Remove unused Optional import
    content = content.replace('from typing import Optional\n', '')
    
    with open('./async_input.py', 'w') as f:
        f.write(content)
    print("✅ Fixed async_input.py")

def fix_web_server():
    """Fix web_server.py long lines"""
    with open('./web_server.py', 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        # Fix long lines by breaking them
        if len(line.rstrip()) > 120:
            # Simple line breaking for common patterns
            if ' and ' in line:
                parts = line.split(' and ')
                if len(parts) == 2:
                    indent = len(line) - len(line.lstrip())
                    new_lines.append(parts[0] + ' and \\\n')
                    new_lines.append(' ' * (indent + 4) + parts[1])
                    continue
            elif ', ' in line and len(line.split(', ')) > 2:
                # Break at commas
                parts = line.split(', ')
                indent = len(line) - len(line.lstrip())
                new_lines.append(parts[0] + ',\n')
                for part in parts[1:-1]:
                    new_lines.append(' ' * (indent + 4) + part + ',\n')
                new_lines.append(' ' * (indent + 4) + parts[-1])
                continue
        
        # Fix f-strings without placeholders
        if 'f"' in line and '{' not in line:
            line = line.replace('f"', '"')
        elif "f'" in line and '{' not in line:
            line = line.replace("f'", "'")
        
        new_lines.append(line)
    
    with open('./web_server.py', 'w') as f:
        f.writelines(new_lines)
    print("✅ Fixed web_server.py")

def remove_unused_imports():
    """Remove unused imports from all files"""
    files_to_fix = [
        './build_monitor.py',
        './cicd_integration.py',
        './claude_squad_bridge.py',
        './code_review_analyzer.py',
        './deployment_automation.py',
        './github_client.py',
        './github_workflows.py',
        './interactive_ui.py',
        './token_tracker.py',
        './workspace_manager.py'
    ]
    
    for filepath in files_to_fix:
        try:
            with open(filepath, 'r') as f:
                content = f.read()
            
            # Remove common unused imports
            unused_patterns = [
                r'import json\n',
                r'import os\n',
                r'import sys\n',
                r'import time\n',
                r'import subprocess\n',
                r'import tempfile\n',
                r'import logging\n',
                r'import threading\n',
                r'import contextlib\n',
                r'from typing import Optional\n',
                r'from typing import Tuple\n',
                r'from typing import List\n',
                r'from typing import Callable\n',
                r'from datetime import timedelta\n',
                r'from pathlib import Path\n',
                r'from unittest\.mock import patch\n',
                r'from unittest\.mock import MagicMock\n',
                r'from unittest\.mock import Mock\n',
                r'from unittest\.mock import mock_open\n',
                r'from datetime import datetime\n',
            ]
            
            original_content = content
            for pattern in unused_patterns:
                # Only remove if the import name doesn't appear elsewhere
                import_match = re.search(pattern, content)
                if import_match:
                    import_name = pattern.split()[-1].replace('\\n', '').replace('\\', '')
                    if import_name not in content.replace(import_match.group(0), ''):
                        content = re.sub(pattern, '', content)
            
            if content != original_content:
                with open(filepath, 'w') as f:
                    f.write(content)
                print(f"✅ Cleaned imports in {filepath}")
        except FileNotFoundError:
            pass

def main():
    """Main function"""
    print("🔧 Fixing critical linting issues...")
    
    fix_main_py()
    fix_async_input()
    fix_web_server()
    remove_unused_imports()
    
    print("\n✨ Critical fixes completed!")

if __name__ == '__main__':
    main()