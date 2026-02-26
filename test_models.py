import asyncio
import dotenv

dotenv.load_dotenv()
from backend.rag.agentic_router import run_agentic_query


async def test_providers():
    query = "Hub Reduction Tandem Axle Analysis Final report"
    group_ids = [1]

    print("Testing with NVIDIA...")
    res_nvidia = run_agentic_query(
        query=query,
        group_ids=group_ids,
        user_id=3,
        session_id="test_nv",
        group_id=1,
        prompt_type="technical",
        history=[],
        model_provider="nvidia",
        model_name="meta/llama-3.1-405b-instruct",
    )
    print(f"NVIDIA Response: {res_nvidia['answer'][:100]}...\n")

    print("Testing with Ollama (Llama3.2:3b)...")
    res_ollama = run_agentic_query(
        query=query,
        group_ids=group_ids,
        user_id=3,
        session_id="test_ol",
        group_id=1,
        prompt_type="technical",
        history=[],
        model_provider="ollama",
        model_name="llama3.2:3b",
    )
    print(f"Ollama Response: {res_ollama['answer'][:100]}...\n")


if __name__ == "__main__":
    asyncio.run(test_providers())
