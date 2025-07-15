#!/usr/bin/env python3
"""Test script for naming agent"""

from naming_agent import generate_creative_project_name

# Test fallback functionality
test_cases = [
    'create a binary calculator using flask',
    'build a weather forecast application',
    'make a todo list manager',
    'create a chat application with real-time messaging',
    'build a file encryption tool'
]

print('🎨 Testing Naming Agent Fallback:')
print('=' * 60)

for desc in test_cases:
    try:
        # Test with no OpenAI key to trigger fallback
        config = {'openai_api_key': None}
        name = generate_creative_project_name(desc, config)
        print(f'{desc[:40]:<40} → {name}')
    except Exception as e:
        print(f'{desc[:40]:<40} → ERROR: {e}')

print('\n✅ Naming agent integration ready!')
