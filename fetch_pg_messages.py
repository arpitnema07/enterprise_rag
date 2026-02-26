import sys
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from backend.database import SessionLocal
from backend.models import ChatMessage, Conversation


def get_latest_query():
    db = SessionLocal()
    try:
        # Get the 5 most recent messages
        messages = (
            db.query(ChatMessage).order_by(ChatMessage.created_at.desc()).limit(5).all()
        )
        for msg in messages:
            print("-" * 50)
            print(f"Time: {msg.created_at}")
            print(f"Role: {msg.role}")
            print(f"Content: {msg.content[:100]}")
            print(f"Conversation ID: {msg.conversation_id}")
            print(f"Sources count: {len(msg.sources_json) if msg.sources_json else 0}")
    finally:
        db.close()


if __name__ == "__main__":
    get_latest_query()
