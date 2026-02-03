"""
Retrieval module for hybrid vector search.
Supports both dense (semantic) and sparse (BM25) vector search with RRF fusion.
"""

from typing import List, Any, Dict, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

# Configuration
QDRANT_HOST = "it38450"
QDRANT_PORT = 6333
COLLECTION_NAME = "vehicle_docs"

# Initialize client
_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection():
    """
    Ensure the Qdrant collection exists with hybrid vector support.
    Creates collection with both dense and sparse vector configurations.
    """
    collections = _client.get_collections()
    if COLLECTION_NAME not in [c.name for c in collections.collections]:
        _client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": rest.VectorParams(
                    size=768,  # nomic-embed-text
                    distance=rest.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse": rest.SparseVectorParams(
                    index=rest.SparseIndexParams(
                        on_disk=False,  # Keep BM25 index in memory for speed
                    )
                )
            },
        )


def recreate_collection():
    """
    Recreate the collection with hybrid vector support.
    WARNING: This will delete all existing data!
    """
    collections = _client.get_collections()
    if COLLECTION_NAME in [c.name for c in collections.collections]:
        _client.delete_collection(COLLECTION_NAME)
    ensure_collection()


def upload_points(points: List[rest.PointStruct]):
    """
    Upload points to Qdrant collection.
    Points should have both dense and sparse vectors.
    """
    _client.upsert(collection_name=COLLECTION_NAME, points=points)


def search(
    query_vector: List[float], group_ids: List[int], limit: int = 10
) -> List[Any]:
    """
    Search for similar vectors using dense vector only (legacy support).

    Args:
        query_vector: Query embedding vector (dense)
        group_ids: List of group IDs to filter by
        limit: Maximum number of results

    Returns:
        List of search results with payloads
    """
    filter_condition = rest.Filter(
        must=[
            rest.FieldCondition(
                key="metadata.group_id", match=rest.MatchAny(any=group_ids)
            )
        ]
    )

    return _client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        using="dense",
        query_filter=filter_condition,
        limit=limit,
    ).points


def hybrid_search(
    dense_vector: List[float],
    sparse_vector: Dict,
    group_ids: List[int],
    limit: int = 10,
    prefetch_limit: int = 20,
    filters: Optional[Dict] = None,
) -> List[Any]:
    """
    Hybrid search with RRF fusion of dense and sparse results.
    Uses Reciprocal Rank Fusion to combine semantic and keyword search.

    Args:
        dense_vector: Dense embedding vector (semantic)
        sparse_vector: Sparse vector dict with 'indices' and 'values' (BM25)
        group_ids: List of group IDs to filter by
        limit: Maximum number of final results
        prefetch_limit: Number of candidates to fetch from each search
        filters: Optional additional metadata filters

    Returns:
        List of search results with payloads
    """
    # Build filter conditions
    must_conditions = [
        rest.FieldCondition(key="metadata.group_id", match=rest.MatchAny(any=group_ids))
    ]

    # Add optional metadata filters
    if filters:
        # Filter by doc_id (extracted from query like ETR_02_24_12)
        if filters.get("doc_id"):
            must_conditions.append(
                rest.FieldCondition(
                    key="metadata.doc_id",
                    match=rest.MatchText(text=filters["doc_id"]),
                )
            )
        if filters.get("test_type"):
            must_conditions.append(
                rest.FieldCondition(
                    key="metadata.test_type",
                    match=rest.MatchValue(value=filters["test_type"]),
                )
            )
        if filters.get("vehicle_model"):
            must_conditions.append(
                rest.FieldCondition(
                    key="metadata.vehicle_model",
                    match=rest.MatchText(text=filters["vehicle_model"]),
                )
            )
        if filters.get("compliance_status"):
            must_conditions.append(
                rest.FieldCondition(
                    key="metadata.compliance_status",
                    match=rest.MatchAny(any=filters["compliance_status"]),
                )
            )

    filter_condition = rest.Filter(must=must_conditions)

    # Build prefetch queries for hybrid search
    prefetch_queries = [
        rest.Prefetch(query=dense_vector, using="dense", limit=prefetch_limit),
        rest.Prefetch(
            query=rest.SparseVector(
                indices=sparse_vector["indices"], values=sparse_vector["values"]
            ),
            using="sparse",
            limit=prefetch_limit,
        ),
    ]

    # Execute hybrid search with RRF fusion
    return _client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=prefetch_queries,
        query=rest.FusionQuery(fusion=rest.Fusion.RRF),
        query_filter=filter_condition,
        limit=limit,
    ).points


def get_collection_info():
    """Get information about the collection."""
    return _client.get_collection(COLLECTION_NAME)


def delete_by_file_path(file_path: str):
    """
    Delete all points associated with a specific file path.

    Args:
        file_path: Path of the file whose chunks should be deleted
    """
    _client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=rest.FilterSelector(
            filter=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="metadata.file_path", match=rest.MatchValue(value=file_path)
                    )
                ]
            )
        ),
    )


def get_client() -> QdrantClient:
    """Get the Qdrant client instance."""
    return _client
