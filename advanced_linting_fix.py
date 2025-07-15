#!/usr/bin/env python3
"""
Advanced script to fix remaining flake8 issues
"""

import ast
import os
import re

class ImportCleaner(ast.NodeVisitor):
    def __init__(self):
        self.imports = {}
        self.used_names = set()
        
    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports[name] = node
            
    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports[name] = node
            
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
            
    def visit_Attribute(self, node):
        if isinstance(node.value, ast.Name):
            self.used_names.add(node.value.id)
        self.generic_visit(node)

def fix_advanced_issues(filepath):
    """Fix advanced linting issues"""
    print(f"Advanced fixing {filepath}")
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        lines = content.split('\n')
        
        # Fix specific issues
        new_lines = []
        skip_next = False
        
        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue
                
            # Remove unused imports (more comprehensive)
            if line.strip().startswith(('import ', 'from ')) and 'imported but unused' in line:
                # Skip this import
                continue
                
            # Fix long lines by breaking them
            if len(line) > 120:
                # Try to break at logical points
                if ' and ' in line:
                    parts = line.split(' and ')
                    if len(parts) == 2:
                        indent = len(line) - len(line.lstrip())
                        new_lines.append(parts[0] + ' and \\')
                        new_lines.append(' ' * (indent + 4) + parts[1])
                        continue
                elif ', ' in line and '"' in line:
                    # Break f-strings
                    parts = line.split(', ')
                    if len(parts) > 1:
                        indent = len(line) - len(line.lstrip())
                        new_lines.append(parts[0] + ',')
                        for part in parts[1:]:
                            new_lines.append(' ' * (indent + 4) + part)
                        continue
            
            # Fix f-strings without placeholders
            if 'f"' in line and '{' not in line:
                line = line.replace('"', '"')
            elif "f'" in line and '{' not in line:
                line = line.replace("'", "'")
            
            # Fix undefined names
            if 'timedelta' in line and 'from datetime import' not in content:
                if i == 0 or 'import' in lines[i-1]:
                    new_lines.append('from datetime import timedelta')
            
            new_lines.append(line)
        
        # Fix specific import issues
        content = '\n'.join(new_lines)
        
        # Remove unused imports more aggressively
        unused_imports = [
            '',
            'import os',
            '',
            'import time',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            '',
            'from datetime import timedelta',
            '',
            '',
            '',
            '',
            '',
            'from datetime import datetime',
        ]
        
        for unused in unused_imports:
            if unused in content:
                # Check if it's actually used
                import_name = unused.split()[-1]
                if import_name not in content.replace(unused, ''):
                    content = content.replace(unused + '\n', '')
                    content = content.replace(unused, '')
        
        # Write back if changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ Advanced fixed {filepath}")
        else:
            print(f"  ⏭️  No advanced changes needed for {filepath}")
            
    except Exception as e:
        print(f"  ❌ Error in advanced fixing {filepath}: {e}")

def main():
    """Main function"""
    print("🎯 Running advanced linting fixes...")
    
    # Get Python files
    python_files = []
    for root, dirs, files in os.walk('.'):
        if any(skip in root for skip in ['.git', '__pycache__', 'venv']):
            continue
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    # Fix each file
    for filepath in python_files:
        fix_advanced_issues(filepath)
    
    print("\n✨ Advanced linting fixes completed!")

if __name__ == '__main__':
    main()