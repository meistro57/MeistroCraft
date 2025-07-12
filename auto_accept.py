#!/usr/bin/env python3
"""
Auto-Accept Mode for MeistroCraft
Enables automatic acceptance of trusted operations and batch processing.
"""

import json
import re
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path
from enum import Enum


class AutoAcceptLevel(Enum):
    """Auto-accept trust levels."""
    NONE = "none"          # Manual approval required for all tasks
    SAFE = "safe"          # Auto-accept safe operations (read, analyze, document)
    TRUSTED = "trusted"    # Auto-accept trusted operations (create files, simple edits)
    AGGRESSIVE = "aggressive"  # Auto-accept most operations (dangerous: modify, delete)


@dataclass
class AutoAcceptRule:
    """Rule for auto-accepting tasks."""
    pattern: str           # Regex pattern to match task description
    level: AutoAcceptLevel
    conditions: List[str]  # Additional conditions (file types, actions, etc.)
    max_files: int = 5     # Maximum number of files to affect
    exclude_patterns: List[str] = None  # Patterns to exclude
    
    def __post_init__(self):
        if self.exclude_patterns is None:
            self.exclude_patterns = []


class AutoAcceptManager:
    """Manages auto-accept rules and decisions."""
    
    def __init__(self, config_file: str = "auto_accept_config.json"):
        self.config_file = Path(config_file)
        self.rules: List[AutoAcceptRule] = []
        self.global_level = AutoAcceptLevel.NONE
        self.trusted_file_types: Set[str] = set()
        self.safe_actions: Set[str] = set()
        self.dangerous_actions: Set[str] = set()
        
        # Load configuration
        self._load_config()
        self._setup_default_rules()
    
    def _load_config(self) -> None:
        """Load auto-accept configuration."""
        if not self.config_file.exists():
            self._create_default_config()
            return
        
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            self.global_level = AutoAcceptLevel(config.get('global_level', 'none'))
            self.trusted_file_types = set(config.get('trusted_file_types', []))
            self.safe_actions = set(config.get('safe_actions', []))
            self.dangerous_actions = set(config.get('dangerous_actions', []))
            
            # Load custom rules
            for rule_data in config.get('rules', []):
                rule = AutoAcceptRule(
                    pattern=rule_data['pattern'],
                    level=AutoAcceptLevel(rule_data['level']),
                    conditions=rule_data.get('conditions', []),
                    max_files=rule_data.get('max_files', 5),
                    exclude_patterns=rule_data.get('exclude_patterns', [])
                )
                self.rules.append(rule)
                
        except Exception as e:
            print(f"Warning: Failed to load auto-accept config: {e}")
            self._create_default_config()
    
    def _create_default_config(self) -> None:
        """Create default auto-accept configuration."""
        default_config = {
            "global_level": "none",
            "trusted_file_types": [
                ".py", ".js", ".ts", ".html", ".css", ".md", ".txt", ".json", 
                ".yaml", ".yml", ".toml", ".ini", ".cfg"
            ],
            "safe_actions": [
                "read", "analyze", "review", "document", "explain", "summarize",
                "list", "show", "display", "check", "validate", "test", "format"
            ],
            "dangerous_actions": [
                "delete", "remove", "drop", "truncate", "destroy", "purge",
                "overwrite", "replace_all", "reset", "clear", "wipe"
            ],
            "rules": [
                {
                    "pattern": r"create.*test.*file",
                    "level": "trusted",
                    "conditions": ["file_type_trusted"],
                    "max_files": 10
                },
                {
                    "pattern": r"add.*comment.*to",
                    "level": "trusted", 
                    "conditions": ["safe_action"],
                    "max_files": 3
                },
                {
                    "pattern": r"create.*documentation",
                    "level": "trusted",
                    "conditions": ["file_type_trusted"],
                    "max_files": 5
                },
                {
                    "pattern": r"fix.*typo|correct.*spelling",
                    "level": "safe",
                    "conditions": [],
                    "max_files": 3
                }
            ]
        }
        
        with open(self.config_file, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        self._load_config()  # Reload the config we just created
    
    def _setup_default_rules(self) -> None:
        """Set up built-in default rules."""
        # These are always loaded regardless of config
        default_rules = [
            # Always safe operations
            AutoAcceptRule(
                pattern=r"(read|view|show|list|display|get|fetch|retrieve)",
                level=AutoAcceptLevel.SAFE,
                conditions=[]
            ),
            # Documentation operations
            AutoAcceptRule(
                pattern=r"(document|comment|explain|describe|annotate)",
                level=AutoAcceptLevel.SAFE,
                conditions=[]
            ),
            # Simple file creation for trusted types
            AutoAcceptRule(
                pattern=r"create.*\.(py|js|ts|html|css|md|txt|json)$",
                level=AutoAcceptLevel.TRUSTED,
                conditions=["file_type_trusted"],
                max_files=3
            ),
            # Dangerous operations - never auto-accept
            AutoAcceptRule(
                pattern=r"(delete|remove|drop|destroy|purge|wipe|clear|reset)",
                level=AutoAcceptLevel.NONE,
                conditions=[]
            )
        ]
        
        # Add default rules at the beginning (so custom rules take precedence)
        self.rules = default_rules + self.rules
    
    def should_auto_accept(self, task_description: str, task_data: Optional[Dict[str, Any]] = None) -> bool:
        """Determine if a task should be auto-accepted."""
        if self.global_level == AutoAcceptLevel.NONE:
            return False
        
        task_data = task_data or {}
        
        # Check each rule in order
        for rule in self.rules:
            if self._rule_matches(rule, task_description, task_data):
                return self._check_conditions(rule, task_description, task_data)
        
        # If no specific rule matches, use global level
        return self._check_global_level(task_description, task_data)
    
    def _rule_matches(self, rule: AutoAcceptRule, task_description: str, task_data: Dict[str, Any]) -> bool:
        """Check if a rule matches the task."""
        # Check main pattern
        if not re.search(rule.pattern, task_description, re.IGNORECASE):
            return False
        
        # Check exclude patterns
        for exclude_pattern in rule.exclude_patterns:
            if re.search(exclude_pattern, task_description, re.IGNORECASE):
                return False
        
        return True
    
    def _check_conditions(self, rule: AutoAcceptRule, task_description: str, task_data: Dict[str, Any]) -> bool:
        """Check if rule conditions are satisfied."""
        if rule.level == AutoAcceptLevel.NONE:
            return False
        
        for condition in rule.conditions:
            if not self._check_condition(condition, task_description, task_data):
                return False
        
        # Check file count limits
        affected_files = task_data.get('affected_files', [])
        if len(affected_files) > rule.max_files:
            return False
        
        return True
    
    def _check_condition(self, condition: str, task_description: str, task_data: Dict[str, Any]) -> bool:
        """Check a specific condition."""
        if condition == "file_type_trusted":
            affected_files = task_data.get('affected_files', [])
            for file_path in affected_files:
                file_ext = Path(file_path).suffix.lower()
                if file_ext not in self.trusted_file_types:
                    return False
            return True
        
        elif condition == "safe_action":
            action = task_data.get('action', '').lower()
            return action in self.safe_actions
        
        elif condition == "not_dangerous":
            action = task_data.get('action', '').lower()
            for dangerous in self.dangerous_actions:
                if dangerous in task_description.lower() or dangerous in action:
                    return False
            return True
        
        elif condition == "single_file":
            affected_files = task_data.get('affected_files', [])
            return len(affected_files) <= 1
        
        elif condition == "workspace_isolated":
            return task_data.get('workspace_id') is not None
        
        return True
    
    def _check_global_level(self, task_description: str, task_data: Dict[str, Any]) -> bool:
        """Check against global auto-accept level."""
        if self.global_level == AutoAcceptLevel.NONE:
            return False
        
        action = task_data.get('action', '').lower()
        affected_files = task_data.get('affected_files', [])
        
        # Check for dangerous operations
        for dangerous in self.dangerous_actions:
            if dangerous in task_description.lower() or dangerous in action:
                return False
        
        if self.global_level == AutoAcceptLevel.SAFE:
            # Only accept read-only and documentation operations
            return action in self.safe_actions
        
        elif self.global_level == AutoAcceptLevel.TRUSTED:
            # Accept safe operations and file creation/modification for trusted types
            if action in self.safe_actions:
                return True
            
            # Check file types for modification operations
            for file_path in affected_files:
                file_ext = Path(file_path).suffix.lower()
                if file_ext not in self.trusted_file_types:
                    return False
            
            return len(affected_files) <= 5  # Limit batch operations
        
        elif self.global_level == AutoAcceptLevel.AGGRESSIVE:
            # Accept most operations except explicitly dangerous ones
            return True
        
        return False
    
    def get_auto_accept_reason(self, task_description: str, task_data: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Get the reason why a task would be auto-accepted."""
        if not self.should_auto_accept(task_description, task_data):
            return None
        
        task_data = task_data or {}
        
        # Check each rule in order to find the matching one
        for rule in self.rules:
            if self._rule_matches(rule, task_description, task_data):
                if self._check_conditions(rule, task_description, task_data):
                    return f"Auto-accepted by rule: {rule.pattern} (level: {rule.level.value})"
        
        # If no specific rule, it's the global level
        return f"Auto-accepted by global level: {self.global_level.value}"
    
    def set_global_level(self, level: AutoAcceptLevel) -> None:
        """Set the global auto-accept level."""
        self.global_level = level
        self._save_config()
    
    def add_rule(self, rule: AutoAcceptRule) -> None:
        """Add a new auto-accept rule."""
        self.rules.append(rule)
        self._save_config()
    
    def remove_rule(self, pattern: str) -> bool:
        """Remove a rule by pattern."""
        for i, rule in enumerate(self.rules):
            if rule.pattern == pattern:
                del self.rules[i]
                self._save_config()
                return True
        return False
    
    def _save_config(self) -> None:
        """Save current configuration to file."""
        try:
            config = {
                "global_level": self.global_level.value,
                "trusted_file_types": list(self.trusted_file_types),
                "safe_actions": list(self.safe_actions),
                "dangerous_actions": list(self.dangerous_actions),
                "rules": []
            }
            
            # Save custom rules only (skip built-in defaults)
            for rule in self.rules[4:]:  # Skip first 4 default rules
                config["rules"].append({
                    "pattern": rule.pattern,
                    "level": rule.level.value,
                    "conditions": rule.conditions,
                    "max_files": rule.max_files,
                    "exclude_patterns": rule.exclude_patterns
                })
            
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
                
        except Exception as e:
            print(f"Warning: Failed to save auto-accept config: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get auto-accept statistics."""
        return {
            "global_level": self.global_level.value,
            "total_rules": len(self.rules),
            "trusted_file_types": len(self.trusted_file_types),
            "safe_actions": len(self.safe_actions),
            "dangerous_actions": len(self.dangerous_actions)
        }


# Global auto-accept manager instance
_auto_accept_manager: Optional[AutoAcceptManager] = None

def get_auto_accept_manager() -> AutoAcceptManager:
    """Get or create the global auto-accept manager."""
    global _auto_accept_manager
    if _auto_accept_manager is None:
        _auto_accept_manager = AutoAcceptManager()
    return _auto_accept_manager