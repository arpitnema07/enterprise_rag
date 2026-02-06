"""
Agentic Router using LangGraph.
Implements a state machine for intent-based routing.
"""

from typing import TypedDict, List, Dict, Any
from langgraph.graph import StateGraph, END
import time

from .intent_classifier import classify_intent, Intent
from .query_filters import extract_filters_from_query
from .retrieval import hybrid_search
from .embeddings import embed_text
from .sparse_embeddings import embed_sparse
from .generation import _invoke_llm, format_context
from .group_prompts import (
    get_system_prompt,
    get_greeting_response,
    get_out_of_scope_response,
    PROMPT_TYPES,
)
from .realtime_logger import log_sync, LogType, LogLevel
from .tracer import create_trace, log_trace, LatencyInfo, TokenInfo, estimate_tokens


class AgentState(TypedDict):
    """State for the agentic router."""

    # Input
    query: str
    session_id: str
    user_id: int
    group_id: int
    group_ids: List[int]
    prompt_type: str
    history: List[Dict[str, str]]

    # Processing
    intent: str
    intent_confidence: float
    metadata_filters: Dict[str, Any]
    enhanced_query: str
    retrieved_chunks: List[Dict[str, Any]]

    # Output
    response: str
    sources: List[Dict[str, Any]]

    # Timing
    retrieval_ms: float
    generation_ms: float


def classify_intent_node(state: AgentState) -> AgentState:
    """Classify the user's intent."""
    intent, confidence = classify_intent(state["query"], state.get("history", []))

    log_sync(
        LogType.SYSTEM,
        f"Intent classified: {intent.value} (confidence: {confidence:.2f})",
        details={"intent": intent.value, "confidence": confidence},
    )

    return {
        **state,
        "intent": intent.value,
        "intent_confidence": confidence,
    }


def handle_greeting_node(state: AgentState) -> AgentState:
    """Handle greeting intent - no RAG needed."""
    response = get_greeting_response(state["query"])

    log_sync(LogType.RESPONSE, "Greeting response generated")

    return {
        **state,
        "response": response,
        "sources": [],
        "retrieval_ms": 0,
        "generation_ms": 0,
    }


def handle_out_of_scope_node(state: AgentState) -> AgentState:
    """Handle out-of-scope queries."""
    response = get_out_of_scope_response(state["query"])

    log_sync(LogType.RESPONSE, "Out-of-scope response generated")

    return {
        **state,
        "response": response,
        "sources": [],
        "retrieval_ms": 0,
        "generation_ms": 0,
    }


def extract_metadata_node(state: AgentState) -> AgentState:
    """Extract metadata filters from query."""
    enhanced_query, filters = extract_filters_from_query(state["query"])

    log_sync(
        LogType.SYSTEM,
        f"Extracted filters: {filters}" if filters else "No filters extracted",
        details={"filters": filters},
    )

    return {
        **state,
        "metadata_filters": filters or {},
        "enhanced_query": enhanced_query,
    }


def retrieve_node(state: AgentState) -> AgentState:
    """Retrieve relevant chunks from vector store."""
    start = time.time()

    # Get query embeddings
    query = state.get("enhanced_query", state["query"])
    dense_vector = embed_text(query)
    sparse_vector = embed_sparse(query)

    # Determine which groups to search
    group_ids = state.get("group_ids", [])
    if state.get("group_id"):
        group_ids = [state["group_id"]]

    # Hybrid search with filters
    results = hybrid_search(
        dense_vector,
        sparse_vector,
        group_ids,
        filters=state.get("metadata_filters") or None,
    )

    # Format chunks and sources
    chunks = []
    sources = []

    for hit in results:
        chunk_text = hit.payload.get("text", "")
        metadata = hit.payload.get("metadata", {})

        chunks.append(
            {
                "text": chunk_text,
                "metadata": metadata,
                "score": getattr(hit, "score", 0.0),
            }
        )

        sources.append(
            {
                "page_number": metadata.get("page_number"),
                "filename": metadata.get("filename")
                or (
                    metadata.get("file_path", "").split("\\")[-1]
                    if "\\" in metadata.get("file_path", "")
                    else metadata.get("file_path", "").split("/")[-1]
                ),
                "file_path": metadata.get("file_path"),
                "group_id": metadata.get("group_id"),
                "score": getattr(hit, "score", 0.0),
                "text_snippet": chunk_text[:200] + "..."
                if len(chunk_text) > 200
                else chunk_text,
                "full_text": chunk_text,  # Full text for citation modal
            }
        )

    retrieval_ms = (time.time() - start) * 1000

    log_sync(
        LogType.RETRIEVAL,
        f"Retrieved {len(chunks)} chunks",
        duration_ms=retrieval_ms,
        details={
            "chunk_count": len(chunks),
            "top_score": chunks[0]["score"] if chunks else 0,
        },
    )

    return {
        **state,
        "retrieved_chunks": chunks,
        "sources": sources,
        "retrieval_ms": retrieval_ms,
    }


def generate_node(state: AgentState) -> AgentState:
    """Generate response using LLM with group-specific prompt."""
    start = time.time()

    chunks = state.get("retrieved_chunks", [])

    if not chunks:
        response = "I couldn't find relevant information in the uploaded documents for your query."
    else:
        # Format context
        context = format_context(chunks)

        # Format history
        history = ""
        if state.get("history"):
            history = "\n".join(
                [f"{m['role'].upper()}: {m['content']}" for m in state["history"][-5:]]
            )

        # Get prompt based on group's prompt type
        prompt_type = state.get("prompt_type", "general")
        prompt = get_system_prompt(prompt_type, context, state["query"], history)

        # Generate response
        response = _invoke_llm(prompt)

    generation_ms = (time.time() - start) * 1000

    log_sync(
        LogType.GENERATION,
        f"Generated response ({len(response)} chars)",
        duration_ms=generation_ms,
    )

    return {
        **state,
        "response": response,
        "generation_ms": generation_ms,
    }


def route_by_intent(state: AgentState) -> str:
    """Route to appropriate node based on intent."""
    intent = state.get("intent", "document_query")

    if intent == Intent.GREETING.value:
        return "handle_greeting"
    elif intent == Intent.OUT_OF_SCOPE.value:
        return "handle_out_of_scope"
    else:
        # DOCUMENT_QUERY, FOLLOW_UP, CLARIFICATION all need retrieval
        return "extract_metadata"


def build_agentic_graph() -> StateGraph:
    """Build the LangGraph state machine."""

    # Create graph
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("handle_greeting", handle_greeting_node)
    graph.add_node("handle_out_of_scope", handle_out_of_scope_node)
    graph.add_node("extract_metadata", extract_metadata_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)

    # Set entry point
    graph.set_entry_point("classify_intent")

    # Add conditional routing from intent classification
    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "handle_greeting": "handle_greeting",
            "handle_out_of_scope": "handle_out_of_scope",
            "extract_metadata": "extract_metadata",
        },
    )

    # Add edges for document query flow
    graph.add_edge("extract_metadata", "retrieve")
    graph.add_edge("retrieve", "generate")

    # End edges
    graph.add_edge("handle_greeting", END)
    graph.add_edge("handle_out_of_scope", END)
    graph.add_edge("generate", END)

    return graph.compile()


# Global compiled graph
_compiled_graph = None


def get_agentic_graph():
    """Get or create the compiled graph."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_agentic_graph()
    return _compiled_graph


def run_agentic_query(
    query: str,
    group_ids: List[int],
    user_id: int = None,
    session_id: str = None,
    group_id: int = None,
    prompt_type: str = "general",
    history: List[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Run a query through the agentic router.

    Args:
        query: User's query
        group_ids: List of accessible group IDs
        user_id: User ID for logging
        session_id: Session ID for conversation
        group_id: Specific group to search (optional)
        prompt_type: Group's prompt type (technical/compliance/general)
        history: Conversation history

    Returns:
        Dict with response, sources, intent, and timing info
    """
    graph = get_agentic_graph()

    # Prepare initial state
    initial_state: AgentState = {
        "query": query,
        "session_id": session_id or "",
        "user_id": user_id or 0,
        "group_id": group_id or 0,
        "group_ids": group_ids,
        "prompt_type": prompt_type,
        "history": history or [],
        "intent": "",
        "intent_confidence": 0.0,
        "metadata_filters": {},
        "enhanced_query": query,
        "retrieved_chunks": [],
        "response": "",
        "sources": [],
        "retrieval_ms": 0.0,
        "generation_ms": 0.0,
    }

    log_sync(
        LogType.REQUEST,
        f"Agentic query: {query[:100]}...",
        user_id=user_id,
        details={"query": query, "group_ids": group_ids},
    )

    # Run graph
    start = time.time()
    result = graph.invoke(initial_state)
    total_ms = (time.time() - start) * 1000

    log_sync(
        LogType.RESPONSE,
        f"Agentic response complete ({result['intent']})",
        duration_ms=total_ms,
        user_id=user_id,
    )

    # Log trace to traces.jsonl for monitoring
    try:
        # Build trace chunks from retrieved chunks
        trace_chunks = []
        for chunk in result.get("retrieved_chunks", []):
            trace_chunks.append(
                {
                    "text": chunk.get("text", "")[:500] + "..."
                    if len(chunk.get("text", "")) > 500
                    else chunk.get("text", ""),
                    "score": chunk.get("score", 0.0),
                    "page_number": chunk.get("metadata", {}).get("page_number"),
                    "file_path": chunk.get("metadata", {}).get("file_path"),
                    "group_id": chunk.get("metadata", {}).get("group_id"),
                }
            )

        # Create latency info
        latency = LatencyInfo(
            retrieval_ms=result["retrieval_ms"],
            generation_ms=result["generation_ms"],
            total_ms=total_ms,
        )

        # Estimate tokens
        context_text = " ".join(
            [c.get("text", "") for c in result.get("retrieved_chunks", [])]
        )
        prompt_text = query + context_text
        tokens = TokenInfo(
            prompt=estimate_tokens(prompt_text),
            completion=estimate_tokens(result["response"]),
            total=estimate_tokens(prompt_text) + estimate_tokens(result["response"]),
        )

        # Create and log trace
        trace = create_trace(
            query=query,
            response=result["response"],
            chunks=trace_chunks,
            latency=latency,
            tokens=tokens,
            user_id=user_id,
            metadata={
                "intent": result["intent"],
                "session_id": session_id,
                "group_ids": group_ids,
                "prompt_type": prompt_type,
            },
        )
        log_trace(trace)
    except Exception as e:
        print(f"Warning: Failed to log trace: {e}")

    return {
        "answer": result["response"],
        "sources": result["sources"],
        "intent": result["intent"],
        "session_id": session_id,
        "latency": {
            "retrieval_ms": result["retrieval_ms"],
            "generation_ms": result["generation_ms"],
            "total_ms": total_ms,
        },
    }
