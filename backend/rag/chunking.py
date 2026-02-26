"""
Chunking module for text splitting with section awareness.
Supports both simple word-based chunking and structure-aware splitting.
"""

import re
from typing import List, Dict, Any


def chunk_text(text: str, chunk_size: int = 200, overlap: int = 40) -> List[str]:
    """
    Split text into overlapping chunks based on word count.

    Args:
        text: Input text to chunk
        chunk_size: Number of words per chunk
        overlap: Number of words to overlap between chunks

    Returns:
        List of text chunks
    """
    # Clean text
    text = " ".join(text.split())
    words = text.split()

    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk_words = words[i : i + chunk_size]
        if chunk_words:  # Don't add empty chunks
            chunks.append(" ".join(chunk_words))

    return chunks


def chunk_document_pages(
    pages: List[Dict[str, Any]], chunk_size: int = 300, overlap: int = 50
) -> List[Dict[str, Any]]:
    """
    Chunk text from document pages (PDF/PPTX) with format-awareness.
    Tables are kept as single chunks. PPTX slides are kept as single chunks where possible.

    Args:
        pages: List of dicts with 'text', 'page_number', 'extraction_method' keys
        chunk_size: Number of words per chunk
        overlap: Number of words to overlap

    Returns:
        List of chunk dicts with 'text', 'page_number', 'chunk_type' keys
    """
    all_chunks = []

    for page in pages:
        page_text = page.get("text", "")
        page_num = page.get("page_number", 1)
        method = page.get("extraction_method", "")

        # PPTX Strategy: One slide is conceptually one semantic unit
        if method == "python-pptx":
            word_count = len(page_text.split())
            if (
                word_count <= chunk_size * 1.5
            ):  # Allow slightly larger chunks for slides
                if page_text.strip():
                    all_chunks.append(
                        {
                            "text": page_text,
                            "page_number": page_num,
                            "chunk_type": "slide",
                        }
                    )
                continue
            # If the slide is massive, fall through to standard chunking

        # Check if page has table markers
        if (
            "[TABLE" in page_text
            or "### Table" in page_text
            or "--- Table Data ---" in page_text
        ):
            # Split content by table markers
            chunks = _chunk_with_tables(page_text, page_num, chunk_size, overlap)
            all_chunks.extend(chunks)
        else:
            # Standard text chunking
            chunks = chunk_text(page_text, chunk_size, overlap)
            for chunk in chunks:
                all_chunks.append(
                    {"text": chunk, "page_number": page_num, "chunk_type": "text"}
                )

    return all_chunks


# For backward compatibility with pipeline.py if it still calls chunk_pdf_pages:
def chunk_pdf_pages(
    pages: List[Dict[str, Any]], chunk_size: int = 300, overlap: int = 50
) -> List[Dict[str, Any]]:
    return chunk_document_pages(pages, chunk_size, overlap)


def _chunk_with_tables(
    text: str, page_num: int, chunk_size: int, overlap: int
) -> List[Dict[str, Any]]:
    """
    Chunk text while keeping tables intact.

    Args:
        text: Page text with table markers
        page_num: Page number
        chunk_size: Words per text chunk
        overlap: Word overlap

    Returns:
        List of chunks with type indicators
    """
    import re

    chunks = []

    # Split by table markers (keep the markers)
    # Pattern matches both [TABLE X...] and ### Table X formats
    table_pattern = r"(\n*(?:\[TABLE \d+[^\]]*\]|\#\#\# Table \d+[^\n]*)\n\|[^\n]+\|[\s\S]*?(?=\n\n(?!\|)|$))"

    parts = re.split(table_pattern, text)

    text_buffer = ""

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check if this is a table
        if (
            part.startswith("[TABLE")
            or part.startswith("### Table")
            or (part.startswith("|") and "---" in part)
        ):
            # First, flush any buffered text
            if text_buffer.strip():
                text_chunks = chunk_text(text_buffer, chunk_size, overlap)
                for chunk in text_chunks:
                    chunks.append(
                        {"text": chunk, "page_number": page_num, "chunk_type": "text"}
                    )
                text_buffer = ""

            # Add table as single chunk (don't split tables)
            chunks.append(
                {"text": part, "page_number": page_num, "chunk_type": "table"}
            )
        else:
            # Accumulate text
            text_buffer += "\n" + part

    # Flush remaining text
    if text_buffer.strip():
        text_chunks = chunk_text(text_buffer, chunk_size, overlap)
        for chunk in text_chunks:
            chunks.append(
                {"text": chunk, "page_number": page_num, "chunk_type": "text"}
            )

    return chunks


def split_by_sections(text: str) -> List[Dict[str, Any]]:
    """
    Split document by section headers for structure-aware chunking.
    Identifies common section header patterns and groups text accordingly.

    Args:
        text: Full document text

    Returns:
        List of section dicts with 'header', 'text', and 'page' keys
    """
    # Patterns for common section headers
    section_patterns = [
        r"^(?:#{1,3}\s+)(.+)$",  # Markdown headers
        r"^(\d+\.?\s+[A-Z][A-Za-z\s]+)$",  # Numbered sections
        r"^([A-Z][A-Z\s]+):?\s*$",  # ALL CAPS headers
        r"^((?:Test|Report|Section|Chapter)\s+\d+[:\.\s].*)$",  # Test/Report/Section headers
    ]

    sections = []
    current_section = {"header": "Introduction", "text": "", "page": 1}

    for line in text.split("\n"):
        stripped = line.strip()

        # Check if line matches any section header pattern
        is_header = False
        for pattern in section_patterns:
            if re.match(pattern, stripped, re.MULTILINE):
                is_header = True
                break

        if is_header and len(stripped) > 3:
            # Save previous section if it has content
            if current_section["text"].strip():
                sections.append(current_section.copy())

            # Start new section
            current_section = {
                "header": stripped,
                "text": "",
                "page": 1,  # Page tracking would need PDF metadata
            }
        else:
            current_section["text"] += line + "\n"

    # Add final section
    if current_section["text"].strip():
        sections.append(current_section)

    return sections


def chunk_with_sections(
    pages: List[Dict[str, Any]], chunk_size: int = 200, overlap: int = 40
) -> List[Dict[str, Any]]:
    """
    Chunk PDF pages with section awareness.
    First splits by sections, then chunks within each section.

    Args:
        pages: List of page dicts with 'text' and 'page_number'
        chunk_size: Words per chunk
        overlap: Word overlap between chunks

    Returns:
        List of chunk dicts with 'text', 'page_number', 'section' keys
    """
    all_chunks = []

    for page in pages:
        page_text = page.get("text", "")
        page_num = page.get("page_number", 1)

        # Split page into sections
        sections = split_by_sections(page_text)

        for section in sections:
            section_text = section.get("text", "")
            section_header = section.get("header", "")

            # Chunk within section
            chunks = chunk_text(section_text, chunk_size, overlap)

            for chunk in chunks:
                all_chunks.append(
                    {"text": chunk, "page_number": page_num, "section": section_header}
                )

    return all_chunks
