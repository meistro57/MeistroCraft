#!/bin/bash

# MeistroCraft Issue Closure Script
# This script automatically closes GitHub issues with detailed comments
# Requires: gh CLI installed and authenticated, or GITHUB_TOKEN environment variable

REPO="meistro57/MeistroCraft"
COMMIT_HASH="c69d037"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 MeistroCraft Issue Closure Script${NC}"
echo "=================================="

# Check if gh CLI is available
if command -v gh &> /dev/null; then
    echo -e "${GREEN}✅ GitHub CLI found${NC}"
    AUTH_METHOD="gh"
elif [ ! -z "$GITHUB_TOKEN" ]; then
    echo -e "${GREEN}✅ GitHub token found in environment${NC}"
    AUTH_METHOD="curl"
else
    echo -e "${RED}❌ No authentication method available${NC}"
    echo "Please either:"
    echo "  1. Install and authenticate GitHub CLI: https://cli.github.com/"
    echo "  2. Set GITHUB_TOKEN environment variable"
    exit 1
fi

# Function to close issue using gh CLI
close_issue_gh() {
    local issue_number=$1
    local comment="$2"
    
    echo -e "${YELLOW}Closing issue #${issue_number} using GitHub CLI...${NC}"
    
    # Add comment
    gh issue comment $issue_number --repo $REPO --body "$comment"
    
    # Close issue
    gh issue close $issue_number --repo $REPO --comment "Issue resolved in commit $COMMIT_HASH"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Issue #${issue_number} closed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to close issue #${issue_number}${NC}"
    fi
}

# Function to close issue using curl
close_issue_curl() {
    local issue_number=$1
    local comment="$2"
    
    echo -e "${YELLOW}Closing issue #${issue_number} using curl...${NC}"
    
    # Add comment
    curl -X POST \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      -H "Content-Type: application/json" \
      -d "{\"body\": \"$comment\"}" \
      "https://api.github.com/repos/$REPO/issues/$issue_number/comments"
    
    # Close issue
    curl -X PATCH \
      -H "Authorization: token $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github.v3+json" \
      -H "Content-Type: application/json" \
      -d '{"state": "closed"}' \
      "https://api.github.com/repos/$REPO/issues/$issue_number"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Issue #${issue_number} closed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to close issue #${issue_number}${NC}"
    fi
}

# Issue #1 comment
ISSUE_1_COMMENT="## Issue Fixed ✅

**Problem:** The GitHub connection test button was producing an error: \`\"str\" object has no attribute \"get\"\`

**Root Cause:** The error handling in the JavaScript code was trying to access \`result.message\` but when the backend raised an HTTPException, the response parsing could fail, and there was insufficient type checking for the GitHub API response.

**Solution Implemented:**

### Backend Changes (\`web_server.py\`):
- Added proper JSON response validation for GitHub API calls
- Added type checking to ensure \`user_data\` is a dictionary, not a string
- Enhanced error handling with try-catch blocks for JSON parsing
- Added fallback error messages for different response types

### Frontend Changes (\`static/js/ide.js\`):
- Added proper HTTP error response handling before JSON parsing
- Added fallback error message handling for both \`detail\` and \`message\` fields
- Enhanced error handling to check response.ok before parsing JSON
- Added proper error propagation and user feedback

### Key Improvements:
- ✅ Fixed the \`\"str\" object has no attribute \"get\"\` error
- ✅ Added robust error handling for all API test buttons (OpenAI, Anthropic, GitHub)
- ✅ Better user feedback for connection failures
- ✅ Proper handling of different response formats

**Testing:** The GitHub connection test now properly handles invalid tokens, network errors, and API response issues with clear error messages.

**Commit:** $COMMIT_HASH - Fix multiple GitHub issues: API configuration persistence, terminal font scaling, and Git connection errors

**Status:** This issue has been resolved and can be closed."

# Issue #2 comment
ISSUE_2_COMMENT="## Issue Fixed ✅

**Problem:** When increasing the font size in the terminal, the command input location gets scaled off the screen.

**Root Cause:** The terminal container was using fixed padding and margins that didn't account for font size changes. The layout used absolute positioning instead of flexible layout that could adapt to font size changes.

**Solution Implemented:**

### CSS Changes (\`templates/ide.html\`):
- Converted terminal container to flexbox layout (\`display: flex; flex-direction: column\`)
- Reduced fixed padding-bottom from 40px to 10px for dynamic sizing
- Added \`.terminal-content\` with \`flex: 1\` to take available space
- Updated \`.terminal-input\` with \`flex-shrink: 0\` to prevent shrinking
- Added proper overflow handling for terminal content
- Reduced margins to scale better with font size changes

### JavaScript Changes (\`static/js/ide.js\`):
- Enhanced font size slider to apply changes immediately to all terminal elements
- Updated \`setupSettingsListeners()\` to handle real-time font size changes
- Modified \`applySettings()\` to properly set font size on container, output, and input
- Added proper font inheritance for terminal container and all child elements

### Key Improvements:
- ✅ Terminal input no longer scales off screen with larger fonts
- ✅ Real-time font size changes apply immediately without needing save/reload
- ✅ Proper flexbox layout adapts to different font sizes
- ✅ Both editor and terminal font size sliders work correctly
- ✅ Maintains proper spacing and layout at all font sizes

**Testing:** Font size can now be increased to large values without the input field disappearing or becoming inaccessible.

**Commit:** $COMMIT_HASH - Fix multiple GitHub issues: API configuration persistence, terminal font scaling, and Git connection errors

**Status:** This issue has been resolved and can be closed."

# Close issues
echo -e "${BLUE}Closing GitHub issues...${NC}"

if [ "$AUTH_METHOD" = "gh" ]; then
    close_issue_gh 1 "$ISSUE_1_COMMENT"
    close_issue_gh 2 "$ISSUE_2_COMMENT"
else
    close_issue_curl 1 "$ISSUE_1_COMMENT"
    close_issue_curl 2 "$ISSUE_2_COMMENT"
fi

echo -e "${GREEN}🎉 Issue closure process completed!${NC}"
echo ""
echo -e "${BLUE}Summary:${NC}"
echo "- Issue #1: GitHub connection test error - FIXED"
echo "- Issue #2: Terminal font size scaling - FIXED"
echo "- Commit: $COMMIT_HASH"
echo "- All changes pushed to master branch"