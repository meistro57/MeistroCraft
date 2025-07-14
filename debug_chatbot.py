#!/usr/bin/env python3
"""Debug script to test chatbot functionality."""

import json
import os
import sys
from main import load_config, generate_task_with_gpt4, run_claude_task, SessionManager, TokenTracker, setup_environment

def debug_chatbot():
    """Debug the chatbot step by step."""
    print("🔍 Debugging MeistroCraft chatbot...")
    
    # Step 1: Load config
    try:
        config = load_config()
        print(f"✅ Config loaded successfully")
        print(f"   OpenAI key present: {'yes' if config.get('openai_api_key') and config['openai_api_key'] != 'sk-your-openai-key-here' else 'no'}")
        print(f"   Anthropic key present: {'yes' if config.get('anthropic_api_key') and config['anthropic_api_key'] != 'sk-ant-your-anthropic-key-here' else 'no'}")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return
    
    # Step 2: Setup environment
    try:
        setup_environment(config)
        print("✅ Environment setup successful")
    except Exception as e:
        print(f"❌ Environment setup failed: {e}")
        return
    
    # Step 3: Initialize components
    try:
        session_manager = SessionManager()
        token_tracker = TokenTracker()
        print("✅ Session manager and token tracker initialized")
    except Exception as e:
        print(f"❌ Component initialization failed: {e}")
        return
    
    # Step 4: Create session
    try:
        session_id = session_manager.create_session("Debug Session", "Testing chatbot")
        print(f"✅ Session created: {session_id}")
    except Exception as e:
        print(f"❌ Session creation failed: {e}")
        return
    
    # Step 5: Test GPT-4 task generation
    try:
        print("\n🤖 Testing GPT-4 task generation...")
        task = generate_task_with_gpt4("Hello, create a simple Python script", config, None, token_tracker, session_id)
        if task:
            print(f"✅ GPT-4 task generated: {task['action']}")
        else:
            print("❌ GPT-4 task generation failed")
            return
    except Exception as e:
        print(f"❌ GPT-4 task generation error: {e}")
        return
    
    # Step 6: Test Claude execution
    try:
        print("\n🔮 Testing Claude execution...")
        result = run_claude_task(task, config, session_id, session_manager, None, token_tracker)
        if result.get("success"):
            print("✅ Claude execution successful")
        else:
            print(f"❌ Claude execution failed: {result.get('error')}")
    except Exception as e:
        print(f"❌ Claude execution error: {e}")
        return
    
    print("\n🎉 All tests passed! Chatbot should be working.")

if __name__ == "__main__":
    debug_chatbot()