"""
Conversation Management module for multi-turn chat.
Uses Redis for session storage with automatic expiration.
"""

import json
import os
from typing import List, Dict
from uuid import uuid4

# Redis client (lazy initialization)
_redis_client = None

# Configuration from environment
REDIS_HOST = os.getenv("REDIS_HOST", "SRPTH1IDMQFS02.vecvnet.com")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
SESSION_TTL = int(os.getenv("SESSION_TIMEOUT", "3600"))  # Default 1 hour


def _get_redis():
    """Get or initialize Redis client."""
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, decode_responses=True
        )
    return _redis_client


class ConversationManager:
    """
    Manages conversation history for a user session.
    Stores messages in Redis with automatic TTL.
    """

    def __init__(self, user_id: int, group_ids: List[int]):
        """
        Create a new conversation session.

        Args:
            user_id: User identifier
            group_ids: List of group IDs the user has access to
        """
        self.user_id = user_id
        self.group_ids = group_ids
        self.session_key = f"chat:{user_id}:{uuid4()}"

    @classmethod
    def from_session(
        cls, session_key: str, user_id: int, group_ids: List[int]
    ) -> "ConversationManager":
        """
        Resume an existing conversation session.

        Args:
            session_key: Existing session key
            user_id: User identifier
            group_ids: List of group IDs

        Returns:
            ConversationManager instance with existing session
        """
        instance = cls.__new__(cls)
        instance.user_id = user_id
        instance.group_ids = group_ids
        instance.session_key = session_key
        return instance

    def add_message(self, role: str, content: str) -> None:
        """
        Add a message to the conversation history.

        Args:
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        redis = _get_redis()
        message = {"role": role, "content": content}
        redis.rpush(self.session_key, json.dumps(message))
        redis.expire(self.session_key, SESSION_TTL)

    def get_history(self, last_n: int = 5) -> List[Dict]:
        """
        Retrieve the last N messages from conversation history.

        Args:
            last_n: Number of messages to retrieve

        Returns:
            List of message dicts with 'role' and 'content'
        """
        redis = _get_redis()
        messages = redis.lrange(self.session_key, -last_n, -1)
        return [json.loads(m) for m in messages]

    def get_full_history(self) -> List[Dict]:
        """
        Retrieve all messages from conversation history.

        Returns:
            List of all message dicts
        """
        redis = _get_redis()
        messages = redis.lrange(self.session_key, 0, -1)
        return [json.loads(m) for m in messages]

    def clear(self) -> None:
        """Clear the conversation history."""
        redis = _get_redis()
        redis.delete(self.session_key)

    def session_exists(self) -> bool:
        """Check if the session still exists in Redis."""
        redis = _get_redis()
        return redis.exists(self.session_key) > 0


def format_history(history: List[Dict]) -> str:
    """
    Format conversation history as a string for prompt context.

    Args:
        history: List of message dicts

    Returns:
        Formatted history string
    """
    if not history:
        return ""

    lines = []
    for msg in history:
        role = msg.get("role", "user").upper()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")

    return "\n".join(lines)
