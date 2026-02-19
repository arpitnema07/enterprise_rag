"""
Unified Observability Module — Replaces tracer.py + realtime_logger.py.

All events (logs + traces) go to:
  1. ClickHouse (persistent, queryable)
  2. WebSocket (live streaming to admin UI)

A "trace" is a group of events sharing the same trace_id.
The 'response' event carries the full trace payload (query, answer, chunks, latency).
"""

import json
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Set
from enum import Enum


# ---------- Enums ----------


class EventType(str, Enum):
    REQUEST = "request"
    EMBEDDING = "embedding"
    RETRIEVAL = "retrieval"
    GENERATION = "generation"
    RESPONSE = "response"
    UPLOAD = "upload"
    REINDEX = "reindex"
    SYSTEM = "system"
    ERROR = "error"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# ---------- WebSocket Broadcasting ----------

_active_connections: Set = set()


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
            pass


def add_connection(
    websocket, user_id: int = None, user_email: str = None
) -> WebSocketConnection:
    """Add a WebSocket connection for live streaming."""
    conn = WebSocketConnection(websocket, user_id, user_email)
    _active_connections.add(conn)
    return conn


def remove_connection(conn: WebSocketConnection):
    """Remove a WebSocket connection."""
    _active_connections.discard(conn)


def get_connection_count() -> int:
    """Get number of active WebSocket connections."""
    return len(_active_connections)


async def _broadcast(data: Dict[str, Any]):
    """Broadcast data to all connected WebSocket clients."""
    dead = set()
    for conn in _active_connections:
        try:
            await conn.send(data)
        except Exception:
            dead.add(conn)
    _active_connections.difference_update(dead)


# ---------- Core Emit Functions ----------


def generate_trace_id() -> str:
    """Generate a new unique trace ID."""
    return str(uuid.uuid4())


def emit(
    event_type: EventType,
    message: str,
    level: LogLevel = LogLevel.INFO,
    trace_id: str = "",
    user_id: int = None,
    user_email: str = None,
    query: str = None,
    response: str = None,
    chunks: list = None,
    latency_ms: float = None,
    token_count: int = None,
    status: str = None,
    error_detail: str = None,
    metadata: dict = None,
    model_provider: str = None,
    model_name: str = None,
):
    """
    Emit an event — writes to ClickHouse and broadcasts via WebSocket.
    This is the SYNCHRONOUS version for use in non-async code.

    Args:
        event_type: Type of event (request, generation, response, etc.)
        message: Human-readable description
        level: Log level
        trace_id: Groups events into a trace
        ... other trace-specific fields
    """
    chunks_json = json.dumps(chunks, ensure_ascii=False) if chunks else None
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    # 1. Write to ClickHouse
    try:
        from ..services.clickhouse_client import insert_event

        insert_event(
            event_type=event_type.value,
            message=message,
            level=level.value,
            trace_id=trace_id,
            user_id=user_id,
            user_email=user_email,
            query=query,
            response=response,
            chunks_json=chunks_json,
            latency_ms=latency_ms,
            token_count=token_count,
            status=status,
            error_detail=error_detail,
            metadata_json=metadata_json,
            model_provider=model_provider,
            model_name=model_name,
        )
    except Exception as e:
        print(f"[observability] ClickHouse write failed: {e}")

    # 2. Broadcast to WebSocket (schedule on event loop if available)
    ws_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type.value,
        "level": level.value,
        "trace_id": trace_id,
        "message": message,
        "user_id": user_id,
        "user_email": user_email,
        "latency_ms": latency_ms,
        "status": status,
        "model_provider": model_provider,
        "model_name": model_name,
    }
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_broadcast(ws_data))
    except RuntimeError:
        # No event loop running — skip WebSocket broadcast (e.g. Celery worker)
        pass


async def emit_async(
    event_type: EventType,
    message: str,
    level: LogLevel = LogLevel.INFO,
    trace_id: str = "",
    user_id: int = None,
    user_email: str = None,
    query: str = None,
    response: str = None,
    chunks: list = None,
    latency_ms: float = None,
    token_count: int = None,
    status: str = None,
    error_detail: str = None,
    metadata: dict = None,
    model_provider: str = None,
    model_name: str = None,
):
    """
    Async version of emit — same behavior but awaits the broadcast.
    Use this from async handlers (FastAPI endpoints).
    """
    chunks_json = json.dumps(chunks, ensure_ascii=False) if chunks else None
    metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata else None

    # 1. Write to ClickHouse (offload to thread to avoid blocking)
    try:
        from ..services.clickhouse_client import insert_event

        await asyncio.to_thread(
            insert_event,
            event_type=event_type.value,
            message=message,
            level=level.value,
            trace_id=trace_id,
            user_id=user_id,
            user_email=user_email,
            query=query,
            response=response,
            chunks_json=chunks_json,
            latency_ms=latency_ms,
            token_count=token_count,
            status=status,
            error_detail=error_detail,
            metadata_json=metadata_json,
            model_provider=model_provider,
            model_name=model_name,
        )
    except Exception as e:
        print(f"[observability] ClickHouse write failed: {e}")

    # 2. Broadcast to WebSocket
    ws_data = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": event_type.value,
        "level": level.value,
        "trace_id": trace_id,
        "message": message,
        "user_id": user_id,
        "user_email": user_email,
        "latency_ms": latency_ms,
        "status": status,
        "model_provider": model_provider,
        "model_name": model_name,
    }
    await _broadcast(ws_data)


# ---------- Convenience Functions ----------


def log_request(query: str, trace_id: str, user_id: int = None, user_email: str = None):
    """Log an incoming query request."""
    emit(
        EventType.REQUEST,
        f"Query received: {query[:80]}...",
        trace_id=trace_id,
        user_id=user_id,
        user_email=user_email,
        query=query,
    )


def log_retrieval(
    chunk_count: int, top_score: float, duration_ms: float, trace_id: str
):
    """Log retrieval results."""
    emit(
        EventType.RETRIEVAL,
        f"Retrieved {chunk_count} chunks (top score: {top_score:.3f}) in {duration_ms:.0f}ms",
        trace_id=trace_id,
        latency_ms=duration_ms,
    )


def log_generation(
    prompt_tokens: int,
    completion_tokens: int,
    duration_ms: float,
    trace_id: str,
    model_provider: str = None,
    model_name: str = None,
):
    """Log LLM generation."""
    emit(
        EventType.GENERATION,
        f"LLM generated {completion_tokens} tokens in {duration_ms:.0f}ms",
        trace_id=trace_id,
        latency_ms=duration_ms,
        token_count=prompt_tokens + completion_tokens,
        model_provider=model_provider,
        model_name=model_name,
    )


def log_response(
    query: str,
    response_text: str,
    chunks: list,
    latency_ms: float,
    token_count: int,
    trace_id: str,
    user_id: int = None,
    user_email: str = None,
    status: str = "success",
    error_detail: str = None,
    model_provider: str = None,
    model_name: str = None,
):
    """Log the completed response — this is the full trace record."""
    emit(
        EventType.RESPONSE,
        f"Response completed in {latency_ms:.0f}ms ({status})",
        trace_id=trace_id,
        user_id=user_id,
        user_email=user_email,
        query=query,
        response=response_text,
        chunks=chunks,
        latency_ms=latency_ms,
        token_count=token_count,
        status=status,
        error_detail=error_detail,
        model_provider=model_provider,
        model_name=model_name,
    )


def log_upload(filename: str, page_count: int, chunk_count: int, user_id: int = None):
    """Log a document upload."""
    emit(
        EventType.UPLOAD,
        f"Uploaded '{filename}' — {page_count} pages, {chunk_count} chunks",
        user_id=user_id,
    )


def log_reindex(message: str, trace_id: str = "", metadata: dict = None):
    """Log reindex progress."""
    emit(EventType.REINDEX, message, trace_id=trace_id, metadata=metadata)


def log_error(message: str, error: str, trace_id: str = ""):
    """Log an error."""
    emit(
        EventType.ERROR,
        message,
        level=LogLevel.ERROR,
        trace_id=trace_id,
        status="error",
        error_detail=error,
    )


def log_system(message: str, level: LogLevel = LogLevel.INFO):
    """Log a system event (startup, shutdown, etc.)."""
    emit(EventType.SYSTEM, message, level=level)


# ---------- Token Estimation ----------


def estimate_tokens(text: str) -> int:
    """Rough token estimation: ~1.3 tokens per word."""
    return int(len(text.split()) * 1.3)
