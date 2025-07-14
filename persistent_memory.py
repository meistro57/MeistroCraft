#!/usr/bin/env python3
"""
Persistent Memory System for MeistroCraft
Maintains context and knowledge between sessions with intelligent storage and retrieval.
"""

import json
import os
import sys
import time
import gzip
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, asdict
from pathlib import Path
import sqlite3
import pickle
from enum import Enum

class MemoryType(Enum):
    CONVERSATION = "conversation"
    CODE_CONTEXT = "code_context"
    PROJECT_INFO = "project_info"
    USER_PREFERENCES = "user_preferences"
    LEARNED_PATTERNS = "learned_patterns"
    ERROR_SOLUTIONS = "error_solutions"
    DEPENDENCIES = "dependencies"
    PERFORMANCE_DATA = "performance_data"
    ANALYSIS_RESULT = "analysis_result"
    OPTIMIZATION_CANDIDATE = "optimization_candidate"
    OPTIMIZATION_RESULT = "optimization_result"

class MemoryPriority(Enum):
    CRITICAL = "critical"      # Never auto-delete
    HIGH = "high"             # Delete only when absolutely necessary
    MEDIUM = "medium"         # Can be archived after 30 days
    LOW = "low"              # Can be deleted after 7 days

@dataclass
class MemoryEntry:
    """Represents a single memory entry."""
    id: str
    type: MemoryType
    priority: MemoryPriority
    content: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: str
    last_accessed: str
    access_count: int
    size_bytes: int
    tags: List[str]
    session_ids: List[str]
    
    @classmethod
    def create(cls, content: Dict[str, Any], memory_type: MemoryType, 
               priority: MemoryPriority = MemoryPriority.MEDIUM, 
               tags: Optional[List[str]] = None, session_id: Optional[str] = None) -> 'MemoryEntry':
        """Create a new memory entry."""
        now = datetime.now().isoformat()
        content_str = json.dumps(content, sort_keys=True)
        entry_id = hashlib.md5(content_str.encode()).hexdigest()
        
        return cls(
            id=entry_id,
            type=memory_type,
            priority=priority,
            content=content,
            metadata={
                "content_hash": hashlib.sha256(content_str.encode()).hexdigest(),
                "source": "meistrocraft",
                "version": "3.1.0"
            },
            created_at=now,
            last_accessed=now,
            access_count=1,
            size_bytes=len(content_str.encode('utf-8')),
            tags=tags or [],
            session_ids=[session_id] if session_id else []
        )
    
    def update_access(self) -> None:
        """Update access information."""
        self.last_accessed = datetime.now().isoformat()
        self.access_count += 1
    
    def add_session(self, session_id: str) -> None:
        """Add session ID if not already present."""
        if session_id not in self.session_ids:
            self.session_ids.append(session_id)

@dataclass
class MemoryStats:
    """Memory usage statistics."""
    total_entries: int
    total_size_bytes: int
    total_size_mb: float
    by_type: Dict[str, int]
    by_priority: Dict[str, int]
    oldest_entry: Optional[str]
    newest_entry: Optional[str]
    most_accessed: Optional[str]
    warning_threshold_mb: float = 512.0
    
    @property
    def is_near_limit(self) -> bool:
        """Check if memory usage is approaching the warning threshold."""
        return self.total_size_mb >= (self.warning_threshold_mb * 0.8)  # 80% of limit
    
    @property
    def is_over_limit(self) -> bool:
        """Check if memory usage exceeds the warning threshold."""
        return self.total_size_mb >= self.warning_threshold_mb

class PersistentMemory:
    """Main persistent memory management system."""
    
    def __init__(self, memory_dir: str = "persistent_memory", max_size_mb: float = 512.0):
        self.memory_dir = Path(memory_dir)
        self.max_size_mb = max_size_mb
        self.db_path = self.memory_dir / "memory.db"
        self.data_dir = self.memory_dir / "data"
        
        # Ensure directories exist
        self.memory_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize database
        self._init_database()
        
        # Memory cache for frequently accessed items
        self._cache: Dict[str, MemoryEntry] = {}
        self._cache_max_size = 100
    
    def _init_database(self) -> None:
        """Initialize SQLite database for memory metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER NOT NULL DEFAULT 1,
                    size_bytes INTEGER NOT NULL,
                    tags TEXT,  -- JSON array
                    session_ids TEXT,  -- JSON array
                    metadata TEXT,  -- JSON object
                    UNIQUE(id)
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_type ON memory_entries(type)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_priority ON memory_entries(priority)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_accessed ON memory_entries(last_accessed)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_size ON memory_entries(size_bytes)
            """)
    
    def store_memory(self, content: Dict[str, Any], memory_type: MemoryType, 
                    priority: MemoryPriority = MemoryPriority.MEDIUM,
                    tags: Optional[List[str]] = None, session_id: Optional[str] = None) -> str:
        """Store a new memory entry."""
        entry = MemoryEntry.create(content, memory_type, priority, tags, session_id)
        
        # Check if we need to make space
        current_stats = self.get_stats()
        if current_stats.is_over_limit:
            self._cleanup_memory()
        
        # Store content to file (compressed)
        content_file = self.data_dir / f"{entry.id}.gz"
        with gzip.open(content_file, 'wt', encoding='utf-8') as f:
            json.dump(entry.content, f)
        
        # Store metadata in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memory_entries 
                (id, type, priority, created_at, last_accessed, access_count, 
                 size_bytes, tags, session_ids, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.id,
                entry.type.value,
                entry.priority.value,
                entry.created_at,
                entry.last_accessed,
                entry.access_count,
                entry.size_bytes,
                json.dumps(entry.tags),
                json.dumps(entry.session_ids),
                json.dumps(entry.metadata)
            ))
        
        # Add to cache
        self._add_to_cache(entry)
        
        # Check for warnings after storage
        new_stats = self.get_stats()
        self._check_memory_warnings(new_stats)
        
        return entry.id
    
    def retrieve_memory(self, entry_id: str) -> Optional[MemoryEntry]:
        """Retrieve a memory entry by ID."""
        # Check cache first
        if entry_id in self._cache:
            entry = self._cache[entry_id]
            entry.update_access()
            self._update_access_in_db(entry_id)
            return entry
        
        # Load from database
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM memory_entries WHERE id = ?
            """, (entry_id,))
            row = cursor.fetchone()
        
        if not row:
            return None
        
        # Load content from file
        content_file = self.data_dir / f"{entry_id}.gz"
        if not content_file.exists():
            return None
        
        try:
            with gzip.open(content_file, 'rt', encoding='utf-8') as f:
                content = json.load(f)
        except Exception:
            return None
        
        # Create entry object
        entry = MemoryEntry(
            id=row[0],
            type=MemoryType(row[1]),
            priority=MemoryPriority(row[2]),
            content=content,
            metadata=json.loads(row[9]),
            created_at=row[3],
            last_accessed=row[4],
            access_count=row[5],
            size_bytes=row[6],
            tags=json.loads(row[7]),
            session_ids=json.loads(row[8])
        )
        
        # Update access
        entry.update_access()
        self._update_access_in_db(entry_id)
        
        # Add to cache
        self._add_to_cache(entry)
        
        return entry
    
    def search_memories(self, query: str = None, memory_type: Optional[MemoryType] = None,
                       tags: Optional[List[str]] = None, session_id: Optional[str] = None,
                       limit: int = 50) -> List[MemoryEntry]:
        """Search for memory entries based on various criteria."""
        conditions = []
        params = []
        
        if memory_type:
            conditions.append("type = ?")
            params.append(memory_type.value)
        
        if tags:
            # Search for any of the tags
            tag_conditions = []
            for tag in tags:
                tag_conditions.append("tags LIKE ?")
                params.append(f"%{tag}%")
            if tag_conditions:
                conditions.append(f"({' OR '.join(tag_conditions)})")
        
        if session_id:
            conditions.append("session_ids LIKE ?")
            params.append(f"%{session_id}%")
        
        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f"""
                SELECT id FROM memory_entries 
                {where_clause}
                ORDER BY last_accessed DESC, access_count DESC
                LIMIT ?
            """, params + [limit])
            
            memory_ids = [row[0] for row in cursor.fetchall()]
        
        # Retrieve full entries
        memories = []
        for memory_id in memory_ids:
            entry = self.retrieve_memory(memory_id)
            if entry:
                # If query provided, do content search
                if query and query.lower() not in json.dumps(entry.content).lower():
                    continue
                memories.append(entry)
        
        return memories
    
    def get_session_context(self, session_id: str, max_entries: int = 20) -> str:
        """Get relevant context for a session."""
        # Get recent memories for this session
        memories = self.search_memories(session_id=session_id, limit=max_entries)
        
        if not memories:
            return ""
        
        context_parts = []
        context_parts.append(f"📋 Session Memory ({len(memories)} entries):")
        
        for memory in memories[:max_entries]:
            if memory.type == MemoryType.CONVERSATION:
                summary = memory.content.get('summary', str(memory.content)[:100])
                context_parts.append(f"• {memory.type.value}: {summary}")
            elif memory.type == MemoryType.CODE_CONTEXT:
                files = memory.content.get('files', [])
                context_parts.append(f"• Code context: {', '.join(files[:3])}")
            elif memory.type == MemoryType.PROJECT_INFO:
                project = memory.content.get('name', 'Unknown project')
                context_parts.append(f"• Project: {project}")
            elif memory.type == MemoryType.ERROR_SOLUTIONS:
                error = memory.content.get('error_type', 'Unknown error')
                context_parts.append(f"• Solution for: {error}")
        
        return "\n".join(context_parts)
    
    def store_conversation_memory(self, conversation_data: Dict[str, Any], session_id: str) -> str:
        """Store conversation-specific memory."""
        memory_content = {
            "messages": conversation_data.get("messages", []),
            "summary": conversation_data.get("summary", ""),
            "key_topics": conversation_data.get("topics", []),
            "decisions_made": conversation_data.get("decisions", []),
            "session_id": session_id
        }
        
        return self.store_memory(
            memory_content,
            MemoryType.CONVERSATION,
            MemoryPriority.HIGH,
            tags=["conversation", "session"],
            session_id=session_id
        )
    
    def store_code_context(self, code_data: Dict[str, Any], session_id: str) -> str:
        """Store code-related memory."""
        memory_content = {
            "files_created": code_data.get("files_created", []),
            "files_modified": code_data.get("files_modified", []),
            "technologies_used": code_data.get("technologies", []),
            "patterns_applied": code_data.get("patterns", []),
            "project_structure": code_data.get("structure", {}),
            "session_id": session_id
        }
        
        return self.store_memory(
            memory_content,
            MemoryType.CODE_CONTEXT,
            MemoryPriority.HIGH,
            tags=["code", "development"],
            session_id=session_id
        )
    
    def store_error_solution(self, error_data: Dict[str, Any], session_id: str) -> str:
        """Store error solutions for future reference."""
        memory_content = {
            "error_type": error_data.get("error_type", ""),
            "error_message": error_data.get("error_message", ""),
            "solution": error_data.get("solution", ""),
            "context": error_data.get("context", ""),
            "success": error_data.get("success", False),
            "session_id": session_id
        }
        
        return self.store_memory(
            memory_content,
            MemoryType.ERROR_SOLUTIONS,
            MemoryPriority.CRITICAL,  # Error solutions are very valuable
            tags=["error", "solution", "troubleshooting"],
            session_id=session_id
        )
    
    def get_stats(self) -> MemoryStats:
        """Get memory usage statistics."""
        with sqlite3.connect(self.db_path) as conn:
            # Get total stats
            cursor = conn.execute("""
                SELECT COUNT(*), SUM(size_bytes) FROM memory_entries
            """)
            total_count, total_bytes = cursor.fetchone()
            total_bytes = total_bytes or 0
            
            # Get stats by type
            cursor = conn.execute("""
                SELECT type, COUNT(*) FROM memory_entries GROUP BY type
            """)
            by_type = dict(cursor.fetchall())
            
            # Get stats by priority
            cursor = conn.execute("""
                SELECT priority, COUNT(*) FROM memory_entries GROUP BY priority
            """)
            by_priority = dict(cursor.fetchall())
            
            # Get oldest and newest entries
            cursor = conn.execute("""
                SELECT id FROM memory_entries ORDER BY created_at ASC LIMIT 1
            """)
            oldest = cursor.fetchone()
            oldest_entry = oldest[0] if oldest else None
            
            cursor = conn.execute("""
                SELECT id FROM memory_entries ORDER BY created_at DESC LIMIT 1
            """)
            newest = cursor.fetchone()
            newest_entry = newest[0] if newest else None
            
            # Get most accessed
            cursor = conn.execute("""
                SELECT id FROM memory_entries ORDER BY access_count DESC LIMIT 1
            """)
            most_accessed = cursor.fetchone()
            most_accessed_entry = most_accessed[0] if most_accessed else None
        
        return MemoryStats(
            total_entries=total_count or 0,
            total_size_bytes=total_bytes,
            total_size_mb=total_bytes / (1024 * 1024),
            by_type=by_type,
            by_priority=by_priority,
            oldest_entry=oldest_entry,
            newest_entry=newest_entry,
            most_accessed=most_accessed_entry,
            warning_threshold_mb=self.max_size_mb
        )
    
    def _check_memory_warnings(self, stats: MemoryStats) -> None:
        """Check and display memory warnings."""
        if stats.is_over_limit:
            print(f"🚨 MEMORY WARNING: Usage exceeds {self.max_size_mb}MB limit!")
            print(f"   Current usage: {stats.total_size_mb:.2f}MB ({stats.total_entries} entries)")
            print(f"   Recommend running memory cleanup or increasing limit.")
        elif stats.is_near_limit:
            percentage = (stats.total_size_mb / self.max_size_mb) * 100
            print(f"⚠️  Memory usage at {percentage:.1f}% of {self.max_size_mb}MB limit")
            print(f"   Current usage: {stats.total_size_mb:.2f}MB ({stats.total_entries} entries)")
    
    def _cleanup_memory(self, target_size_mb: Optional[float] = None) -> int:
        """Clean up memory to reduce size."""
        if target_size_mb is None:
            target_size_mb = self.max_size_mb * 0.7  # Target 70% of limit
        
        target_bytes = target_size_mb * 1024 * 1024
        current_stats = self.get_stats()
        
        if current_stats.total_size_bytes <= target_bytes:
            return 0  # No cleanup needed
        
        bytes_to_free = current_stats.total_size_bytes - target_bytes
        deleted_count = 0
        
        # Cleanup strategy: Delete in order of priority
        # 1. Low priority, old entries
        # 2. Medium priority, old entries  
        # 3. High priority, very old entries (>90 days)
        # Never delete CRITICAL priority
        
        cleanup_queries = [
            # Low priority, older than 7 days
            ("priority = 'low' AND datetime(last_accessed) < datetime('now', '-7 days')", "Low priority, old"),
            # Medium priority, older than 30 days
            ("priority = 'medium' AND datetime(last_accessed) < datetime('now', '-30 days')", "Medium priority, old"), 
            # High priority, older than 90 days
            ("priority = 'high' AND datetime(last_accessed) < datetime('now', '-90 days')", "High priority, very old")
        ]
        
        with sqlite3.connect(self.db_path) as conn:
            for condition, description in cleanup_queries:
                if bytes_to_free <= 0:
                    break
                
                # Get entries to delete
                cursor = conn.execute(f"""
                    SELECT id, size_bytes FROM memory_entries 
                    WHERE {condition}
                    ORDER BY last_accessed ASC
                """)
                
                entries_to_delete = cursor.fetchall()
                
                for entry_id, size_bytes in entries_to_delete:
                    if bytes_to_free <= 0:
                        break
                    
                    # Delete content file
                    content_file = self.data_dir / f"{entry_id}.gz"
                    if content_file.exists():
                        content_file.unlink()
                    
                    # Delete from database
                    conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
                    
                    # Remove from cache
                    if entry_id in self._cache:
                        del self._cache[entry_id]
                    
                    bytes_to_free -= size_bytes
                    deleted_count += 1
        
        if deleted_count > 0:
            print(f"🧹 Cleaned up {deleted_count} memory entries to free space")
        
        return deleted_count
    
    def _add_to_cache(self, entry: MemoryEntry) -> None:
        """Add entry to cache with LRU eviction."""
        if len(self._cache) >= self._cache_max_size:
            # Remove least recently accessed item
            oldest_id = min(self._cache.keys(), 
                           key=lambda k: self._cache[k].last_accessed)
            del self._cache[oldest_id]
        
        self._cache[entry.id] = entry
    
    def _update_access_in_db(self, entry_id: str) -> None:
        """Update access information in database."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE memory_entries 
                SET last_accessed = ?, access_count = access_count + 1
                WHERE id = ?
            """, (now, entry_id))
    
    def export_memory_report(self, output_file: str) -> None:
        """Export memory usage report."""
        stats = self.get_stats()
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "stats": asdict(stats),
            "entries": []
        }
        
        # Get all entries for detailed report
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT id, type, priority, created_at, last_accessed, 
                       access_count, size_bytes, tags
                FROM memory_entries
                ORDER BY size_bytes DESC
            """)
            
            for row in cursor.fetchall():
                report["entries"].append({
                    "id": row[0],
                    "type": row[1],
                    "priority": row[2],
                    "created_at": row[3],
                    "last_accessed": row[4],
                    "access_count": row[5],
                    "size_bytes": row[6],
                    "size_mb": row[6] / (1024 * 1024),
                    "tags": json.loads(row[7])
                })
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Memory report exported to: {output_file}")
    
    def clear_session_memories(self, session_id: str) -> int:
        """Clear all memories associated with a specific session."""
        with sqlite3.connect(self.db_path) as conn:
            # Get entries to delete
            cursor = conn.execute("""
                SELECT id FROM memory_entries WHERE session_ids LIKE ?
            """, (f"%{session_id}%",))
            
            entry_ids = [row[0] for row in cursor.fetchall()]
            
            # Delete content files and database entries
            for entry_id in entry_ids:
                content_file = self.data_dir / f"{entry_id}.gz"
                if content_file.exists():
                    content_file.unlink()
                
                conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
                
                if entry_id in self._cache:
                    del self._cache[entry_id]
        
        return len(entry_ids)
    
    def get_memory_summary(self) -> str:
        """Get a brief memory summary for display."""
        stats = self.get_stats()
        
        summary = f"💾 Persistent Memory: {stats.total_entries} entries, {stats.total_size_mb:.1f}MB"
        
        if stats.is_over_limit:
            summary += " 🚨 OVER LIMIT"
        elif stats.is_near_limit:
            percentage = (stats.total_size_mb / stats.warning_threshold_mb) * 100
            summary += f" ⚠️ {percentage:.0f}% of limit"
        
        return summary