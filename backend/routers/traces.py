"""
Traces Router — Admin endpoints for viewing and managing unified traces + logs.
Now backed by ClickHouse instead of JSONL files.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from .. import models, auth
from ..services import clickhouse_client

router = APIRouter(prefix="/admin/traces", tags=["traces"])


def require_admin(current_user: models.User = Depends(auth.get_current_user)):
    """Verify user is an admin."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("")
async def list_traces(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    event_type: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    status: Optional[str] = Query(None, pattern="^(success|error)$"),
    user_id: Optional[int] = None,
    start_date: Optional[str] = Query(None, pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    end_date: Optional[str] = Query(None, pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    search: Optional[str] = None,
    _: models.User = Depends(require_admin),
):
    """
    List events with optional filtering.
    For full traces only, filter by event_type=response.
    """
    events, total = clickhouse_client.query_events(
        limit=limit,
        offset=offset,
        event_type=event_type,
        level=level,
        status=status,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )

    return {
        "events": events,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(events) < total,
    }


@router.get("/stats")
async def get_stats(
    hours: int = Query(24, ge=1, le=720),
    _: models.User = Depends(require_admin),
):
    """Get event statistics for the last N hours."""
    return clickhouse_client.get_event_stats(hours=hours)


@router.get("/{trace_id}")
async def get_trace_events(
    trace_id: str,
    _: models.User = Depends(require_admin),
):
    """Get all events belonging to a specific trace."""
    events = clickhouse_client.get_trace_events(trace_id)
    if not events:
        raise HTTPException(status_code=404, detail="Trace not found")
    return {"trace_id": trace_id, "events": events}


@router.get("/health/check")
async def health_check(_: models.User = Depends(require_admin)):
    """Check ClickHouse connectivity."""
    healthy = clickhouse_client.health_check()
    return {"clickhouse": "connected" if healthy else "disconnected"}
