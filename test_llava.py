"""
Compare pdfplumber vs gemma3:27b on a NORMAL digital PDF (non-CID).
Uses E449 Water Cooling Jacket CFD report — a clean engineering PDF.
"""

import os
import base64
import time
import requests
import fitz
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

OLLAMA = os.getenv("OLLAMA_BASE_URL")
MODEL = "gemma3:27b"
PDF = "uploaded_files/E449-BSVI-WCJ-R-00-01-Water Cooling Jacket CFD Simulation.pdf"

OCR_PROMPT = (
    "You are a precise OCR engine. Your job is to extract every single word of text "
    "visible on this document page. Output the text exactly as it appears, character by character. "
    "Include: page headers, chapter titles, paragraph text, numbered lists, bold/italic text, "
    "captions, footnotes, page numbers, and footer text. "
    "Do NOT describe images — just output [IMAGE] where images appear. "
    "Do NOT paraphrase or summarize. Transcribe verbatim. "
    "Pay close attention to small text, technical terms, software names, and menu paths."
)


def get_image(page_num, dpi=150):
    doc = fitz.open(PDF)
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
    b64 = base64.b64encode(pix.tobytes("png")).decode()
    doc.close()
    return b64


def get_plumber_text(page_num):
    with pdfplumber.open(PDF) as pdf:
        if page_num < len(pdf.pages):
            return pdf.pages[page_num].extract_text() or ""
    return ""


def ask_gemma(image_b64):
    t0 = time.time()
    r = requests.post(
        f"{OLLAMA}/api/generate",
        json={
            "model": MODEL,
            "prompt": OCR_PROMPT,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.0, "num_predict": 4096},
        },
        timeout=900,
    )
    r.raise_for_status()
    return r.json().get("response", ""), time.time() - t0


def word_overlap(text_a, text_b):
    """Calculate word-level overlap between two texts."""
    words_a = set(text_a.lower().split())
    words_b = set(text_b.lower().split())
    if not words_a or not words_b:
        return 0, 0, 0
    common = words_a & words_b
    precision = (
        len(common) / len(words_b) * 100 if words_b else 0
    )  # how much of gemma is real
    recall = (
        len(common) / len(words_a) * 100 if words_a else 0
    )  # how much of plumber gemma captured
    return precision, recall, len(common)


def main():
    if not os.path.exists(PDF):
        print(f"ERROR: {PDF} not found")
        return

    doc = fitz.open(PDF)
    total_pages = len(doc)
    doc.close()
    print(f"PDF: {os.path.basename(PDF)} ({total_pages} pages)")
    print(f"Model: {MODEL}\n")

    # Test pages 0, 1, 2 (cover page, content page, page with possible diagrams)
    test_pages = [0, 1, min(3, total_pages - 1)]

    for page_num in test_pages:
        print(f"\n{'=' * 70}")
        print(f"PAGE {page_num + 1}")
        print(f"{'=' * 70}")

        # pdfplumber
        t0 = time.time()
        plumber_text = get_plumber_text(page_num)
        plumber_time = time.time() - t0

        print(f"\n--- PDFPLUMBER ({plumber_time:.2f}s, {len(plumber_text)} chars) ---")
        print(plumber_text[:800])

        # Check if CID-encoded
        is_cid = "(cid:" in plumber_text
        print(f"\nCID encoded: {is_cid}")

        # gemma3:27b
        img = get_image(page_num)
        gemma_text, gemma_time = ask_gemma(img)

        print(f"\n--- GEMMA3:27B ({gemma_time:.1f}s, {len(gemma_text)} chars) ---")
        print(gemma_text[:800])

        # Word-level comparison
        if plumber_text and not is_cid:
            precision, recall, common = word_overlap(plumber_text, gemma_text)
            print(f"\n--- COMPARISON (pdfplumber as ground truth) ---")
            print(f"Plumber words: {len(plumber_text.split())}")
            print(f"Gemma words:   {len(gemma_text.split())}")
            print(f"Common words:  {common}")
            print(
                f"Precision:     {precision:.0f}% (of Gemma output, how much is real)"
            )
            print(
                f"Recall:        {recall:.0f}% (of Plumber text, how much Gemma captured)"
            )
            print(f"Speed ratio:   {gemma_time / max(plumber_time, 0.001):.0f}x slower")
        else:
            print(f"\n(CID page — pdfplumber unusable, Gemma is only option)")

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
