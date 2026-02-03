from qdrant_client import QdrantClient
from qdrant_client.http import models as rest

# QDrant Config - Hardcoded for MVP, should be Env Vars
QDRANT_HOST = "it38450"
QDRANT_PORT = 6333
COLLECTION_NAME = "vehicle_docs"

client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection():
    collections = client.get_collections()
    if COLLECTION_NAME not in [c.name for c in collections.collections]:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=rest.VectorParams(
                size=768,  # e.g. for nomic-embed-text
                distance=rest.Distance.COSINE,
            ),
        )


def upload_points(points):
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def search(query_vector, group_ids, limit=10):
    # Filter by group_ids
    filter_condition = rest.Filter(
        must=[
            rest.FieldCondition(
                key="metadata.group_id", match=rest.MatchAny(any=group_ids)
            )
        ]
    )

    return client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=filter_condition,
        limit=limit,
    ).points
