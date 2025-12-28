"""
Thread Manager Service

Manages Slack conversation threading and context preservation.
"""

import time
from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass
import logging

# Use simple logging instead of custom logger
logger = logging.getLogger(__name__)


@dataclass
class ThreadContext:
    """Context for a Slack thread."""
    thread_ts: str
    channel_id: str
    starter_user: str
    created_at: float
    messages: List[Dict[str, str]]  # [{role: user/assistant, content: text, ts: timestamp}]
    
    def add_message(self, role: str, content: str, ts: str = None):
        """Add message to thread context."""
        self.messages.append({
            "role": role,
            "content": content,
            "ts": ts or str(time.time())
        })
    
    def get_recent_messages(self, max_count: int = 3) -> List[Dict[str, str]]:
        """Get last N messages for context."""
        return self.messages[-max_count:] if max_count > 0 else []
    
    def format_context(self, max_messages: int = 3, format_template: str = None) -> str:
        """
        Format recent messages as context string.
        
        Args:
            max_messages: Maximum messages to include
            format_template: Optional custom format template
            
        Returns:
            Formatted context string
        """
        recent = self.get_recent_messages(max_messages)
        
        if not recent:
            return ""
        
        # Build context string
        context_lines = []
        for msg in recent:
            role_label = "User" if msg["role"] == "user" else "Assistant"
            context_lines.append(f"{role_label}: {msg['content']}")
        
        context = "\n".join(context_lines)
        
        # Apply format template if provided
        if format_template and "{context}" in format_template:
            return format_template.replace("{context}", context)
        
        return f"Previous conversation:\n{context}"


class ThreadManager:
    """
    Manages Slack threading and conversation context.
    
    Features:
    - Track active threads
    - Store conversation history
    - Provide context for LLM
    - Configurable context depth
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize thread manager with configuration.
        
        Args:
            config: Threading configuration from threading.yaml
        """
        self.config = config
        
        # Thread storage: {thread_ts: ThreadContext}
        self._threads: Dict[str, ThreadContext] = {}
        
        # DM context storage: {user_id: List[messages]}
        self._dm_context: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        
        # Configuration shortcuts
        threading_config = config.get("threading", {})
        self.enabled = threading_config.get("enabled", True)
        self.always_use_threads = threading_config.get("behavior", {}).get("always_use_threads", True)
        self.continue_threads = threading_config.get("behavior", {}).get("continue_threads", True)
        
        context_config = threading_config.get("context", {})
        self.context_enabled = context_config.get("enabled", True)
        self.max_context_messages = context_config.get("max_messages", 3)
        self.send_to_llm = context_config.get("send_to_llm", True)
        self.context_format = context_config.get("format", "Previous conversation:\n{context}\n\nCurrent question: {message}")
        
        dm_config = config.get("direct_messages", {})
        self.dm_threads = dm_config.get("use_threads", False)
        self.dm_context_enabled = dm_config.get("context", {}).get("enabled", True)
        self.dm_max_messages = dm_config.get("context", {}).get("max_messages", 5)
        
        logger.info(
            "🧵 Thread manager initialized",
            threading_enabled=self.enabled,
            context_enabled=self.context_enabled,
            max_context=self.max_context_messages
        )
    
    def should_use_thread(self, channel_type: str, existing_thread_ts: str = None) -> bool:
        """
        Determine if threading should be used.
        
        Args:
            channel_type: "channel", "group", "im" (direct message)
            existing_thread_ts: Thread TS if message is in existing thread
            
        Returns:
            True if threading should be used
        """
        if not self.enabled:
            return False
        
        # Check if in DM
        is_dm = channel_type == "im"
        
        if is_dm:
            return self.dm_threads
        
        # If message is in existing thread, continue it
        if existing_thread_ts and self.continue_threads:
            return True
        
        # Always use threads in channels (if configured)
        return self.always_use_threads
    
    def get_or_create_thread(
        self,
        thread_ts: str,
        channel_id: str,
        starter_user: str
    ) -> ThreadContext:
        """
        Get existing thread or create new one.
        
        Args:
            thread_ts: Thread timestamp
            channel_id: Slack channel ID
            starter_user: User who started thread
            
        Returns:
            ThreadContext object
        """
        if thread_ts not in self._threads:
            self._threads[thread_ts] = ThreadContext(
                thread_ts=thread_ts,
                channel_id=channel_id,
                starter_user=starter_user,
                created_at=time.time(),
                messages=[]
            )
            logger.debug(
                "🧵 Created new thread context",
                thread_ts=thread_ts,
                channel=channel_id,
                user=starter_user
            )
        
        return self._threads[thread_ts]
    
    def add_user_message(
        self,
        thread_ts: str,
        channel_id: str,
        user_id: str,
        message: str,
        message_ts: str
    ):
        """
        Add user message to thread context.
        
        Args:
            thread_ts: Thread timestamp
            channel_id: Slack channel ID
            user_id: User ID
            message: Message text
            message_ts: Message timestamp
        """
        thread = self.get_or_create_thread(thread_ts, channel_id, user_id)
        thread.add_message("user", message, message_ts)
        
        logger.debug(
            "📝 Added user message to thread",
            thread_ts=thread_ts,
            message_preview=message[:50]
        )
    
    def add_assistant_message(
        self,
        thread_ts: str,
        channel_id: str,
        user_id: str,
        message: str,
        message_ts: str
    ):
        """
        Add assistant (bot) message to thread context.
        
        Args:
            thread_ts: Thread timestamp
            channel_id: Slack channel ID
            user_id: User ID who triggered response
            message: Assistant message text
            message_ts: Message timestamp
        """
        thread = self.get_or_create_thread(thread_ts, channel_id, user_id)
        thread.add_message("assistant", message, message_ts)
        
        logger.debug(
            "🤖 Added assistant message to thread",
            thread_ts=thread_ts,
            message_preview=message[:50]
        )
    
    def get_context_for_message(
        self,
        message: str,
        thread_ts: str = None,
        channel_id: str = None,
        user_id: str = None,
        channel_type: str = "channel"
    ) -> str:
        """
        Get conversation context for a message.
        
        Args:
            message: Current message
            thread_ts: Thread timestamp (if in thread)
            channel_id: Channel ID
            user_id: User ID
            channel_type: "channel", "group", or "im"
            
        Returns:
            Message with context prepended (if context enabled)
        """
        # Check if context is disabled
        if not self.context_enabled:
            return message
        
        # Handle DM context
        is_dm = channel_type == "im"
        if is_dm and self.dm_context_enabled:
            recent_messages = self._dm_context.get(user_id, [])[-self.dm_max_messages:]
            if recent_messages:
                context_lines = []
                for msg in recent_messages:
                    role_label = "User" if msg["role"] == "user" else "Assistant"
                    context_lines.append(f"{role_label}: {msg['content']}")
                
                context = "\n".join(context_lines)
                return self.context_format.replace("{context}", context).replace("{message}", message)
            return message
        
        # Handle thread context
        if thread_ts and thread_ts in self._threads:
            thread = self._threads[thread_ts]
            context_str = thread.format_context(self.max_context_messages, self.context_format)
            
            if context_str:
                # Replace placeholders
                return context_str.replace("{message}", message)
        
        return message
    
    def add_dm_message(self, user_id: str, role: str, content: str):
        """
        Add message to DM context.
        
        Args:
            user_id: User ID
            role: "user" or "assistant"
            content: Message content
        """
        if not self.dm_context_enabled:
            return
        
        self._dm_context[user_id].append({
            "role": role,
            "content": content,
            "ts": str(time.time())
        })
        
        # Keep only recent messages
        self._dm_context[user_id] = self._dm_context[user_id][-self.dm_max_messages:]
    
    def cleanup_old_threads(self, max_age_hours: int = 24):
        """
        Clean up old thread contexts to prevent memory bloat.
        
        Args:
            max_age_hours: Maximum age in hours
        """
        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        
        threads_to_remove = []
        for thread_ts, thread in self._threads.items():
            if thread.created_at < cutoff:
                threads_to_remove.append(thread_ts)
        
        for thread_ts in threads_to_remove:
            del self._threads[thread_ts]
        
        if threads_to_remove:
            logger.info(
                "🧹 Cleaned up old threads",
                removed_count=len(threads_to_remove),
                remaining=len(self._threads)
            )
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get thread manager statistics.
        
        Returns:
            Dict with active threads and message counts
        """
        total_messages = sum(len(t.messages) for t in self._threads.values())
        dm_contexts = len(self._dm_context)
        
        return {
            "active_threads": len(self._threads),
            "total_messages": total_messages,
            "dm_contexts": dm_contexts,
            "config": {
                "threading_enabled": self.enabled,
                "context_enabled": self.context_enabled,
                "max_context_messages": self.max_context_messages
            }
        }


# Global thread manager instance
_thread_manager: Optional[ThreadManager] = None


def get_thread_manager(config: Dict[str, Any] = None) -> ThreadManager:
    """
    Get or create global thread manager instance.
    
    Args:
        config: Threading configuration (required on first call)
        
    Returns:
        ThreadManager instance
    """
    global _thread_manager
    
    if _thread_manager is None:
        if config is None:
            # Use default config
            config = {
                "threading": {
                    "enabled": True,
                    "behavior": {
                        "always_use_threads": True,
                        "continue_threads": True
                    },
                    "context": {
                        "enabled": True,
                        "max_messages": 3,
                        "send_to_llm": True
                    }
                },
                "direct_messages": {
                    "use_threads": False,
                    "context": {
                        "enabled": True,
                        "max_messages": 5
                    }
                }
            }
        
        _thread_manager = ThreadManager(config)
        logger.info("🧵 Thread manager created")
    
    return _thread_manager
