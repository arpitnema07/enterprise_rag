import asyncio
from backend.rag.agentic_router import run_agentic_query
import warnings

warnings.filterwarnings("ignore")

res = run_agentic_query(
    query="what is the power of the engine?",
    group_ids=[1],
    group_id=1,
)
print("Result:")
print("Chunks:", len(res.get("sources", [])))
print("Intent:", res.get("intent"))
print("Answer:", res.get("answer"))
