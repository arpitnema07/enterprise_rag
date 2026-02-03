"""
Query Filter Extraction - Auto-detect metadata filters from user queries.
Extracts document IDs, vehicle models, test types, and other patterns.
"""

import re
from typing import Dict, Any, Tuple


# Patterns for extracting metadata from queries
PATTERNS = {
    # ETR document IDs: ETR_02_24_12, ETR_12_24_104, ETR-01-25-03, etc.
    "doc_id": re.compile(r"ETR[-_]?\d{1,2}[-_]\d{2}[-_]\d{1,4}", re.IGNORECASE),
    # Vehicle models: Pro 3012, Pro 6028XPT, Pro 2110 XPT, etc.
    "vehicle_model": re.compile(r"Pro\s*\d{4}(?:\s*[A-Z]{2,4})?", re.IGNORECASE),
    # Chassis numbers: MC2BHGRC0RB110801
    "chassis_no": re.compile(r"MC[0-9A-Z]{14,17}", re.IGNORECASE),
    # Test types based on common mentions
    "test_type": re.compile(
        r"(brake\s*test|noise\s*test|performance\s*test|emission\s*test|"
        r"endurance\s*test|durability\s*test|gradeability|"
        r"fuel\s*consumption|acceleration|load\s*test)",
        re.IGNORECASE,
    ),
}


def extract_filters_from_query(query: str) -> Tuple[str, Dict[str, Any]]:
    """
    Extract metadata filters from a user query.
    Returns the cleaned query and extracted filters.

    Args:
        query: User's query string

    Returns:
        Tuple of (cleaned_query, filters_dict)
    """
    filters: Dict[str, Any] = {}
    cleaned_query = query

    # Extract document ID (ETR patterns)
    doc_match = PATTERNS["doc_id"].search(query)
    if doc_match:
        doc_id = doc_match.group(0)
        # Normalize: replace dashes with underscores, uppercase
        normalized_doc_id = doc_id.replace("-", "_").upper()
        filters["doc_id"] = normalized_doc_id

    # Extract vehicle model
    model_match = PATTERNS["vehicle_model"].search(query)
    if model_match:
        filters["vehicle_model"] = model_match.group(0).strip()

    # Extract chassis number
    chassis_match = PATTERNS["chassis_no"].search(query)
    if chassis_match:
        filters["chassis_no"] = chassis_match.group(0).upper()

    # Extract test type
    test_match = PATTERNS["test_type"].search(query)
    if test_match:
        filters["test_type"] = test_match.group(0).lower().replace(" ", "_")

    return cleaned_query, filters


def build_enhanced_query(query: str, filters: Dict[str, Any]) -> str:
    """
    Build an enhanced query by appending key metadata terms.
    This helps both dense and sparse search find relevant documents.

    Args:
        query: Original user query
        filters: Extracted filters

    Returns:
        Enhanced query string
    """
    enhancements = []

    if filters.get("doc_id"):
        enhancements.append(f"Document: {filters['doc_id']}")

    if filters.get("vehicle_model"):
        enhancements.append(f"Vehicle: {filters['vehicle_model']}")

    if filters.get("chassis_no"):
        enhancements.append(f"Chassis: {filters['chassis_no']}")

    if enhancements:
        return f"{query} [{' | '.join(enhancements)}]"

    return query


def get_doc_id_filter_conditions(doc_id: str) -> list:
    """
    Generate filter conditions to match a document ID.
    Handles variations in formatting.

    Args:
        doc_id: Normalized document ID

    Returns:
        List of potential matching patterns
    """
    # Generate variations: ETR_02_24_12 -> [ETR_02_24_12, ETR-02-24-12, ETR 02 24 12]
    variations = [
        doc_id,
        doc_id.replace("_", "-"),
        doc_id.replace("_", " "),
        doc_id.lower(),
    ]
    return list(set(variations))
