import sys
import warnings
from dotenv import load_dotenv
from pathlib import Path

warnings.filterwarnings("ignore")
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from backend.rag.agentic_router import get_agentic_graph
from backend.rag.generation import format_context
from backend.rag.group_prompts import get_system_prompt

try:
    graph = get_agentic_graph()
    state = {
        "query": "what is the performance test of Pro 3012?",
        "session_id": "",
        "user_id": 0,
        "group_id": 1,
        "group_ids": [1],
        "prompt_type": "technical",
        "history": [],
        "model_provider": "nvidia",
        "model_name": "",
        "intent": "document_query",
        "intent_confidence": 1.0,
        "metadata_filters": {},
        "enhanced_query": "what is the performance test of Pro 3012?",
        "retrieved_chunks": [],
        "response": "",
        "sources": [],
        "retrieval_ms": 0.0,
        "generation_ms": 0.0,
        "stream_queue": None,
    }

    state = graph.nodes["extract_metadata"].invoke(state)
    state = graph.nodes["retrieve"].invoke(state)

    chunks = state.get("retrieved_chunks", [])
    print(f"\nRetrieved {len(chunks)} chunks.")

    context = format_context(chunks)

    prompt_parts = get_system_prompt("technical", context, state["query"], "")

    with open("prompt_dump.txt", "w", encoding="utf-8") as f:
        f.write("=== SYSTEM PROMPT ===\n")
        f.write(prompt_parts["system_prompt"])
        f.write("\n\n=== USER PROMPT ===\n")
        f.write(prompt_parts["user_prompt"])

    print("Wrote full prompts to prompt_dump.txt")
except Exception as e:
    import traceback

    traceback.print_exc()
