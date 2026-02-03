"""
Metadata Extraction module for vehicle reports.
Uses regex patterns and spaCy NER for structured metadata extraction.
"""

import re
from typing import Dict

# Lazy load spacy to avoid startup overhead
_nlp = None


def _get_nlp():
    """Get or initialize the spaCy NLP model."""
    global _nlp
    if _nlp is None:
        import spacy

        try:
            _nlp = spacy.load("en_core_web_sm")
        except OSError:
            # Model not installed, download it
            import subprocess

            subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
            _nlp = spacy.load("en_core_web_sm")
    return _nlp


# Regex patterns for vehicle report metadata
PATTERNS = {
    "vehicle_model": r"Model:\s*([A-Za-z0-9\s\-]+?)(?:\n|$)",
    "chassis_no": r"Chassis\s*(?:No\.?|Number)?:?\s*([A-Z0-9]+)",
    "test_date": r"Date:\s*(\d{2}[.\-/]\d{2}[.\-/]\d{4})",
    "report_no": r"(?:Test\s*Report\s*No\.?|ETR):?\s*(ETR[_\-]?\d+[_\-]?\d*[_\-]?\d*)",
    "registration_no": r"(?:Reg(?:istration)?\.?\s*No\.?|Regd\.?\s*No\.?):?\s*([A-Z]{2}\d{2}[A-Z]{1,3}\d{4})",
    "engine_model": r"Engine\s*(?:Model|Type):?\s*([A-Za-z0-9\-\s]+?)(?:\n|$)",
    "gvw": r"(?:GVW|Gross\s*Vehicle\s*Weight):?\s*(\d+(?:\.\d+)?)\s*(?:kg|Kg|KG)?",
    "power": r"(?:Power|Max\.?\s*Power):?\s*(\d+(?:\.\d+)?)\s*(?:kW|KW|hp|HP)",
}

# Test types commonly found in vehicle reports
TEST_TYPES = [
    "gradability",
    "brake",
    "noise",
    "cooling",
    "weighment",
    "agility",
    "articulation",
    "steering",
    "suspension",
    "emission",
    "durability",
    "performance",
    "safety",
]

# Vehicle-specific keywords
VEHICLE_TERMS = [
    "CNG",
    "BSVI",
    "BSIV",
    "kW",
    "torque",
    "power",
    "GVW",
    "diesel",
    "petrol",
    "hybrid",
    "EV",
    "electric",
]


def extract_metadata(text: str, doc_name: str = "") -> Dict:
    """
    Extract structured metadata from vehicle report text.

    Args:
        text: Document or chunk text
        doc_name: Document identifier

    Returns:
        Dict with extracted metadata fields
    """
    metadata = {
        "doc_id": doc_name,
        "keywords": [],
        "vehicle_model": None,
        "test_type": None,
        "chassis_no": None,
        "test_date": None,
        "report_no": None,
        "registration_no": None,
        "engine_model": None,
        "gvw": None,
        "power": None,
        "compliance_status": [],
        "standards": [],
        "test_parameters": [],
    }

    # Extract using regex patterns
    for key, pattern in PATTERNS.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()

    # Extract IS/AIS standards
    standards_pattern = r"\b(IS|AIS)[\s:\-]*\d+(?:[\:\-]\d+)*\b"
    standards_matches = re.findall(standards_pattern, text, re.IGNORECASE)
    if standards_matches:
        # Get full matches
        full_standards = re.findall(
            r"\b(?:IS|AIS)[\s:\-]*\d+(?:[\:\-]\d+)*\b", text, re.IGNORECASE
        )
        metadata["standards"] = list(set(full_standards))

    # Extract test types from text
    text_lower = text.lower()
    for test in TEST_TYPES:
        if test.lower() in text_lower:
            metadata["test_parameters"].append(test)

    # Set primary test type if found
    if metadata["test_parameters"]:
        metadata["test_type"] = metadata["test_parameters"][0]

    # Compliance status extraction
    if re.search(r"\b(?:meeting|pass(?:ed)?|compliant)\b", text, re.IGNORECASE):
        metadata["compliance_status"].append("pass")
    if re.search(
        r"\b(?:not\s+meeting|fail(?:ed)?|non[\-\s]?compliant)\b", text, re.IGNORECASE
    ):
        metadata["compliance_status"].append("fail")

    # Add vehicle terms as keywords
    for term in VEHICLE_TERMS:
        if term in text:
            metadata["keywords"].append(term)

    # NER for product/organization entities (limit text for performance)
    try:
        nlp = _get_nlp()
        doc = nlp(text[:5000])
        for ent in doc.ents:
            if ent.label_ in ["PRODUCT", "ORG", "GPE"]:
                if ent.text not in metadata["keywords"]:
                    metadata["keywords"].append(ent.text)
    except Exception:
        # Skip NER if spacy fails
        pass

    # Deduplicate keywords
    metadata["keywords"] = list(set(metadata["keywords"]))

    return metadata


def merge_metadata(doc_metadata: Dict, chunk_metadata: Dict) -> Dict:
    """
    Merge document-level and chunk-level metadata.
    Chunk-level values override document-level for specific fields.

    Args:
        doc_metadata: Document-level extracted metadata
        chunk_metadata: Chunk-level extracted metadata

    Returns:
        Merged metadata dict
    """
    merged = doc_metadata.copy()

    # Merge list fields
    for field in ["keywords", "test_parameters", "compliance_status", "standards"]:
        merged[field] = list(
            set(doc_metadata.get(field, []) + chunk_metadata.get(field, []))
        )

    # Override with chunk-level if available
    for field in ["test_type", "vehicle_model", "chassis_no"]:
        if chunk_metadata.get(field):
            merged[field] = chunk_metadata[field]

    return merged
