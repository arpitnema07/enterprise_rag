"""
ClickHouse Client — Unified observability storage for traces and logs.
Replaces JSONL file-based logging with indexed, queryable storage.
"""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import clickhouse_connect

# Environment configurations are loaded dynamically in _get_client

# Lazy-initialized client
_client = None


def _get_client():
    """Get or create the ClickHouse client singleton."""
    global _client
    if _client is None:
        ch_database = os.getenv("CLICKHOUSE_DB", "vecvrag")
        _client = clickhouse_connect.get_client(
            host=os.getenv("CLICKHOUSE_HOST", "localhost"),
            port=int(os.getenv("CLICKHOUSE_PORT", "8123")),
            database=ch_database,
            username=os.getenv("CLICKHOUSE_USER", "default"),
            password=os.getenv("CLICKHOUSE_PASSWORD", ""),
        )
        # Store for reuse in ensure_table_exists
        _client.vecvrag_db = ch_database
    return _client


def ensure_table_exists():
    """Ensure the events table exists in ClickHouse."""
    client = _get_client()
    query = """
    CREATE TABLE IF NOT EXISTS events (
        event_id UUID DEFAULT generateUUIDv4(),
        timestamp DateTime64(3, 'UTC'),
        event_type String,
        level String,
        trace_id String,
        user_id Nullable(Int32),
        user_email Nullable(String),
        message String,
        query Nullable(String),
        response Nullable(String),
        chunks_json Nullable(String),
        latency_ms Nullable(Float64),
        token_count Nullable(Int32),
        status Nullable(String),
        error_detail Nullable(String),
        metadata_json Nullable(String),
        model_provider Nullable(String),
        model_name Nullable(String)
    ) ENGINE = MergeTree()
    ORDER BY (timestamp, event_type)
    """
    # Create DB if it doesn't exist
    client.command(f"CREATE DATABASE IF NOT EXISTS {client.vecvrag_db}")
    client.command(query)


def insert_event(
    event_type: str,
    message: str,
    level: str = "INFO",
    trace_id: str = "",
    user_id: int = None,
    user_email: str = None,
    query: str = None,
    response: str = None,
    chunks_json: str = None,
    latency_ms: float = None,
    token_count: int = None,
    status: str = None,
    error_detail: str = None,
    metadata_json: str = None,
    model_provider: str = None,
    model_name: str = None,
) -> None:
    """
    Insert a single event into ClickHouse.

    Args:
        event_type: One of: request, embedding, retrieval, generation, response,
                    upload, reindex, system, error
        message: Human-readable event message
        level: DEBUG, INFO, WARNING, ERROR
        trace_id: Groups related events into a trace
        ... (remaining fields are optional trace-specific data)
    """
    client = _get_client()

    data = [
        [
            datetime.utcnow(),
            event_type,
            level,
            trace_id or "",
            user_id,
            user_email,
            message,
            query,
            response,
            chunks_json,
            latency_ms,
            token_count,
            status,
            error_detail,
            metadata_json,
            model_provider,
            model_name,
        ]
    ]

    columns = [
        "timestamp",
        "event_type",
        "level",
        "trace_id",
        "user_id",
        "user_email",
        "message",
        "query",
        "response",
        "chunks_json",
        "latency_ms",
        "token_count",
        "status",
        "error_detail",
        "metadata_json",
        "model_provider",
        "model_name",
    ]

    client.insert("events", data, column_names=columns)


def query_events(
    limit: int = 50,
    offset: int = 0,
    event_type: str = None,
    level: str = None,
    trace_id: str = None,
    user_id: int = None,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    search: str = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Query events from ClickHouse with filtering.

    Returns:
        Tuple of (events list, total count)
    """
    client = _get_client()

    where_clauses = []
    params = {}

    if event_type:
        where_clauses.append("event_type = {event_type:String}")
        params["event_type"] = event_type
    if level:
        where_clauses.append("level = {level:String}")
        params["level"] = level
    if trace_id:
        where_clauses.append("trace_id = {trace_id:String}")
        params["trace_id"] = trace_id
    if user_id:
        where_clauses.append("user_id = {user_id:Int32}")
        params["user_id"] = user_id
    if status:
        where_clauses.append("status = {status:String}")
        params["status"] = status
    if start_date:
        where_clauses.append("toDate(timestamp) >= {start_date:String}")
        params["start_date"] = start_date
    if end_date:
        where_clauses.append("toDate(timestamp) <= {end_date:String}")
        params["end_date"] = end_date
    if search:
        where_clauses.append(
            "(message ILIKE {search:String} OR query ILIKE {search:String})"
        )
        params["search"] = f"%{search}%"

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    # Get total count
    count_query = f"SELECT count() FROM events WHERE {where_sql}"
    count_result = client.query(count_query, parameters=params)
    total = count_result.result_rows[0][0] if count_result.result_rows else 0

    # Get paginated events
    data_query = f"""
        SELECT
            event_id, timestamp, event_type, level, trace_id,
            user_id, user_email, message,
            query, response, chunks_json, latency_ms, token_count,
            status, error_detail, metadata_json,
            model_provider, model_name
        FROM events
        WHERE {where_sql}
        ORDER BY timestamp DESC
        LIMIT {limit} OFFSET {offset}
    """
    result = client.query(data_query, parameters=params)

    events = []
    columns = [
        "event_id",
        "timestamp",
        "event_type",
        "level",
        "trace_id",
        "user_id",
        "user_email",
        "message",
        "query",
        "response",
        "chunks_json",
        "latency_ms",
        "token_count",
        "status",
        "error_detail",
        "metadata_json",
        "model_provider",
        "model_name",
    ]
    for row in result.result_rows:
        event = dict(zip(columns, row))
        # Convert UUID and datetime to strings for JSON serialization
        event["event_id"] = str(event["event_id"])
        event["timestamp"] = (
            event["timestamp"].isoformat() if event["timestamp"] else None
        )
        events.append(event)

    return events, total


def get_traces(
    limit: int = 50,
    offset: int = 0,
    status: str = None,
    user_id: int = None,
    start_date: str = None,
    end_date: str = None,
    search: str = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get full traces (response-type events that carry the complete trace data).
    """
    return query_events(
        limit=limit,
        offset=offset,
        event_type="response",
        status=status,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
    )


def get_trace_events(trace_id: str) -> List[Dict[str, Any]]:
    """
    Get all events belonging to a specific trace, ordered chronologically.
    """
    events, _ = query_events(trace_id=trace_id, limit=1000)
    return sorted(events, key=lambda e: e.get("timestamp", ""))


def get_event_stats(hours: int = 24) -> Dict[str, Any]:
    """Get event statistics for the last N hours."""
    client = _get_client()

    stats_query = f"""
        SELECT
            event_type,
            count() as cnt,
            avg(latency_ms) as avg_latency,
            countIf(status = 'error') as error_count
        FROM events
        WHERE timestamp >= now() - INTERVAL {hours} HOUR
        GROUP BY event_type
        ORDER BY cnt DESC
    """
    result = client.query(stats_query)

    stats = {}
    for row in result.result_rows:
        stats[row[0]] = {
            "count": row[1],
            "avg_latency_ms": round(row[2], 2) if row[2] else None,
            "errors": row[3],
        }

    return stats


def health_check() -> bool:
    """Check if ClickHouse is reachable."""
    try:
        client = _get_client()
        client.query("SELECT 1")
        return True
    except Exception:
        return False
