#!/usr/bin/env python3
"""
MeistroCraft IDE Startup Script (Cross-platform Python version)
Automatically sets up virtual environment and starts the web interface
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path

class Colors:
    """ANSI color codes for terminal output"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color
    
    @classmethod
    def disable_on_windows(cls):
        """Disable colors on Windows if not supported"""
        if platform.system() == 'Windows':
            cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.NC = ''

def print_colored(message, color=Colors.NC):
    """Print colored message"""
    print(f"{color}{message}{Colors.NC}")

def check_python_version(python_cmd, min_version=(3, 8)):
    """Check if Python command meets minimum version requirement"""
    try:
        result = subprocess.run([python_cmd, '--version'], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            version_str = result.stdout.strip().split()[1]
            version_parts = version_str.split('.')
            major, minor = int(version_parts[0]), int(version_parts[1])
            
            if (major, minor) >= min_version:
                return True
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, 
            IndexError, ValueError, FileNotFoundError):
        pass
    return False

def find_python_executable():
    """Find suitable Python executable"""
    candidates = ['python3.11', 'python3.10', 'python3.9', 'python3.8', 
                  'python3', 'python']
    
    for cmd in candidates:
        if shutil.which(cmd) and check_python_version(cmd):
            return cmd
    return None

def setup_virtual_environment(python_cmd, venv_dir):
    """Create and setup virtual environment"""
    venv_path = Path(venv_dir)
    
    if not venv_path.exists():
        print_colored("📦 Creating virtual environment...", Colors.YELLOW)
        result = subprocess.run([python_cmd, '-m', 'venv', str(venv_path)])
        if result.returncode != 0:
            raise RuntimeError("Failed to create virtual environment")
        print_colored("✅ Virtual environment created", Colors.GREEN)
    else:
        print_colored("✅ Virtual environment already exists", Colors.GREEN)
    
    return venv_path

def get_venv_python(venv_path):
    """Get the Python executable inside virtual environment"""
    if platform.system() == 'Windows':
        return venv_path / 'Scripts' / 'python.exe'
    else:
        return venv_path / 'bin' / 'python'

def install_dependencies(venv_python):
    """Install project dependencies"""
    print_colored("📦 Upgrading pip...", Colors.YELLOW)
    subprocess.run([str(venv_python), '-m', 'pip', 'install', '--upgrade', 'pip'],
                   check=True)
    
    print_colored("📦 Installing/updating dependencies...", Colors.YELLOW)
    subprocess.run([str(venv_python), '-m', 'pip', 'install', '-r', 'requirements.txt'],
                   check=True)
    
    print_colored("✅ Dependencies installed successfully", Colors.GREEN)

def test_imports(venv_python):
    """Test if all required modules can be imported"""
    print_colored("🧪 Testing imports...", Colors.YELLOW)
    test_script = """
import fastapi
import uvicorn
import openai
import websockets
print('✅ All imports successful')
"""
    result = subprocess.run([str(venv_python), '-c', test_script], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Import test failed: {result.stderr}")
    print(result.stdout.strip())

def copy_config_template():
    """Copy configuration template if config doesn't exist"""
    config_path = Path('config/config.json')
    template_path = Path('config/config.template.json')
    
    if not config_path.exists():
        print_colored("⚠️  Configuration file not found", Colors.YELLOW)
        if template_path.exists():
            print("   Copying template to config/config.json...")
            shutil.copy2(template_path, config_path)
            print_colored("✅ Configuration template copied", Colors.GREEN)
            print_colored("📝 Please edit config/config.json and add your API keys", Colors.YELLOW)
        else:
            raise FileNotFoundError("config.template.json not found")

def start_web_server(venv_python):
    """Start the MeistroCraft web server"""
    print()
    print_colored("🌐 Starting MeistroCraft IDE Web Server...", Colors.GREEN)
    print_colored("📖 Open your browser to: http://localhost:8000", Colors.BLUE)
    print_colored("🔧 API docs available at: http://localhost:8000/docs", Colors.BLUE)
    print_colored("⏹️  Press Ctrl+C to stop", Colors.YELLOW)
    print()
    
    # Start the server
    subprocess.run([str(venv_python), 'web_server.py'])

def main():
    """Main startup function"""
    # Disable colors on Windows if not supported
    if platform.system() == 'Windows':
        Colors.disable_on_windows()
    
    print_colored("🚀 MeistroCraft IDE Startup Script", Colors.BLUE)
    print("==================================")
    
    try:
        # Check if we're in the right directory
        if not Path('web_server.py').exists():
            print_colored("❌ Error: Please run this script from the MeistroCraft directory", Colors.RED)
            print("   (The directory containing web_server.py)")
            return 1
        
        # Find Python executable
        print_colored("🔍 Checking Python installation...", Colors.YELLOW)
        python_cmd = find_python_executable()
        if not python_cmd:
            print_colored("❌ Error: Python 3.8 or higher is required", Colors.RED)
            print("Please install Python 3.8+ and try again")
            return 1
        
        print_colored(f"✅ Found Python: {python_cmd}", Colors.GREEN)
        
        # Setup configuration
        copy_config_template()
        
        # Setup virtual environment
        venv_path = setup_virtual_environment(python_cmd, 'venv')
        venv_python = get_venv_python(venv_path)
        
        # Install dependencies
        install_dependencies(venv_python)
        
        # Test imports
        test_imports(venv_python)
        
        # Start web server
        start_web_server(venv_python)
        
        return 0
        
    except KeyboardInterrupt:
        print_colored("\n👋 MeistroCraft IDE stopped", Colors.YELLOW)
        return 0
    except Exception as e:
        print_colored(f"❌ Error: {e}", Colors.RED)
        return 1

if __name__ == "__main__":
    sys.exit(main())