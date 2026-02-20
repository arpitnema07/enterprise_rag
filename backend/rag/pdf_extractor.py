"""
Enhanced PDF Extraction with Table Detection + Hybrid OCR.

Strategy:
1. pdfplumber for digital PDFs (fast, 100% accurate)
2. gemma3:27b vision OCR fallback for CID-encoded / scanned pages
3. Embedded image extraction for vision captioning
"""

import base64
import logging
import re
from typing import List, Dict, Any

import fitz  # PyMuPDF
import pdfplumber

logger = logging.getLogger(__name__)

# Minimum meaningful text length — below this, page is likely scanned
MIN_TEXT_LENGTH = 50

# CID pattern — indicates embedded fonts that pdfplumber can't decode
CID_PATTERN = re.compile(r"\(cid:\d+\)")


def is_page_needs_ocr(text: str) -> bool:
    """
    Detect if pdfplumber output is unusable (CID-encoded or near-empty).

    Args:
        text: Raw text from pdfplumber

    Returns:
        True if page needs vision OCR fallback
    """
    if not text or len(text.strip()) < MIN_TEXT_LENGTH:
        return True

    # Check for CID-encoded content (font not embedded properly)
    cid_matches = CID_PATTERN.findall(text)
    if len(cid_matches) > 5:
        # More than 5 CID references = mostly unreadable
        real_text = CID_PATTERN.sub("", text).strip()
        if len(real_text) < MIN_TEXT_LENGTH:
            return True

    return False


def page_to_base64(pdf_path: str, page_num: int, dpi: int = 150) -> str:
    """
    Render a PDF page to a base64-encoded PNG image.

    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        dpi: Resolution for rendering (150 is optimal for gemma3:27b)

    Returns:
        Base64-encoded PNG string
    """
    doc = fitz.open(pdf_path)
    page = doc[page_num]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    doc.close()
    return base64.b64encode(img_bytes).decode("utf-8")


def extract_embedded_images(
    pdf_path: str, page_num: int, min_size: int = 100
) -> List[Dict[str, Any]]:
    """
    Extract embedded images from a PDF page.

    Args:
        pdf_path: Path to PDF file
        page_num: Page number (0-indexed)
        min_size: Minimum width/height in pixels to include

    Returns:
        List of dicts with 'image_b64', 'width', 'height', 'image_index'
    """
    images = []

    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        image_list = page.get_images(full=True)

        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue

                width = base_image.get("width", 0)
                height = base_image.get("height", 0)

                # Skip tiny images (icons, bullets, etc.)
                if width < min_size or height < min_size:
                    continue

                img_bytes = base_image["image"]
                img_b64 = base64.b64encode(img_bytes).decode("utf-8")

                images.append(
                    {
                        "image_b64": img_b64,
                        "width": width,
                        "height": height,
                        "image_index": img_idx,
                        "ext": base_image.get("ext", "png"),
                    }
                )
            except Exception as e:
                logger.debug(f"Could not extract image {img_idx}: {e}")

        doc.close()

    except Exception as e:
        logger.warning(f"Image extraction failed for page {page_num}: {e}")

    return images


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
        logger.warning(f"Table extraction failed: {e}")

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
        tables = extract_tables_as_markdown(page)

        table_bboxes = []
        try:
            for table in page.find_tables():
                table_bboxes.append(table.bbox)
        except Exception:
            pass

        full_text = page.extract_text() or ""

        combined_parts = []
        if full_text.strip():
            combined_parts.append(full_text)

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
    Extract all pages from PDF with hybrid OCR.

    Strategy per page:
    1. Try pdfplumber → if text is good (not CID, not empty) → use it
    2. Otherwise → render page image → send to gemma3:27b vision OCR
    3. Always extract embedded images for later captioning

    Args:
        pdf_path: Path to PDF file

    Returns:
        List of page dicts with 'text', 'tables', 'page_number', 'has_tables',
        'extraction_method', 'images'
    """
    pages = []
    ocr_page_count = 0

    # Lazy import vision module (only loaded if needed)
    vision_module = None

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                # Step 1: Try pdfplumber
                tables = extract_tables_as_markdown(page)
                raw_text = page.extract_text() or ""

                extraction_method = "pdfplumber"

                # Step 2: Check if OCR fallback is needed
                if is_page_needs_ocr(raw_text):
                    logger.info(
                        f"Page {page_num + 1}: pdfplumber unusable "
                        f"({len(raw_text)} chars, CID={bool(CID_PATTERN.findall(raw_text))})"
                        f" — falling back to vision OCR"
                    )

                    # Lazy load vision module
                    if vision_module is None:
                        try:
                            from backend.rag.vision import ocr_page_image

                            vision_module = ocr_page_image
                        except ImportError:
                            logger.warning(
                                "Vision module not available, using empty text"
                            )

                            def _noop_ocr(x: str) -> str:
                                return ""

                            vision_module = _noop_ocr

                    # Render page and run vision OCR
                    page_image_b64 = page_to_base64(pdf_path, page_num)
                    raw_text = vision_module(page_image_b64)
                    extraction_method = "vision_ocr"
                    ocr_page_count += 1
                    tables = []  # Can't extract tables from vision OCR

                # Build combined text
                combined_parts = [raw_text] if raw_text.strip() else []

                for i, table in enumerate(tables):
                    table_header = f"\n\n### Table {i + 1} (Page {page_num + 1})\n"
                    combined_parts.append(table_header + table["markdown"])

                # Step 3: Extract embedded images
                embedded_images = extract_embedded_images(pdf_path, page_num)

                pages.append(
                    {
                        "text": "\n".join(combined_parts),
                        "raw_text": raw_text,
                        "tables": tables,
                        "page_number": page_num + 1,
                        "has_tables": len(tables) > 0,
                        "table_count": len(tables),
                        "extraction_method": extraction_method,
                        "images": embedded_images,
                        "image_count": len(embedded_images),
                    }
                )

    except Exception as e:
        logger.error(f"Error extracting PDF with pdfplumber: {e}")
        # Fallback to basic fitz extraction
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
                    "extraction_method": "fitz_fallback",
                    "images": [],
                    "image_count": 0,
                }
            )

    if ocr_page_count > 0:
        logger.info(f"Vision OCR used on {ocr_page_count}/{len(pages)} pages")

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
