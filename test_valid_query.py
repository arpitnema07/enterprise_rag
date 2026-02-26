import sys
import warnings
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from backend.rag.agentic_router import run_agentic_query

warnings.filterwarnings("ignore")

try:
    print("Testing a known valid query...")
    # Using a term we saw in prompt_dump.txt
    res = run_agentic_query(
        query="What are the heat transfer boundary conditions for the CNG Cylinderhead?",
        group_ids=[1],
        group_id=1,
    )
    print(f"\nRetrieved {len(res['sources'])} chunks.")
    print("\n--- LLM Response ---")
    print(res["answer"])
except Exception as e:
    import traceback

    traceback.print_exc()
