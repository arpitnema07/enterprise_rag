"""
RAG Tracing Module - LangSmith-style logging for request/response monitoring.
Logs traces to JSONL files with automatic rotation.
"""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid

# Configuration
LOGS_DIR = Path(__file__).parent.parent / "logs"
TRACES_FILE = LOGS_DIR / "traces.jsonl"
MAX_FILE_SIZE_MB = 50


@dataclass
class ChunkInfo:
    """Information about a retrieved chunk."""

    text: str
    score: float
    page_number: int
    file_path: str
    group_id: int


@dataclass
class LatencyInfo:
    """Latency breakdown in milliseconds."""

    retrieval_ms: float = 0
    generation_ms: float = 0
    total_ms: float = 0


@dataclass
class TokenInfo:
    """Approximate token counts."""

    prompt: int = 0
    completion: int = 0
    total: int = 0


@dataclass
class Trace:
    """Complete trace of a RAG request."""

    trace_id: str
    timestamp: str
    user_id: Optional[int]
    user_email: Optional[str]
    query: str
    response: str
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    latency: Dict[str, float] = field(default_factory=dict)
    tokens: Dict[str, int] = field(default_factory=dict)
    status: str = "success"
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ensure_logs_dir():
    """Ensure logs directory exists."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def _rotate_if_needed():
    """Rotate log file if it exceeds max size, archiving with timestamp."""
    if not TRACES_FILE.exists():
        return

    file_size_mb = TRACES_FILE.stat().st_size / (1024 * 1024)
    if file_size_mb >= MAX_FILE_SIZE_MB:
        # Archive with date timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"traces_{timestamp}.jsonl"
        archive_path = LOGS_DIR / archive_name
        TRACES_FILE.rename(archive_path)


def log_trace(trace: Trace) -> None:
    """
    Log a trace to the JSONL file.

    Args:
        trace: Trace object to log
    """
    _ensure_logs_dir()
    _rotate_if_needed()

    with open(TRACES_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(trace.to_dict(), ensure_ascii=False) + "\n")


def create_trace(
    query: str,
    response: str,
    chunks: List[Dict[str, Any]],
    latency: LatencyInfo,
    tokens: TokenInfo,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
    status: str = "success",
    error: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Trace:
    """
    Create a new trace object.

    Args:
        query: User's query
        response: Generated response
        chunks: Retrieved chunks with scores
        latency: Latency breakdown
        tokens: Token counts
        user_id: Optional user ID
        user_email: Optional user email
        status: "success" or "error"
        error: Error message if status is error
        metadata: Additional metadata

    Returns:
        Trace object
    """
    return Trace(
        trace_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow().isoformat() + "Z",
        user_id=user_id,
        user_email=user_email,
        query=query,
        response=response,
        chunks=chunks,
        latency={
            "retrieval_ms": latency.retrieval_ms,
            "generation_ms": latency.generation_ms,
            "total_ms": latency.total_ms,
        },
        tokens={
            "prompt": tokens.prompt,
            "completion": tokens.completion,
            "total": tokens.total,
        },
        status=status,
        error=error,
        metadata=metadata or {},
    )


def get_traces(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    user_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[List[Dict[str, Any]], int]:
    """
    Get traces with optional filtering.

    Args:
        limit: Max number of traces to return
        offset: Number of traces to skip
        status: Filter by status ("success" or "error")
        user_id: Filter by user ID
        start_date: Filter by start date (ISO format)
        end_date: Filter by end date (ISO format)
        search: Search in query text

    Returns:
        Tuple of (list of traces, total count)
    """
    _ensure_logs_dir()

    if not TRACES_FILE.exists():
        return [], 0

    traces = []
    with open(TRACES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trace = json.loads(line)
                traces.append(trace)
            except json.JSONDecodeError:
                continue

    # Reverse to get newest first
    traces.reverse()

    # Apply filters
    filtered = []
    for trace in traces:
        if status and trace.get("status") != status:
            continue
        if user_id and trace.get("user_id") != user_id:
            continue
        if start_date:
            trace_date = trace.get("timestamp", "")[:10]
            if trace_date < start_date:
                continue
        if end_date:
            trace_date = trace.get("timestamp", "")[:10]
            if trace_date > end_date:
                continue
        if search and search.lower() not in trace.get("query", "").lower():
            continue
        filtered.append(trace)

    total = len(filtered)
    paginated = filtered[offset : offset + limit]

    return paginated, total


def get_trace_by_id(trace_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single trace by ID.

    Args:
        trace_id: The trace ID to find

    Returns:
        Trace dict or None if not found
    """
    _ensure_logs_dir()

    if not TRACES_FILE.exists():
        return None

    with open(TRACES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                trace = json.loads(line)
                if trace.get("trace_id") == trace_id:
                    return trace
            except json.JSONDecodeError:
                continue

    return None


def clear_traces() -> int:
    """
    Clear all traces by archiving the current file.

    Returns:
        Number of traces archived
    """
    _ensure_logs_dir()

    if not TRACES_FILE.exists():
        return 0

    # Count traces
    count = 0
    with open(TRACES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1

    # Archive with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"traces_archived_{timestamp}.jsonl"
    archive_path = LOGS_DIR / archive_name
    TRACES_FILE.rename(archive_path)

    return count


def estimate_tokens(text: str) -> int:
    """
    Estimate token count from text (rough approximation).

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    # Rough estimate: 1 token ≈ 4 characters or 0.75 words
    words = len(text.split())
    return int(words * 1.3)
