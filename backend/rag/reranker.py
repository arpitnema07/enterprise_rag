"""
Reranker module.
Uses cross-encoder models to re-score retrieval results for higher precision.
"""

import logging
from typing import List, Dict, Any
from fastembed.rerank.cross_encoder import TextCrossEncoder

logger = logging.getLogger(__name__)

# Initialize the cross-encoder model
# BAAI/bge-reranker-base is highly capable and fast enough for CPU inference
_reranker = None


def get_reranker():
    global _reranker
    if _reranker is None:
        logger.info("Initializing fastembed cross-encoder (BAAI/bge-reranker-base)...")
        _reranker = TextCrossEncoder(model_name="BAAI/bge-reranker-base")
    return _reranker


def rerank_chunks(
    query: str, chunks: List[Dict[str, Any]], top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Rerank a list of chunks based on their relevance to the query.

    Args:
        query: User query
        chunks: List of retrieved chunks (payloads)
        top_k: Number of chunks to return after reranking

    Returns:
        List of reranked chunks, sorted by relevance score
    """
    if not chunks:
        return []

    model = get_reranker()

    # Extract text content from chunks (handling both 'text_snippet' and 'page_content' formats)
    documents = [
        chunk.get("text_snippet")
        or chunk.get("page_content")
        or chunk.get("text")
        or ""
        for chunk in chunks
    ]

    # Score documents
    try:
        # fastembed model.rerank yields a sequence of float scores corresponding to the documents
        scores = list(model.rerank(query, documents))

        # In fastembed recent versions, it might yield objects with .score.
        # Handle both float and object cases
        if scores and hasattr(scores[0], "score"):
            scores = [s.score for s in scores]

        # Attach scores to chunks and apply length heuristics
        scored_chunks = []
        for chunk, score in zip(chunks, scores):
            text = (
                chunk.get("text_snippet")
                or chunk.get("page_content")
                or chunk.get("text")
                or ""
            )
            word_count = len(text.split())

            # Filter out very small chunks (like footers or page numbers) unless they are tables or images
            if (
                word_count < 15
                and "[Image" not in text
                and "[TABLE" not in text
                and "|" not in text
            ):
                continue

            chunk_copy = dict(chunk)
            chunk_copy["rerank_score"] = float(score)
            scored_chunks.append(chunk_copy)

        # Sort by score descending
        scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Fallback if filtering removed everything
        if not scored_chunks and chunks:
            scored_chunks = []
            for chunk, score in zip(chunks, scores):
                chunk_copy = dict(chunk)
                chunk_copy["rerank_score"] = float(score)
                scored_chunks.append(chunk_copy)
            scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)

        # Return top_k
        return scored_chunks[:top_k]

    except Exception as e:
        logger.error(f"Error during reranking: {e}", exc_info=True)
        # Fallback to original ordering if reranking fails
        return chunks[:top_k]
