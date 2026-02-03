"""
Embeddings module for vector generation.
"""

from typing import List
from langchain_community.embeddings import OllamaEmbeddings

# Configuration
EMBEDDING_MODEL = "nomic-embed-text"
OLLAMA_BASE_URL = "http://it38450:11434"

# Initialize embeddings
_embeddings = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL)


def embed_text(text: str) -> List[float]:
    """
    Generate embedding vector for a single text.

    Args:
        text: Input text

    Returns:
        Embedding vector as list of floats
    """
    return _embeddings.embed_query(text)


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embedding vectors for multiple texts.

    Args:
        texts: List of input texts

    Returns:
        List of embedding vectors
    """
    return _embeddings.embed_documents(texts)
