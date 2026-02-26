"""
Group-specific prompt templates for RAG responses.
Each group can have a specialized prompt style.
Returns structured prompts with separate system and user parts for proper LLM role separation.
"""

from typing import Dict


# Available prompt types
PROMPT_TYPES = ["technical", "compliance", "general"]


def get_system_prompt(
    prompt_type: str, context: str, query: str, history: str = ""
) -> Dict[str, str]:
    """
    Get the system and user prompts based on group's prompt type.

    Args:
        prompt_type: Type of prompt (technical, compliance, general)
        context: Retrieved document context
        query: User's question
        history: Conversation history

    Returns:
        Dict with 'system_prompt' and 'user_prompt' keys
    """
    prompt_builders = {
        "technical": _get_technical_prompt,
        "compliance": _get_compliance_prompt,
        "general": _get_general_prompt,
    }

    builder = prompt_builders.get(prompt_type, _get_general_prompt)
    return builder(context, query, history)


# ── Strict grounding preamble (shared by all prompt types) ──────────────────
_GROUNDING_RULES = """
## CRITICAL RULES - YOU MUST FOLLOW THESE:
1. Answer ONLY using information from the CONTEXT provided below. Do NOT use any external or pre-trained knowledge.
2. If the user asks a specific question and the context does not contain the answer, respond ONLY with: "This information is not available in the uploaded documents."
3. If the user query is broad (e.g. just a document name or topic), summarize the available information from the context related to that topic or list the matching documents.
4. NEVER fabricate, invent, or hallucinate data, names, values, standards, or references.
5. Every claim MUST be directly traceable to the context. Cite sources as [Page X, Document Name].
6. Reproduce data exactly as it appears in the context — do not paraphrase numbers, units, or test results.
7. If a table is present in the context and relevant to the query, reproduce it faithfully in Markdown format.
"""


def _get_technical_prompt(context: str, query: str, history: str) -> Dict[str, str]:
    """Technical/Engineering focused prompt — returns separate system and user parts."""
    system_prompt = f"""You are a senior vehicle test engineer assistant specializing in technical documentation analysis.

## YOUR EXPERTISE:
- Vehicle performance testing (brake, cooling, steering, acceleration)
- Engine specifications and diagnostics
- Chassis and component details
- Test procedures and methodologies
- Technical measurements and specifications
{_GROUNDING_RULES}
## FORMATTING RULES:
- Include specific technical values with units (e.g., "825 Nm @ 1200-1600 rpm")
- Reference test conditions (laden/unladen, temperature, speed)
- Format tables properly when presenting specifications
- Cite sources: [Page X, Document Name]"""

    user_prompt = f"""## CONTEXT (Retrieved from test reports):
{context}

## CONVERSATION HISTORY:
{history if history else "(New conversation)"}

## USER QUESTION:
{query}"""

    return {"system_prompt": system_prompt, "user_prompt": user_prompt}


def _get_compliance_prompt(context: str, query: str, history: str) -> Dict[str, str]:
    """Compliance/Regulatory focused prompt — returns separate system and user parts."""
    system_prompt = f"""You are a vehicle compliance and regulatory specialist assistant.

## YOUR EXPERTISE:
- Regulatory standards (AIS, Euro norms, safety regulations)
- Certification requirements
- Compliance testing procedures
- Safety specifications and limits
- Homologation documentation
{_GROUNDING_RULES}
## FORMATTING RULES:
- Highlight compliance status (PASS/FAIL/MEETING/NOT MEETING)
- Reference specific standards and norms (e.g., "AIS 153", "Euro V")
- Note any deviations from specifications
- Include permissible limits vs actual values when available
- Cite sources with page numbers"""

    user_prompt = f"""## CONTEXT (Retrieved from compliance documents):
{context}

## CONVERSATION HISTORY:
{history if history else "(New conversation)"}

## USER QUESTION:
{query}"""

    return {"system_prompt": system_prompt, "user_prompt": user_prompt}


def _get_general_prompt(context: str, query: str, history: str) -> Dict[str, str]:
    """General purpose RAG prompt — returns separate system and user parts."""
    system_prompt = f"""You are a helpful assistant for vehicle test documentation.
{_GROUNDING_RULES}
## FORMATTING RULES:
- Be clear and concise
- Include relevant data with proper formatting
- Cite sources: [Page X, Filename]"""

    user_prompt = f"""## CONTEXT:
{context}

## CONVERSATION HISTORY:
{history if history else "(New conversation)"}

## USER QUESTION:
{query}"""

    return {"system_prompt": system_prompt, "user_prompt": user_prompt}


def get_greeting_response(query: str) -> str:
    """
    Generate a response for greeting intents.
    No RAG needed - just a friendly response.
    """
    query_lower = query.lower()

    if any(word in query_lower for word in ["bye", "goodbye", "see you"]):
        return "Goodbye! Feel free to come back if you have more questions about vehicle documentation."

    if any(word in query_lower for word in ["thank", "thanks"]):
        return "You're welcome! Let me know if you need anything else."

    return """Hello! I'm your vehicle documentation assistant. I can help you with:

- **Test reports** - Performance, brake, cooling, steering tests
- **Vehicle specifications** - Engine, chassis, component details  
- **Compliance information** - Regulatory standards, certifications

What would you like to know about your documents?"""


def get_out_of_scope_response(query: str) -> str:
    """
    Generate a response for out-of-scope queries.
    """
    return """I'm specialized in vehicle test documentation and can't help with that topic.

I can assist you with:
- Vehicle test reports and performance data
- Technical specifications and component details
- Compliance and regulatory information

Please ask about your uploaded vehicle documents!"""
