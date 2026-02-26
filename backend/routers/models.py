"""
Router for listing available LLM models (Ollama + Cloud/NVIDIA).
"""

import os
import requests
from fastapi import APIRouter

router = APIRouter(prefix="/models", tags=["models"])

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")

# Hardcoded cloud model options
CLOUD_MODELS = [
    {
        "name": "moonshotai/kimi-k2-instruct",
        "provider": "nvidia",
        "label": "Kimi K2 Instruct",
        "description": "Fast, high-quality reasoning model",
    },
    {
        "name": "meta/llama-3.3-70b-instruct",
        "provider": "nvidia",
        "label": "Llama 3.3 70B",
        "description": "Meta's flagship open model",
    },
    {
        "name": "nvidia/llama-3.1-nemotron-ultra-253b-v1",
        "provider": "nvidia",
        "label": "Nemotron Ultra 253B",
        "description": "NVIDIA's most capable model",
    },
]


def _fetch_ollama_models() -> list:
    """Fetch installed chat/generation models from Ollama API (excludes embedding models)."""
    # Model name patterns that indicate non-chat models
    NON_CHAT_KEYWORDS = ["embed", "bert", "rerank", "clip", "whisper"]

    try:
        response = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()

        models = []
        for model in data.get("models", []):
            name = model.get("name", "")

            # Skip non-chat models (embedding, reranking, etc.)
            if any(kw in name.lower() for kw in NON_CHAT_KEYWORDS):
                continue

            size_bytes = model.get("size", 0)
            size_gb = round(size_bytes / (1024**3), 1) if size_bytes else None

            models.append(
                {
                    "name": name,
                    "provider": "ollama",
                    "label": name.split(":")[0].title(),
                    "size": f"{size_gb} GB" if size_gb else "Unknown",
                    "description": f"Local model ({size_gb} GB)"
                    if size_gb
                    else "Local model",
                }
            )

        return models
    except Exception as e:
        print(f"Warning: Could not fetch Ollama models: {e}")
        return []


@router.get("")
def list_models():
    """
    List all available LLM models grouped by provider.
    Fetches installed Ollama models dynamically and includes hardcoded cloud options.
    """
    ollama_models = _fetch_ollama_models()

    # Only show cloud models if API key is configured
    cloud_models = CLOUD_MODELS if NVIDIA_API_KEY else []
    # cloud_models = []

    return {
        "ollama": ollama_models,
        "cloud": cloud_models,
    }
