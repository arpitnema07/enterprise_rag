import sys
import os
import requests
from dotenv import load_dotenv
from pathlib import Path
from datetime import timedelta

env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

from backend.auth import create_access_token

try:
    print("Generating JWT for admin@gmail.com...")
    access_token = create_access_token(
        data={"sub": "admin@gmail.com", "user_id": 3, "role": "admin"},
        expires_delta=timedelta(minutes=30),
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "message": "Hub Reduction Tandem Axle Analysis Final report",
        "group_id": 1,
        "is_agentic": True,
    }

    print("Sending request to backend...")
    url = "http://localhost:8001/documents/chat"
    response = requests.post(url, headers=headers, json=payload)

    print(f"Status: {response.status_code}")
    print("Response JSON:")
    print(response.json())
except Exception as e:
    import traceback

    traceback.print_exc()
