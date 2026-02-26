import sys
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from backend.services.clickhouse_client import _get_client

try:
    client = _get_client()
    query = f"""
    SELECT 
        event_id,
        timestamp,
        event_type,
        query,
        message,
        response,
        model_name,
        metadata_json
    FROM {client.vecvrag_db}.events
    ORDER BY timestamp DESC
    LIMIT 20
    """

    res = client.query(query)
    for row in res.result_rows:
        print("-" * 50)
        print(
            f"Time: {row[1]}, Type: {row[2]}, Msg: {row[4][:100] if row[4] else None}"
        )
        if row[2] == "response" or row[2] == "error":
            if row[3]:
                print(f"Query: {row[3][:100]}")
            if row[5]:
                print(f"Response: {row[5][:200]}")
except Exception as e:
    import traceback

    traceback.print_exc()
