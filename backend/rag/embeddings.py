"""
Embeddings module for vector generation.
"""

import os
from typing import List

# Configuration
EMBEDDING_MODEL = "nomic-embed-text"

# Lazy-initialize embeddings
_embeddings = None


def _get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_community.embeddings import OllamaEmbeddings

        base_url = os.getenv(
            "OLLAMA_BASE_URL", "http://SRPTH1IDMQFS02.vecvnet.com:11434"
        )
        _embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=base_url)
    return _embeddings


def embed_text(text: str) -> List[float]:
    """
    Generate embedding vector for a single text.

    Args:
        text: Input text

    Returns:
        Embedding vector as list of floats
    """
    return _get_embeddings().embed_query(text)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embedding vectors for multiple texts.

    Args:
        texts: List of input texts

    Returns:
        List of embedding vectors
    """
    return _get_embeddings().embed_documents(texts)
