"""
RAG Pipeline - Main orchestrator for PDF processing and query answering.
Supports hybrid search with dense and sparse vectors.
"""

import uuid
import time
from typing import List, Dict, Any, Optional
from qdrant_client.http import models as rest

from .chunking import chunk_pdf_pages
from .embeddings import embed_text
from .sparse_embeddings import embed_sparse
from .metadata_extraction import extract_metadata, merge_metadata
from .retrieval import upload_points, search, hybrid_search
from .generation import generate_answer as llm_generate, generate_answer_with_history
from .tracer import create_trace, log_trace, LatencyInfo, TokenInfo, estimate_tokens
from .query_filters import extract_filters_from_query, build_enhanced_query
from .pdf_extractor import extract_pdf_with_tables


def process_pdf(file_path: str, group_id: int, metadata: Dict[str, Any] = {}) -> int:
    """
    Process a PDF file: extract text with tables, chunk, embed (dense + sparse), and store in Qdrant.

    Args:
        file_path: Path to PDF file
        group_id: Group ID for access control
        metadata: Additional metadata to store

    Returns:
        Number of chunks processed
    """
    # Use enhanced extraction with table detection
    pages = extract_pdf_with_tables(file_path)

    # Extract full document text for document-level metadata
    full_text = "\n".join([p.get("text", "") for p in pages])

    # Extract document-level metadata
    doc_name = metadata.get("filename", file_path)
    doc_metadata = extract_metadata(full_text, doc_name)

    # Chunk the pages (table-aware)
    chunks = chunk_pdf_pages(pages)

    # Create Qdrant points with both dense and sparse vectors
    points = []
    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        chunk_text = chunk["text"]

        # Approach 1: Include filename/doc_id in searchable text
        # This allows BM25 sparse search to match document names
        filename_clean = doc_name.replace(".pdf", "").replace("_", " ")
        searchable_text = (
            f"[Document: {doc_name}] [File: {filename_clean}]\n{chunk_text}"
        )

        # Generate dense embedding (using enhanced text)
        dense_vector = embed_text(searchable_text)

        # Generate sparse embedding (BM25) - also use searchable text for filename matching
        sparse_vector = embed_sparse(searchable_text)

        # Extract chunk-level metadata
        chunk_meta = extract_metadata(chunk_text, doc_name)

        # Merge document and chunk metadata
        merged_metadata = merge_metadata(doc_metadata, chunk_meta)

        # Build payload with enhanced metadata
        payload = {
            "text": chunk_text,
            "metadata": {
                "group_id": group_id,
                "page_number": chunk["page_number"],
                "file_path": file_path,
                "section": chunk.get("section", ""),
                "doc_id": doc_name,
                "vehicle_model": merged_metadata.get("vehicle_model"),
                "chassis_no": merged_metadata.get("chassis_no"),
                "test_date": merged_metadata.get("test_date"),
                "test_type": merged_metadata.get("test_type"),
                "test_parameters": merged_metadata.get("test_parameters", []),
                "compliance_status": merged_metadata.get("compliance_status", []),
                "standards": merged_metadata.get("standards", []),
                "keywords": merged_metadata.get("keywords", []),
                **metadata,
            },
        }

        # Create point with named vectors for hybrid search
        points.append(
            rest.PointStruct(
                id=chunk_id,
                vector={
                    "dense": dense_vector,
                    "sparse": rest.SparseVector(
                        indices=sparse_vector["indices"], values=sparse_vector["values"]
                    ),
                },
                payload=payload,
            )
        )

    # Upload to Qdrant
    upload_points(points)

    return len(points)


def generate_answer(
    query: str,
    group_ids: List[int],
    use_hybrid: bool = True,
    user_id: Optional[int] = None,
    user_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an answer to a query based on documents in specified groups.
    Uses hybrid search by default for improved retrieval.

    Args:
        query: User question
        group_ids: List of group IDs to search within
        use_hybrid: Whether to use hybrid search (default True)
        user_id: Optional user ID for tracing
        user_email: Optional user email for tracing

    Returns:
        Dict with 'answer' and 'sources'
    """
    total_start = time.time()
    retrieval_start = time.time()

    # Approach 2: Auto-extract filters from query (doc_id, vehicle_model, etc.)
    _, extracted_filters = extract_filters_from_query(query)

    # Build enhanced query for better matching
    enhanced_query = build_enhanced_query(query, extracted_filters)

    # Embed query - both dense and sparse for hybrid search
    dense_vector = embed_text(enhanced_query)

    if use_hybrid:
        sparse_vector = embed_sparse(enhanced_query)
        search_results = hybrid_search(
            dense_vector,
            sparse_vector,
            group_ids,
            filters=extracted_filters if extracted_filters else None,
        )
    else:
        search_results = search(dense_vector, group_ids)

    retrieval_end = time.time()

    # Build context and sources
    context_chunks = []
    sources = []
    trace_chunks = []

    for hit in search_results:
        chunk_text = hit.payload.get("text", "")
        chunk_metadata = hit.payload.get("metadata", {})

        context_chunks.append({"text": chunk_text, "metadata": chunk_metadata})

        source_info = {
            "page_number": chunk_metadata.get("page_number"),
            "group_id": chunk_metadata.get("group_id"),
            "file_path": chunk_metadata.get("file_path"),
            "filename": chunk_metadata.get("filename"),
            "section": chunk_metadata.get("section"),
            "test_type": chunk_metadata.get("test_type"),
            "text_snippet": chunk_text[:200] + "..."
            if len(chunk_text) > 200
            else chunk_text,
            "full_text": chunk_text,
        }
        sources.append(source_info)

        # Track chunks for tracing
        trace_chunks.append(
            {
                "text": chunk_text[:500] + "..."
                if len(chunk_text) > 500
                else chunk_text,
                "score": getattr(hit, "score", 0.0),
                "page_number": chunk_metadata.get("page_number"),
                "file_path": chunk_metadata.get("file_path"),
                "group_id": chunk_metadata.get("group_id"),
            }
        )

    # Log retrieval results
    from .realtime_logger import log_retrieval, log_generation

    top_score = trace_chunks[0]["score"] if trace_chunks else 0.0
    retrieval_ms = (retrieval_end - retrieval_start) * 1000
    log_retrieval(len(trace_chunks), top_score, retrieval_ms)

    # Generate answer
    generation_start = time.time()
    answer = llm_generate(query, context_chunks)
    generation_end = time.time()

    # Log generation
    generation_ms = (generation_end - generation_start) * 1000
    prompt_text = query + " ".join([c["text"] for c in context_chunks])
    from .tracer import estimate_tokens as est_tokens

    log_generation(est_tokens(prompt_text), est_tokens(answer), generation_ms)

    total_end = time.time()

    # Log trace
    try:
        latency = LatencyInfo(
            retrieval_ms=(retrieval_end - retrieval_start) * 1000,
            generation_ms=(generation_end - generation_start) * 1000,
            total_ms=(total_end - total_start) * 1000,
        )

        # Estimate tokens
        prompt_text = query + " ".join([c["text"] for c in context_chunks])
        tokens = TokenInfo(
            prompt=estimate_tokens(prompt_text),
            completion=estimate_tokens(answer),
            total=estimate_tokens(prompt_text) + estimate_tokens(answer),
        )

        trace = create_trace(
            query=query,
            response=answer,
            chunks=trace_chunks,
            latency=latency,
            tokens=tokens,
            user_id=user_id,
            user_email=user_email,
        )
        log_trace(trace)
    except Exception as e:
        print(f"Warning: Failed to log trace: {e}")

    return {"answer": answer, "sources": sources}


def generate_answer_with_context(
    query: str,
    group_ids: List[int],
    history: Optional[List[Dict[str, str]]] = None,
    filters: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Generate an answer with conversation history and optional filters.
    Uses hybrid search with metadata filtering.

    Args:
        query: User question
        group_ids: List of group IDs to search within
        history: Optional conversation history
        filters: Optional metadata filters (test_type, vehicle_model, etc.)

    Returns:
        Dict with 'answer' and 'sources'
    """
    # Embed query for hybrid search
    dense_vector = embed_text(query)
    sparse_vector = embed_sparse(query)

    # Hybrid search with filters
    search_results = hybrid_search(
        dense_vector, sparse_vector, group_ids, filters=filters
    )

    # Build context and sources
    context_chunks = []
    sources = []

    for hit in search_results:
        chunk_text = hit.payload.get("text", "")
        chunk_metadata = hit.payload.get("metadata", {})

        context_chunks.append({"text": chunk_text, "metadata": chunk_metadata})

        sources.append(
            {
                "page_number": chunk_metadata.get("page_number"),
                "group_id": chunk_metadata.get("group_id"),
                "file_path": chunk_metadata.get("file_path"),
                "filename": chunk_metadata.get("filename"),
                "section": chunk_metadata.get("section"),
                "test_type": chunk_metadata.get("test_type"),
                "vehicle_model": chunk_metadata.get("vehicle_model"),
                "text_snippet": chunk_text[:200] + "..."
                if len(chunk_text) > 200
                else chunk_text,
                "full_text": chunk_text,
            }
        )

    # Generate answer with history
    answer = generate_answer_with_history(query, context_chunks, history)

    return {"answer": answer, "sources": sources}
