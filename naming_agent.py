"""
Naming Agent for MeistroCraft - Generates creative, concise project names
"""
try:
    import openai
except ImportError:
    openai = None
import re
from typing import Optional, Dict, Any

class NamingAgent:
    """Creative naming agent that generates concise project names from descriptions."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        if openai and config.get("openai_api_key"):
            self.client = openai.OpenAI(api_key=config.get("openai_api_key"))
        else:
            self.client = None
    
    def generate_project_name(self, description: str) -> str:
        """
        Generate a creative, concise project name from a description.
        
        Args:
            description: The app/project description
            
        Returns:
            A clean, filesystem-safe project name (kebab-case, 3-15 chars)
        """
        
        # Creative system prompt for naming
        system_prompt = """You are a creative naming agent for software projects. Your job is to generate concise, memorable, and descriptive project names.

RULES:
- Generate ONE project name only
- 3-15 characters maximum
- Use kebab-case (lowercase with hyphens)
- Be creative and memorable
- Capture the essence of the project
- Avoid generic words like "app", "tool", "system" unless essential
- Use abbreviations intelligently (calc, auth, etc.)
- Make it brandable and distinctive

EXAMPLES:
"create a binary calculator using flask" → "bin-calc"
"build a weather forecast application" → "sky-cast"
"make a todo list manager" → "task-flow"
"create a chat application with real-time messaging" → "chat-pulse"
"build a file encryption tool" → "safe-lock"
"create a music player with playlist support" → "beat-sync"
"make a password generator" → "pass-forge"
"build a QR code scanner app" → "qr-snap"
"create a markdown editor" → "md-craft"
"make a expense tracker" → "coin-track"

Be creative and think like a startup founder naming their product!"""

        user_prompt = f"Generate a project name for: {description}"
        
        # Use OpenAI if available
        if self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.config.get("openai_model", "gpt-4-0613"),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=50,
                    temperature=0.8  # Higher creativity
                )
                
                # Extract the name from response
                generated_name = response.choices[0].message.content.strip()
                
                # Clean and validate the name
                cleaned_name = self._clean_name(generated_name)
                
                # Fallback to simple method if cleaning fails
                if not cleaned_name or len(cleaned_name) < 3:
                    cleaned_name = self._fallback_name(description)
                    
                return cleaned_name
                
            except Exception as e:
                print(f"⚠️  Naming agent failed: {e}")
                # Fallback to simple extraction method
                return self._fallback_name(description)
        else:
            # No OpenAI client, use fallback
            return self._fallback_name(description)
    
    def _clean_name(self, name: str) -> str:
        """Clean and validate the generated name."""
        # Remove quotes, extra spaces, explanations
        name = re.sub(r'^["\']|["\']$', '', name)  # Remove quotes
        name = name.split('\n')[0]  # Take first line only
        name = name.split(' ')[0]  # Take first word if multiple
        
        # Keep only valid characters
        name = re.sub(r'[^a-zA-Z0-9-]', '', name)
        
        # Convert to lowercase
        name = name.lower()
        
        # Validate length
        if 3 <= len(name) <= 15:
            return name
        
        return ""
    
    def _fallback_name(self, description: str) -> str:
        """Fallback method for name generation using simple rules."""
        # Extract key words
        words = re.findall(r'\b\w+\b', description.lower())
        
        # Filter out common words
        stop_words = {'create', 'build', 'make', 'a', 'an', 'the', 'using', 'with', 'for', 'app', 'application'}
        key_words = [w for w in words if w not in stop_words and len(w) > 2]
        
        if not key_words:
            return "my-app"
        
        # Take first 1-2 key words and abbreviate if needed
        if len(key_words) >= 2:
            name = f"{key_words[0][:4]}-{key_words[1][:4]}"
        else:
            name = key_words[0][:8]
        
        # Common abbreviations
        abbreviations = {
            'calculator': 'calc',
            'application': 'app',
            'binary': 'bin',
            'weather': 'weather',
            'forecast': 'cast',
            'manager': 'mgr',
            'generator': 'gen',
            'scanner': 'scan',
            'editor': 'edit',
            'tracker': 'track',
            'player': 'play'
        }
        
        for full, abbr in abbreviations.items():
            name = name.replace(full, abbr)
        
        return name[:15]  # Ensure max length


def generate_creative_project_name(description: str, config: Dict[str, Any]) -> str:
    """
    Public function to generate a creative project name.
    
    Args:
        description: The project description
        config: MeistroCraft configuration
        
    Returns:
        A creative, filesystem-safe project name
    """
    agent = NamingAgent(config)
    return agent.generate_project_name(description)