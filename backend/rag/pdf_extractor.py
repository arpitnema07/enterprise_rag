"""
Enhanced PDF Extraction with Table Detection.
Uses pdfplumber for precise table extraction and converts to Markdown format.
"""

import pdfplumber
from typing import List, Dict, Any
import re


def extract_tables_as_markdown(page: pdfplumber.page.Page) -> List[Dict[str, Any]]:
    """
    Extract tables from a PDF page and convert to Markdown format.

    Args:
        page: pdfplumber page object

    Returns:
        List of table dicts with 'markdown', 'bbox', 'row_count', 'col_count'
    """
    tables = []

    try:
        page_tables = page.extract_tables()

        for idx, table in enumerate(page_tables):
            if not table or len(table) < 1:
                continue

            # Convert table to Markdown
            markdown_lines = []

            # First row as header
            if table[0]:
                headers = [str(cell).strip() if cell else "" for cell in table[0]]
                markdown_lines.append("| " + " | ".join(headers) + " |")
                markdown_lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

            # Data rows
            for row in table[1:]:
                if row:
                    cells = [
                        str(cell).strip().replace("\n", " ") if cell else ""
                        for cell in row
                    ]
                    # Ensure same number of cells as header
                    while len(cells) < len(table[0]):
                        cells.append("")
                    markdown_lines.append(
                        "| " + " | ".join(cells[: len(table[0])]) + " |"
                    )

            if markdown_lines:
                tables.append(
                    {
                        "markdown": "\n".join(markdown_lines),
                        "row_count": len(table),
                        "col_count": len(table[0]) if table[0] else 0,
                        "table_index": idx,
                    }
                )

    except Exception as e:
        print(f"Warning: Table extraction failed: {e}")

    return tables


def extract_page_content(pdf_path: str, page_num: int) -> Dict[str, Any]:
    """
    Extract all content from a PDF page including tables.

    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)

    Returns:
        Dict with 'text', 'tables', 'combined_text'
    """
    with pdfplumber.open(pdf_path) as pdf:
        if page_num >= len(pdf.pages):
            return {"text": "", "tables": [], "combined_text": ""}

        page = pdf.pages[page_num]

        # Extract tables first
        tables = extract_tables_as_markdown(page)

        # Get table bounding boxes to exclude from text extraction
        table_bboxes = []
        try:
            for table in page.find_tables():
                table_bboxes.append(table.bbox)
        except Exception:
            pass

        # Extract text, excluding table areas if possible
        full_text = page.extract_text() or ""

        # Build combined content with tables inline
        combined_parts = []

        # Add regular text
        if full_text.strip():
            combined_parts.append(full_text)

        # Add tables as Markdown blocks
        for i, table in enumerate(tables):
            table_header = f"\n\n[TABLE {i + 1} - {table['row_count']} rows x {table['col_count']} columns]\n"
            combined_parts.append(table_header + table["markdown"])

        return {
            "text": full_text,
            "tables": tables,
            "combined_text": "\n".join(combined_parts),
        }


def extract_pdf_with_tables(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extract all pages from PDF with enhanced table handling.

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of page dicts with 'text', 'tables', 'page_number', 'has_tables'
    """
    pages = []

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Extract tables
                tables = extract_tables_as_markdown(page)

                # Extract text
                text = page.extract_text() or ""

                # Build enhanced text with tables
                combined_parts = [text] if text.strip() else []

                for i, table in enumerate(tables):
                    # Add table context header
                    table_header = f"\n\n### Table {i + 1} (Page {page_num + 1})\n"
                    combined_parts.append(table_header + table["markdown"])

                pages.append(
                    {
                        "text": "\n".join(combined_parts),
                        "raw_text": text,
                        "tables": tables,
                        "page_number": page_num + 1,
                        "has_tables": len(tables) > 0,
                        "table_count": len(tables),
                    }
                )

    except Exception as e:
        print(f"Error extracting PDF: {e}")
        # Fallback to basic extraction
        import fitz

        doc = fitz.open(pdf_path)
        for page_num, page in enumerate(doc):
            pages.append(
                {
                    "text": page.get_text(),
                    "raw_text": page.get_text(),
                    "tables": [],
                    "page_number": page_num + 1,
                    "has_tables": False,
                    "table_count": 0,
                }
            )

    return pages


def clean_extracted_text(text: str) -> str:
    """
    Clean extracted text for better chunking.

    Args:
        text: Raw extracted text

    Returns:
        Cleaned text
    """
    # Remove excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)

    # Fix common extraction issues
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # Fix hyphenated line breaks

    return text.strip()
