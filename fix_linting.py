#!/usr/bin/env python3
"""
Script to fix common flake8 linting issues in the MeistroCraft codebase
"""

import os
import re
import subprocess


def fix_file(filepath):
    """Fix common linting issues in a Python file"""
    print(f"Fixing {filepath}")

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        original_content = content

        # Fix trailing whitespace (W291)
        content = re.sub(r'[ \t]+$', '', content, flags=re.MULTILINE)

        # Fix blank lines containing whitespace (W293)
        content = re.sub(r'^[ \t]+$', '', content, flags=re.MULTILINE)

        # Ensure file ends with newline (W292)
        if content and not content.endswith('\n'):
            content += '\n'

        # Fix multiple blank lines - ensure 2 blank lines before class/function definitions
        # This is a simplified approach for E302 errors
        content = re.sub(r'\n\n\n+', '\n\n', content)

        # Remove unused imports (basic cases)
        lines = content.split('\n')
        new_lines = []

        for line in lines:
            # Skip obvious unused imports based on common patterns
            if (line.strip().startswith('import ') or line.strip().startswith('from ')) and \
               ('imported but unused' in line or
                'typing.Optional' in line or
                'json' in line or
                    'asyncio' in line):
                # Check if the import is actually used later in the file
                import_name = line.split()[-1] if 'import' in line else None
                if import_name and import_name not in content.replace(line, ''):
                    continue  # Skip unused import

            new_lines.append(line)

        content = '\n'.join(new_lines)

        # Only write if content changed
        if content != original_content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✅ Fixed {filepath}")
        else:
            print(f"  ⏭️  No changes needed for {filepath}")

    except Exception as e:
        print(f"  ❌ Error fixing {filepath}: {e}")


def main():
    """Main function to fix all Python files"""
    print("🔧 Starting flake8 linting fixes...")

    # Get all Python files in the current directory
    python_files = []
    for root, dirs, files in os.walk('.'):
        # Skip certain directories
        if any(skip in root for skip in ['.git', '__pycache__', 'venv', 'node_modules']):
            continue

        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))

    print(f"Found {len(python_files)} Python files to check")

    # Fix each file
    for filepath in python_files:
        fix_file(filepath)

    print("\n🎯 Running autopep8 for additional fixes...")

    # Try to use autopep8 if available
    try:
        subprocess.run(['pip', 'install', 'autopep8'], check=True)

        # Run autopep8 on all Python files
        for filepath in python_files:
            try:
                subprocess.run([
                    'autopep8',
                    '--in-place',
                    '--max-line-length=120',
                    '--aggressive',
                    '--aggressive',
                    filepath
                ], check=True)
                print(f"  ✅ autopep8 fixed {filepath}")
            except subprocess.CalledProcessError:
                print(f"  ⚠️  autopep8 skipped {filepath}")

    except subprocess.CalledProcessError:
        print("  ⚠️  Could not install autopep8")

    print("\n✨ Linting fixes completed!")
    print("Run 'python -m flake8 .' to check remaining issues")


if __name__ == '__main__':
    main()
