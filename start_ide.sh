#!/bin/bash
# MeistroCraft IDE Startup Script
# Automatically sets up virtual environment and starts the web interface

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR="venv"
PYTHON_MIN_VERSION="3.8"

echo -e "${BLUE}🚀 MeistroCraft IDE Startup Script${NC}"
echo "=================================="

# Function to check Python version
check_python_version() {
    local python_cmd=$1
    if command -v "$python_cmd" >/dev/null 2>&1; then
        local version=$($python_cmd --version 2>&1 | cut -d' ' -f2)
        local major=$(echo $version | cut -d'.' -f1)
        local minor=$(echo $version | cut -d'.' -f2)
        
        if [ "$major" -ge 3 ] && [ "$minor" -ge 8 ]; then
            echo "$python_cmd"
            return 0
        fi
    fi
    return 1
}

# Find suitable Python executable
echo -e "${YELLOW}🔍 Checking Python installation...${NC}"
PYTHON_CMD=""
for cmd in python3.11 python3.10 python3.9 python3.8 python3 python; do
    if PYTHON_CMD=$(check_python_version "$cmd"); then
        echo -e "${GREEN}✅ Found Python: $PYTHON_CMD${NC}"
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}❌ Error: Python 3.8 or higher is required${NC}"
    echo "Please install Python 3.8+ and try again"
    exit 1
fi

# Check if we're in the right directory
if [ ! -f "web_server.py" ]; then
    echo -e "${RED}❌ Error: Please run this script from the MeistroCraft directory${NC}"
    echo "   (The directory containing web_server.py)"
    exit 1
fi

# Check if config exists
if [ ! -f "config/config.json" ]; then
    echo -e "${YELLOW}⚠️  Configuration file not found${NC}"
    echo "   Copying template to config/config.json..."
    if [ -f "config/config.template.json" ]; then
        cp config/config.template.json config/config.json
        echo -e "${GREEN}✅ Configuration template copied${NC}"
        echo -e "${YELLOW}📝 Please edit config/config.json and add your API keys${NC}"
    else
        echo -e "${RED}❌ Error: config.template.json not found${NC}"
        exit 1
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    $PYTHON_CMD -m venv "$VENV_DIR"
    echo -e "${GREEN}✅ Virtual environment created${NC}"
else
    echo -e "${GREEN}✅ Virtual environment already exists${NC}"
fi

# Activate virtual environment
echo -e "${YELLOW}🔧 Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo -e "${YELLOW}📦 Upgrading pip...${NC}"
python -m pip install --upgrade pip

# Install/upgrade requirements
echo -e "${YELLOW}📦 Installing/updating dependencies...${NC}"
pip install -r requirements.txt

echo -e "${GREEN}✅ Dependencies installed successfully${NC}"

# Check if all required modules can be imported
echo -e "${YELLOW}🧪 Testing imports...${NC}"
python -c "
import fastapi
import uvicorn
import openai
import websockets
print('✅ All imports successful')
" || {
    echo -e "${RED}❌ Error: Some dependencies failed to import${NC}"
    exit 1
}

# Start the web server
echo ""
echo -e "${GREEN}🌐 Starting MeistroCraft IDE Web Server...${NC}"
echo -e "${BLUE}📖 Open your browser to: http://localhost:8000${NC}"
echo -e "${BLUE}🔧 API docs available at: http://localhost:8000/docs${NC}"
echo -e "${YELLOW}⏹️  Press Ctrl+C to stop${NC}"
echo ""

# Start the server
python web_server.py