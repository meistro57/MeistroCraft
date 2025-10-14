# MeistroCraft IDE Startup Guide

## Quick Start

Choose your preferred method to start the MeistroCraft IDE:

### Option 1: Cross-Platform Python Script (Recommended)
```bash
./start_ide.py
```

### Option 2: Linux/macOS Shell Script
```bash
./start_ide.sh
```

### Option 3: Windows Batch Script
```cmd
start_ide.bat
```

## What the Start Scripts Do

All start scripts automatically handle:

✅ **Python Version Check** - Ensures Python 3.8+ is available  
✅ **Virtual Environment Setup** - Creates `venv/` directory if needed  
✅ **Dependency Installation** - Installs all requirements from `requirements.txt`  
✅ **Configuration Setup** - Copies template config if needed  
✅ **Import Validation** - Tests that all dependencies work correctly  
✅ **Web Server Launch** - Starts the IDE at http://localhost:8000

## First-Time Setup

1. **API Keys Required**: After running the script for the first time, edit `config/config.json` and add your API keys:
   ```json
   {
     "openai_api_key": "your-openai-key-here",
     "crush_api_key": "your-crush-key-here",
     "github_api_key": "your-github-token-here"
   }
   ```

2. **Restart**: Run the start script again after adding your API keys

## Manual Setup (Alternative)

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # Linux/macOS
# or
venv\Scripts\activate.bat  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy configuration template
cp config/config.template.json config/config.json

# Edit config with your API keys
nano config/config.json

# Start the server
python web_server.py
```

## Troubleshooting

### Python Not Found
- Install Python 3.8 or higher from [python.org](https://python.org)
- Ensure Python is in your system PATH

### Permission Denied (Linux/macOS)
```bash
chmod +x start_ide.py start_ide.sh
```

### Virtual Environment Issues
- Delete the `venv/` directory and run the script again
- Ensure you have sufficient disk space

### Dependency Installation Fails
- Check your internet connection
- Try upgrading pip: `python -m pip install --upgrade pip`

## Features

Once started, the IDE provides:

- 🤖 **AI-Powered Development** with GPT-4 and Crush
- 📁 **Project Management** with isolated workspaces  
- 🌐 **Browser-Based Interface** at http://localhost:8000
- 🔧 **Integrated Terminal** and file explorer
- 📝 **Code Editor** with syntax highlighting
- 🔗 **GitHub Integration** for repositories

## Stopping the Server

Press `Ctrl+C` in the terminal to stop the web server.

## Support

If you encounter issues, check:
1. Python version is 3.8+
2. All dependencies are installed correctly
3. Configuration file has valid API keys
4. Port 8000 is not in use by another application