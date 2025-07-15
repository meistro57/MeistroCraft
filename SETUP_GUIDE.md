# MeistroCraft Setup Guide

This guide will help you get MeistroCraft up and running quickly with the new features.

## 🚀 Quick Start

### Option 1: Docker (Recommended)
```bash
# Clone the repository
git clone https://github.com/meistro57/MeistroCraft.git
cd MeistroCraft

# Start with Docker Compose
docker-compose up --build

# Access the Web IDE at http://localhost:8000
```

### Option 2: Python Setup
```bash
# Clone the repository
git clone https://github.com/meistro57/MeistroCraft.git
cd MeistroCraft

# Run the automated setup
python3 start_ide.py

# Access the Web IDE at http://localhost:8000
```

## 🔧 Configuration

### 1. Add Your API Keys

1. Open the Web IDE at http://localhost:8000
2. Click the ⚙️ Settings icon
3. Enter your API keys:
   - **OpenAI API Key**: `sk-your-openai-key-here`
   - **Anthropic API Key**: `sk-ant-your-anthropic-key-here`
   - **GitHub Token**: `ghp_your-github-token-here` (optional)
4. Click "Save Settings"

### 2. Verify Configuration

- Check the console (F12) for `✅ API configuration saved` messages
- Look for the green status indicators in the settings panel
- Test the chatbot by asking a simple question

## 📁 Using the Project Manager

### Access Project Manager
1. Click the 📁 folder icon in the main IDE
2. Or use the keyboard shortcut (if configured)

### Key Features
- **View Modes**: Click ⊞ (grid) or ☰ (list) to switch views
- **Multi-Select**: Use checkboxes to select multiple projects
- **Bulk Actions**: Delete, archive, or restore multiple projects at once
- **Filtering**: Use the dropdown to filter by project status
- **Sorting**: Sort by name, date, size, or last modified

### Bulk Operations
1. Switch to **List View** for easier bulk operations
2. **Select projects** using the checkboxes
3. **Use bulk actions** in the bottom bar (Archive, Restore, Delete)
4. **Confirm action** when prompted

## 🔄 Session Management

### Auto-Resume Feature
- Sessions now automatically resume when you refresh the page
- No more losing your work or creating duplicate sessions
- Session IDs are stored locally for continuity

### Projects vs Sessions
- The system now uses "projects" terminology instead of "sessions"
- Each project gets its own isolated workspace
- Projects persist automatically between browser sessions

## 🐳 Docker Features

### Persistent Data
- **Projects**: Stored in `./projects` volume
- **Sessions**: Stored in `./sessions` volume
- **Configuration**: Stored in `./config` volume

### Container Management
```bash
# View container logs
docker logs meistrocraft-meistrocraft-1

# Restart container
docker restart meistrocraft-meistrocraft-1

# Stop and remove
docker-compose down

# Rebuild and restart
docker-compose up --build
```

## 🔧 Troubleshooting

### API Keys Not Saving
1. **Check browser console** (F12) for error messages
2. **Look for debugging logs**:
   - `🔧 saveSettings() called`
   - `✅ API configuration saved`
   - `❌ Error saving API configuration`
3. **Check container logs** if using Docker

### Session Issues
1. **Clear browser cache** and localStorage
2. **Check for session reuse messages** in container logs:
   - `🔄 Reusing existing MeistroCraft session`
   - `🌐 Created NEW MeistroCraft session`

### Project Manager Issues
1. **Check browser console** for debugging messages:
   - `🔄 Setting view mode to: list`
   - `🗑️ bulkDelete called`
2. **Try refreshing the page** to reset the project manager state

### Docker Issues
1. **Check Docker version**: `docker --version`
2. **Update Docker Compose**: Use v2.0+ for best compatibility
3. **Check volume permissions**: Ensure Docker can write to project folders

## 📊 Debugging Features

### Frontend Debugging
- **Browser Console**: All actions logged with emoji indicators
- **Real-time Status**: Live updates in the console
- **Error Tracking**: Comprehensive error reporting

### Backend Debugging
- **Container Logs**: Real-time logging with emoji indicators
- **API Validation**: Enhanced validation with detailed messages
- **Session Tracking**: Monitor session creation and reuse

## 🎯 Next Steps

1. **Test the chatbot** with a simple request
2. **Create a test project** to verify project management
3. **Try the bulk operations** in the project manager
4. **Explore the settings** to customize your experience

## 📚 Additional Resources

- **README.md**: Comprehensive feature documentation
- **CLAUDE.md**: Technical documentation for developers
- **CHANGELOG.md**: Detailed release notes and improvements

## 🆘 Getting Help

If you encounter issues:

1. **Check the console** (F12) for error messages
2. **Review container logs** if using Docker
3. **Try the troubleshooting steps** in this guide
4. **Check the GitHub issues** for known problems
5. **Create a new issue** with detailed error information

Happy coding with MeistroCraft! 🚀