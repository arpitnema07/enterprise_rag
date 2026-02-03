"""
WebSocket endpoint for realtime log streaming.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..rag.realtime_logger import (
    add_connection,
    remove_connection,
    get_recent_logs,
    get_connection_count,
    log_sync,
    LogType,
    LogLevel,
)

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/logs")
async def websocket_logs(websocket: WebSocket):
    """
    WebSocket endpoint for streaming realtime logs.
    Connect to receive live log entries.
    """
    await websocket.accept()

    # Add connection
    conn = add_connection(websocket)

    # Log connection
    log_sync(
        LogType.SYSTEM,
        f"Admin connected to log stream (Total connections: {get_connection_count()})",
        level=LogLevel.INFO,
    )

    # Send recent logs on connect
    recent = get_recent_logs(50)
    for log_entry in reversed(recent):  # Send oldest first
        await websocket.send_json(log_entry)

    try:
        # Keep connection alive
        while True:
            # Wait for any message (heartbeat/ping)
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        remove_connection(conn)
        log_sync(
            LogType.SYSTEM,
            f"Admin disconnected from log stream (Total connections: {get_connection_count()})",
            level=LogLevel.INFO,
        )
