"""
WebSocket endpoint for realtime log/trace streaming.
Uses the unified observability module.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..rag.observability import (
    add_connection,
    remove_connection,
    get_connection_count,
    emit,
    EventType,
    LogLevel,
)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket endpoint for streaming realtime events.
    Streams all observability events (logs + traces) live.
    """
    await websocket.accept()

    # Add connection
    conn = add_connection(websocket)

    # Log connection event
    emit(
        EventType.SYSTEM,
        f"Admin connected to event stream (Total: {get_connection_count()})",
        level=LogLevel.INFO,
    )

    try:
        # Keep connection alive
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        remove_connection(conn)
        emit(
            EventType.SYSTEM,
            f"Admin disconnected from event stream (Total: {get_connection_count()})",
            level=LogLevel.INFO,
        )
