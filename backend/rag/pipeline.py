"""
RAG Pipeline - Main orchestrator for PDF processing and query answering.
Supports hybrid search with dense and sparse vectors.
"""

import logging
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
from .observability import (
    log_retrieval,
    log_generation,
    log_response,
    estimate_tokens,
    generate_trace_id,
)
from .query_filters import extract_filters_from_query, build_enhanced_query
from .pdf_extractor import extract_pdf_with_tables

logger = logging.getLogger(__name__)


def _caption_images(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Generate captions for embedded images found in PDF pages.

    Args:
        pages: List of page dicts from extract_pdf_with_tables

    Returns:
        List of image caption chunks with 'text', 'page_number', 'chunk_type'
    """
    image_chunks = []

    # Count total images first
    total_images = sum(p.get("image_count", 0) for p in pages)
    if total_images == 0:
        return image_chunks

    logger.info(f"Found {total_images} embedded images across {len(pages)} pages")

    try:
        from .vision import caption_image, is_vision_available

        if not is_vision_available():
            logger.warning("Vision model not available — skipping image captioning")
            return image_chunks

        captioned = 0
        for page in pages:
            page_images = page.get("images", [])
            page_num = page.get("page_number", 1)

            for img in page_images:
                img_b64 = img.get("image_b64", "")
                if not img_b64:
                    continue

                caption = caption_image(img_b64)
                if caption:
                    image_chunks.append(
                        {
                            "text": f"[Image on page {page_num}]: {caption}",
                            "page_number": page_num,
                            "chunk_type": "image_caption",
                            "image_width": img.get("width", 0),
                            "image_height": img.get("height", 0),
                        }
                    )
                    captioned += 1

        logger.info(f"Generated {captioned}/{total_images} image captions")

    except ImportError:
        logger.warning("Vision module not available — skipping image captioning")
    except Exception as e:
        logger.error(f"Image captioning failed: {e}")

    return image_chunks


def process_pdf(file_path: str, group_id: int, metadata: Dict[str, Any] = {}) -> int:
    """
    Process a PDF file: extract text with tables + OCR fallback, chunk,
    embed (dense + sparse), caption images, and store in Qdrant.

    Args:
        file_path: Path to PDF file
        group_id: Group ID for access control
        metadata: Additional metadata to store

    Returns:
        Number of chunks processed
    """
    # Use enhanced extraction with table detection + hybrid OCR
    pages = extract_pdf_with_tables(file_path)

    # Log extraction methods used
    methods = {}
    for p in pages:
        m = p.get("extraction_method", "unknown")
        methods[m] = methods.get(m, 0) + 1
    logger.info(f"Extraction methods: {methods}")

    # Extract full document text for document-level metadata
    full_text = "\n".join([p.get("text", "") for p in pages])

    # Extract document-level metadata
    doc_name = metadata.get("filename", file_path)
    doc_metadata = extract_metadata(full_text, doc_name)

    # Chunk the pages (table-aware)
    chunks = chunk_pdf_pages(pages)

    # Generate image captions and add as additional chunks
    image_chunks = _caption_images(pages)
    chunks.extend(image_chunks)

    # Create Qdrant points with both dense and sparse vectors
    points = []
    for chunk in chunks:
        chunk_id = str(uuid.uuid4())
        chunk_text = chunk["text"]

        # Include filename/doc_id in searchable text for BM25 matching
        filename_clean = doc_name.replace(".pdf", "").replace("_", " ")
        searchable_text = (
            f"[Document: {doc_name}] [File: {filename_clean}]\n{chunk_text}"
        )

        # Generate dense embedding
        dense_vector = embed_text(searchable_text)

        # Generate sparse embedding (BM25)
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
                "chunk_type": chunk.get("chunk_type", "text"),
                "extraction_method": chunk.get("extraction_method", "pdfplumber"),
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

    logger.info(
        f"Processed {file_path}: {len(points)} chunks "
        f"({len(image_chunks)} image captions)"
    )

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
    top_score = trace_chunks[0]["score"] if trace_chunks else 0.0
    retrieval_ms = (retrieval_end - retrieval_start) * 1000
    trace_id = generate_trace_id()
    log_retrieval(len(trace_chunks), top_score, retrieval_ms, trace_id=trace_id)

    # Generate answer
    generation_start = time.time()
    answer = llm_generate(query, context_chunks)
    generation_end = time.time()

    # Log generation
    generation_ms = (generation_end - generation_start) * 1000
    prompt_text = query + " ".join([c["text"] for c in context_chunks])
    log_generation(
        estimate_tokens(prompt_text),
        estimate_tokens(answer),
        generation_ms,
        trace_id=trace_id,
    )

    total_end = time.time()
    total_ms = (total_end - total_start) * 1000

    # Log unified trace
    try:
        total_tokens = estimate_tokens(prompt_text) + estimate_tokens(answer)
        log_response(
            query=query,
            response_text=answer,
            chunks=trace_chunks,
            latency_ms=total_ms,
            token_count=total_tokens,
            trace_id=trace_id,
            user_id=user_id,
            user_email=user_email,
        )
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
