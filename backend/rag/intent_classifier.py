"""
Intent Classification module for the agentic router.
Classifies user queries into intents for routing.
"""

from enum import Enum
from typing import Tuple, Optional
import re


class Intent(str, Enum):
    """Possible user intents."""

    GREETING = "greeting"
    DOCUMENT_QUERY = "document_query"
    FOLLOW_UP = "follow_up"
    CLARIFICATION = "clarification"
    OUT_OF_SCOPE = "out_of_scope"


# Greeting patterns
GREETING_PATTERNS = [
    r"^(hi|hello|hey|good\s*(morning|afternoon|evening)|greetings)[\s!.,]*$",
    r"^(how\s+are\s+you|what'?s\s+up|howdy)[\s!?,]*$",
    r"^(thanks?|thank\s+you|bye|goodbye|see\s+you)[\s!.,]*$",
]

# Follow-up indicators
FOLLOW_UP_PATTERNS = [
    r"^(what|which|how|where|when|why|who)\s+(about|is|are|was|were)\s+(it|this|that|these|those)",
    r"^(tell\s+me\s+more|more\s+details|explain|elaborate)",
    r"^(and|also|additionally|furthermore)",
    r"^(can\s+you|could\s+you)\s+(also|explain|show)",
]

# Out of scope patterns
OUT_OF_SCOPE_PATTERNS = [
    r"(weather|news|joke|song|music|movie|game|sport)",
    r"(write\s+code|python|javascript|programming)",
    r"(recipe|cook|food|restaurant)",
]


def classify_intent_rule_based(
    query: str, has_history: bool = False
) -> Tuple[Intent, float]:
    """
    Rule-based intent classification (fast path).

    Args:
        query: User query
        has_history: Whether there's conversation history

    Returns:
        Tuple of (Intent, confidence)
    """
    query_lower = query.lower().strip()

    # Check greetings
    for pattern in GREETING_PATTERNS:
        if re.match(pattern, query_lower, re.IGNORECASE):
            return Intent.GREETING, 0.95

    # Check follow-ups (only if there's history)
    if has_history:
        for pattern in FOLLOW_UP_PATTERNS:
            if re.match(pattern, query_lower, re.IGNORECASE):
                return Intent.FOLLOW_UP, 0.85

        # Short queries with history are likely follow-ups
        if len(query_lower.split()) <= 3:
            return Intent.FOLLOW_UP, 0.7

    # Check out of scope
    for pattern in OUT_OF_SCOPE_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return Intent.OUT_OF_SCOPE, 0.8

    # Default to document query
    return Intent.DOCUMENT_QUERY, 0.9


def classify_intent_llm(query: str, history: list = None) -> Tuple[Intent, float]:
    """
    LLM-based intent classification for complex cases.

    Args:
        query: User query
        history: Conversation history

    Returns:
        Tuple of (Intent, confidence)
    """
    from .generation import _invoke_llm

    history_context = ""
    if history:
        history_context = "\n".join(
            [f"{m['role']}: {m['content']}" for m in history[-3:]]
        )

    prompt = f"""Classify the user's intent into exactly one of these categories:
- GREETING: Simple greetings, thanks, or farewells
- DOCUMENT_QUERY: Questions about vehicle documents, test reports, specifications
- FOLLOW_UP: Continuation or clarification of previous conversation
- OUT_OF_SCOPE: Questions unrelated to vehicle documentation

Conversation history:
{history_context if history_context else "(No history)"}

User message: {query}

Respond with ONLY the category name (e.g., DOCUMENT_QUERY):"""

    try:
        response = _invoke_llm(prompt).strip().upper()

        # Parse response
        for intent in Intent:
            if intent.value.upper() in response or intent.name in response:
                return intent, 0.9

        return Intent.DOCUMENT_QUERY, 0.6

    except Exception:
        # Fallback to rule-based
        return classify_intent_rule_based(query, bool(history))


def classify_intent(
    query: str, history: list = None, use_llm: bool = False
) -> Tuple[Intent, float]:
    """
    Main intent classification function.
    Uses rule-based for speed, LLM for complex cases.

    Args:
        query: User query
        history: Optional conversation history
        use_llm: Whether to use LLM classification

    Returns:
        Tuple of (Intent, confidence)
    """
    # Fast path with rules
    intent, confidence = classify_intent_rule_based(query, bool(history))

    # Use LLM if confidence is low or explicitly requested
    if use_llm or confidence < 0.75:
        intent, confidence = classify_intent_llm(query, history)

    return intent, confidence
