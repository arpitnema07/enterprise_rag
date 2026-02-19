-- ClickHouse initialization schema for VECVRAG observability
-- This runs automatically when the ClickHouse container starts for the first time.

CREATE TABLE IF NOT EXISTS vecvrag.events (
    event_id     UUID DEFAULT generateUUIDv4(),
    timestamp    DateTime64(3) DEFAULT now64(3),
    event_type   Enum8(
        'request'    = 1,
        'embedding'  = 2,
        'retrieval'  = 3,
        'generation' = 4,
        'response'   = 5,
        'upload'     = 6,
        'reindex'    = 7,
        'system'     = 8,
        'error'      = 9
    ),
    level        Enum8(
        'DEBUG'   = 1,
        'INFO'    = 2,
        'WARNING' = 3,
        'ERROR'   = 4
    ) DEFAULT 'INFO',
    trace_id       String DEFAULT '',
    user_id        Nullable(Int32),
    user_email     Nullable(String),
    message        String,

    -- Trace-specific fields (populated on 'response' events)
    query          Nullable(String),
    response       Nullable(String),
    chunks_json    Nullable(String),
    latency_ms     Nullable(Float64),
    token_count    Nullable(Int32),
    status         Nullable(Enum8('success' = 1, 'error' = 2)),
    error_detail   Nullable(String),
    metadata_json  Nullable(String),

    -- Model info
    model_provider Nullable(String),
    model_name     Nullable(String)
)
ENGINE = MergeTree()
ORDER BY (timestamp, trace_id)
TTL toDateTime(timestamp) + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;
