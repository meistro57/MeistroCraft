#!/usr/bin/env python3
"""
MeistroCraft Web IDE Launcher
Simple launcher script for the web interface.
"""

import sys
import os


def main():
    """Launch the MeistroCraft Web IDE."""
    print("🎯 MeistroCraft Web IDE Launcher")
    print("=" * 40)

    # Check if we're in the right directory
    if not os.path.exists("web_server.py"):
        print("❌ Error: Please run this script from the MeistroCraft directory")
        print("   (The directory containing web_server.py)")
        sys.exit(1)

    # Check if config exists
    if not os.path.exists("config/config.json"):
        print("❌ Error: Configuration file not found")
        print("   Please copy config/config.template.json to config/config.json")
        print("   and add your API keys")
        sys.exit(1)

    # Import and run the web server
    try:
        from web_server import main as run_web_server
        run_web_server()
    except ImportError as e:
        print(f"❌ Error importing web server: {e}")
        print("   Make sure you've installed the requirements:")
        print("   pip install -r requirements.txt")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Web IDE stopped")
    except Exception as e:
        print(f"❌ Error starting web server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
