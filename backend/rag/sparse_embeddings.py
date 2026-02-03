"""
Sparse Embeddings module for BM25 vector generation.
Uses fastembed for efficient BM25 sparse vector creation.
"""

from typing import List, Dict
from fastembed import SparseTextEmbedding

# Initialize BM25 sparse model (lazy loading)
_sparse_model = None


def _get_sparse_model() -> SparseTextEmbedding:
    """Get or initialize the sparse embedding model."""
    global _sparse_model
    if _sparse_model is None:
        _sparse_model = SparseTextEmbedding("Qdrant/bm25")
    return _sparse_model


def embed_sparse(text: str) -> Dict:
    """
    Generate BM25 sparse vector for a single text.

    Args:
        text: Input text

    Returns:
        Dict with 'indices' and 'values' for sparse vector
    """
    model = _get_sparse_model()
    result = list(model.embed([text]))[0]
    return {"indices": result.indices.tolist(), "values": result.values.tolist()}


def embed_sparse_batch(texts: List[str]) -> List[Dict]:
    """
    Generate BM25 sparse vectors for multiple texts.

    Args:
        texts: List of input texts

    Returns:
        List of dicts with 'indices' and 'values' for each text
    """
    model = _get_sparse_model()
    results = list(model.embed(texts))
    return [
        {"indices": r.indices.tolist(), "values": r.values.tolist()} for r in results
    ]
