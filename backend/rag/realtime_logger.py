"""
Realtime Logging Module - WebSocket broadcast for live log streaming.
Logs all RAG operations: requests, embeddings, retrieval, generation.
"""

import json
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Set, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum

# WebSocket connections for live streaming
_active_connections: Set["WebSocketConnection"] = set()


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogType(str, Enum):
    REQUEST = "REQUEST"
    EMBEDDING = "EMBEDDING"
    RETRIEVAL = "RETRIEVAL"
    GENERATION = "GENERATION"
    RESPONSE = "RESPONSE"
    UPLOAD = "UPLOAD"
    REINDEX = "REINDEX"
    SYSTEM = "SYSTEM"


@dataclass
class LogEntry:
    """A single log entry."""

    timestamp: str
    level: str
    log_type: str
    message: str
    details: Dict[str, Any] = None
    user_id: Optional[int] = None
    user_email: Optional[str] = None
    trace_id: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Remove None values for cleaner output
        return {k: v for k, v in d.items() if v is not None}


# Log file configuration
LOGS_DIR = Path(__file__).parent.parent / "logs"
REALTIME_LOG_FILE = LOGS_DIR / "realtime.jsonl"
MAX_FILE_SIZE_MB = 20


class WebSocketConnection:
    """Wrapper for WebSocket connection with metadata."""

    def __init__(self, websocket, user_id: int = None, user_email: str = None):
        self.websocket = websocket
        self.user_id = user_id
        self.user_email = user_email
        self.connected_at = datetime.utcnow().isoformat()

    async def send(self, data: Dict[str, Any]):
        try:
            await self.websocket.send_json(data)
        except Exception:
            pass  # Connection closed


def _ensure_logs_dir():
    """Ensure logs directory exists."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _rotate_if_needed():
    """Rotate log file if it exceeds max size."""
    if not REALTIME_LOG_FILE.exists():
        return

    file_size_mb = REALTIME_LOG_FILE.stat().st_size / (1024 * 1024)
    if file_size_mb >= MAX_FILE_SIZE_MB:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"realtime_{timestamp}.jsonl"
        archive_path = LOGS_DIR / archive_name
        REALTIME_LOG_FILE.rename(archive_path)


def _write_log_to_file(entry: LogEntry):
    """Write log entry to JSONL file."""
    _ensure_logs_dir()
    _rotate_if_needed()

    with open(REALTIME_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")


async def _broadcast_log(entry: LogEntry):
    """Broadcast log entry to all connected WebSocket clients."""
    if not _active_connections:
        return

    data = entry.to_dict()

    # Send to all connections
    disconnected = set()
    for conn in _active_connections:
        try:
            await conn.send(data)
        except Exception:
            disconnected.add(conn)

    # Remove disconnected clients
    for conn in disconnected:
        _active_connections.discard(conn)


def log_sync(
    log_type: LogType,
    message: str,
    level: LogLevel = LogLevel.INFO,
    details: Dict[str, Any] = None,
    user_id: int = None,
    user_email: str = None,
    trace_id: str = None,
    duration_ms: float = None,
):
    """
    Synchronous logging - writes to file and queues broadcast.
    Use this from non-async code.
    """
    entry = LogEntry(
        timestamp=datetime.utcnow().isoformat() + "Z",
        level=level.value,
        log_type=log_type.value,
        message=message,
        details=details,
        user_id=user_id,
        user_email=user_email,
        trace_id=trace_id,
        duration_ms=duration_ms,
    )

    # Write to file synchronously
    _write_log_to_file(entry)

    # Queue async broadcast (fire and forget)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_broadcast_log(entry))
        else:
            loop.run_until_complete(_broadcast_log(entry))
    except RuntimeError:
        # No event loop available, skip broadcast
        pass


async def log_async(
    log_type: LogType,
    message: str,
    level: LogLevel = LogLevel.INFO,
    details: Dict[str, Any] = None,
    user_id: int = None,
    user_email: str = None,
    trace_id: str = None,
    duration_ms: float = None,
):
    """
    Async logging - writes to file and broadcasts immediately.
    Use this from async code.
    """
    entry = LogEntry(
        timestamp=datetime.utcnow().isoformat() + "Z",
        level=level.value,
        log_type=log_type.value,
        message=message,
        details=details,
        user_id=user_id,
        user_email=user_email,
        trace_id=trace_id,
        duration_ms=duration_ms,
    )

    # Write to file
    _write_log_to_file(entry)

    # Broadcast to WebSocket clients
    await _broadcast_log(entry)


def add_connection(websocket, user_id: int = None, user_email: str = None):
    """Add a WebSocket connection to receive logs."""
    conn = WebSocketConnection(websocket, user_id, user_email)
    _active_connections.add(conn)
    return conn


def remove_connection(conn: WebSocketConnection):
    """Remove a WebSocket connection."""
    _active_connections.discard(conn)


def get_connection_count() -> int:
    """Get number of active WebSocket connections."""
    return len(_active_connections)


def get_recent_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Get recent log entries from file."""
    _ensure_logs_dir()

    if not REALTIME_LOG_FILE.exists():
        return []

    logs = []
    with open(REALTIME_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    logs.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    # Return most recent first
    logs.reverse()
    return logs[:limit]


# Convenience functions for common log types


def log_request(
    query: str, user_id: int = None, user_email: str = None, trace_id: str = None
):
    """Log an incoming query request."""
    log_sync(
        LogType.REQUEST,
        f"Query received: {query[:100]}..."
        if len(query) > 100
        else f"Query received: {query}",
        details={"query": query, "query_length": len(query)},
        user_id=user_id,
        user_email=user_email,
        trace_id=trace_id,
    )


def log_embedding(text_count: int, duration_ms: float, trace_id: str = None):
    """Log embedding generation."""
    log_sync(
        LogType.EMBEDDING,
        f"Generated embeddings for {text_count} chunks",
        details={"chunk_count": text_count},
        duration_ms=duration_ms,
        trace_id=trace_id,
    )


def log_retrieval(
    chunk_count: int, top_score: float, duration_ms: float, trace_id: str = None
):
    """Log retrieval results."""
    log_sync(
        LogType.RETRIEVAL,
        f"Retrieved {chunk_count} chunks (top score: {top_score:.3f})",
        details={"chunk_count": chunk_count, "top_score": top_score},
        duration_ms=duration_ms,
        trace_id=trace_id,
    )


def log_generation(
    prompt_tokens: int, completion_tokens: int, duration_ms: float, trace_id: str = None
):
    """Log LLM generation."""
    log_sync(
        LogType.GENERATION,
        f"Generated response ({completion_tokens} tokens in {duration_ms:.0f}ms)",
        details={
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
        },
        duration_ms=duration_ms,
        trace_id=trace_id,
    )


def log_response(
    response_length: int,
    total_duration_ms: float,
    user_id: int = None,
    trace_id: str = None,
):
    """Log completed response."""
    log_sync(
        LogType.RESPONSE,
        f"Response sent ({response_length} chars, {total_duration_ms:.0f}ms total)",
        details={"response_length": response_length},
        duration_ms=total_duration_ms,
        user_id=user_id,
        trace_id=trace_id,
    )


def log_upload(filename: str, page_count: int, chunk_count: int, user_id: int = None):
    """Log document upload."""
    log_sync(
        LogType.UPLOAD,
        f"Uploaded: {filename} ({page_count} pages, {chunk_count} chunks)",
        details={
            "filename": filename,
            "page_count": page_count,
            "chunk_count": chunk_count,
        },
        user_id=user_id,
    )


def log_error(
    message: str, error: str, log_type: LogType = LogType.SYSTEM, trace_id: str = None
):
    """Log an error."""
    log_sync(
        log_type,
        message,
        level=LogLevel.ERROR,
        details={"error": error},
        trace_id=trace_id,
    )
