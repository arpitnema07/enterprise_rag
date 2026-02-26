import sys
import warnings
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from backend.rag.agentic_router import run_agentic_query

warnings.filterwarnings("ignore")

try:
    print("Running query...")
    res = run_agentic_query(
        query="what is the performance test of Pro 3012?",
        group_ids=[1],
        group_id=1,
    )
    print(f"\nRetrieved {len(res['sources'])} chunks.")

    # Let's inspect the context that was built
    from backend.rag.generation import format_context

    chunks = res.get("retrieved_chunks", res.get("sources", []))
    # Note: run_agentic_query drops retrieved_chunks from final output
    if "retrieved_chunks" not in res and not chunks[0].get("text"):
        # Sources uses "full_text" instead of "text"
        for s in chunks:
            s["text"] = s.get("full_text", "")

    context = format_context(chunks)
    print(f"\nContext length: {len(context)} characters")
    print(f"Sample context: {context[:500]}")

    print("\n--- LLM Response ---")
    print(res["answer"])
except Exception as e:
    import traceback

    traceback.print_exc()
