"""
Traces Router - Admin endpoints for viewing and managing request traces.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from .. import models, auth
from ..rag.tracer import get_traces, get_trace_by_id, clear_traces

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
    status: Optional[str] = Query(None, regex="^(success|error)$"),
    user_id: Optional[int] = None,
    start_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$"),
    end_date: Optional[str] = Query(None, regex="^\\d{4}-\\d{2}-\\d{2}$"),
    search: Optional[str] = None,
    _: models.User = Depends(require_admin),
):
    """
    List traces with optional filtering.

    - **limit**: Max traces to return (1-500)
    - **offset**: Number to skip for pagination
    - **status**: Filter by 'success' or 'error'
    - **user_id**: Filter by user ID
    - **start_date**: Filter traces from this date (YYYY-MM-DD)
    - **end_date**: Filter traces until this date (YYYY-MM-DD)
    - **search**: Search in query text
    """
    traces, total = get_traces(
        limit=limit,
        offset=offset,
        status=status,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )

    return {
        "traces": traces,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(traces) < total,
    }


@router.get("/{trace_id}")
async def get_trace(trace_id: str, _: models.User = Depends(require_admin)):
    """Get a single trace by ID."""
    trace = get_trace_by_id(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@router.delete("")
async def delete_traces(
    confirm: bool = Query(False), _: models.User = Depends(require_admin)
):
    """
    Archive all traces (requires confirm=true).
    Traces are moved to a timestamped archive file.
    """
    if not confirm:
        raise HTTPException(
            status_code=400, detail="Must pass confirm=true to archive traces"
        )

    count = clear_traces()
    return {"message": f"Archived {count} traces", "count": count}
