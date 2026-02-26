import sys
import warnings
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from backend.rag.retrieval import _client, COLLECTION_NAME
from qdrant_client import models

try:
    print("Searching Qdrant for 'Pro 3012' exactly...")
    results = _client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=models.Filter(
            should=[
                models.FieldCondition(key="text", match=models.MatchText(text="3012")),
                models.FieldCondition(
                    key="text", match=models.MatchText(text="Pro 3012")
                ),
            ]
        ),
        limit=10,
        with_payload=True,
    )

    hits = results[0]
    print(f"Found {len(hits)} hits containing '3012' or 'Pro 3012'.")
    for hit in hits:
        print(
            f"- File: {hit.payload.get('metadata', {}).get('filename')}, Page: {hit.payload.get('metadata', {}).get('page_number')}"
        )
        print(f"  Snippet: {hit.payload.get('text')[:200]}")

except Exception as e:
    import traceback

    traceback.print_exc()
