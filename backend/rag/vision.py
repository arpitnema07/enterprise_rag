"""
Vision module — Ollama vision API wrapper for OCR and image captioning.
Uses gemma3:27b for both OCR (scanned/CID pages) and image description.
"""

import os
import logging
import requests

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("VISION_MODEL", "gemma3:27b")

OCR_PROMPT = (
    "You are a precise OCR engine. Your job is to extract every single word of text "
    "visible on this document page. Output the text exactly as it appears, character by character. "
    "Include: page headers, chapter titles, paragraph text, numbered lists, bold/italic text, "
    "captions, footnotes, page numbers, and footer text. "
    "Do NOT describe images — just output [IMAGE] where images appear. "
    "Do NOT paraphrase or summarize. Transcribe verbatim. "
    "Pay close attention to small text, technical terms, software names, and menu paths."
)

IMAGE_CAPTION_PROMPT = (
    "Describe this image in detail for use in a document search system. "
    "Include: what type of visual this is (diagram, chart, photo, schematic, etc.), "
    "what it shows, any labels or annotations visible, key data points or values, "
    "and the overall purpose of the image. Be factual — do not guess or invent details."
)


def _call_vision(image_b64: str, prompt: str, timeout: int = 600) -> str:
    """Send image + prompt to Ollama vision API."""
    try:
        response = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": VISION_MODEL,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 4096},
            },
            timeout=timeout,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()
    except requests.exceptions.Timeout:
        logger.warning(f"Vision API timed out after {timeout}s")
        return ""
    except Exception as e:
        logger.error(f"Vision API error: {e}")
        return ""


def ocr_page_image(image_b64: str) -> str:
    """
    Extract text from a page image using vision model OCR.

    Args:
        image_b64: Base64-encoded PNG image of the page

    Returns:
        Extracted text, or empty string on failure
    """
    logger.info(f"Running vision OCR with {VISION_MODEL}")
    text = _call_vision(image_b64, OCR_PROMPT)

    if text:
        logger.info(f"Vision OCR extracted {len(text)} chars")
    else:
        logger.warning("Vision OCR returned empty result")

    return text


def caption_image(image_b64: str) -> str:
    """
    Generate a text description of an image for RAG indexing.

    Args:
        image_b64: Base64-encoded PNG/JPEG image

    Returns:
        Text description of the image
    """
    logger.info(f"Generating image caption with {VISION_MODEL}")
    caption = _call_vision(image_b64, IMAGE_CAPTION_PROMPT, timeout=300)

    if caption:
        logger.info(f"Caption generated: {len(caption)} chars")
    else:
        logger.warning("Image captioning returned empty result")

    return caption


def is_vision_available() -> bool:
    """Check if the vision model is available on Ollama."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        available = VISION_MODEL in models
        if not available:
            logger.warning(
                f"Vision model '{VISION_MODEL}' not found. Available: {models}"
            )
        return available
    except Exception as e:
        logger.error(f"Cannot reach Ollama: {e}")
        return False
