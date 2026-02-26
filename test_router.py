import sys
import asyncio
from backend.rag.agentic_router import run_agentic_query

# Configure environment path
import warnings

warnings.filterwarnings("ignore")

try:
    res = run_agentic_query(
        query="what is the performance test of Pro 3012?",
        group_ids=[1],
        group_id=1,
    )
    print("Chunks:", len(res["sources"]))
    print("Latency:", res["latency"])
except Exception as e:
    print("Error:", e)
