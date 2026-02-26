"""
RAG (Retrieval Augmented Generation) module.
Provides document processing, embedding, retrieval, and generation capabilities.
"""

from .pipeline import process_document, generate_answer, generate_answer_with_context
from .retrieval import ensure_collection, hybrid_search, search
from .embeddings import embed_text, embed_texts
from .sparse_embeddings import embed_sparse, embed_sparse_batch
from .chunking import chunk_text, chunk_pdf_pages, split_by_sections
from .generation import generate_answer_with_history
from .metadata_extraction import extract_metadata
from .conversation import ConversationManager
from .prompt_manager import prompt_manager

__all__ = [
    "process_document",
    "generate_answer",
    "generate_answer_with_context",
    "ensure_collection",
    "hybrid_search",
    "search",
    "embed_text",
    "embed_texts",
    "embed_sparse",
    "embed_sparse_batch",
    "chunk_text",
    "chunk_pdf_pages",
    "split_by_sections",
    "generate_answer_with_history",
    "extract_metadata",
    "ConversationManager",
    "prompt_manager",
]
