"""
Generation module for LLM answer generation.
Supports Ollama and NVIDIA API endpoints with versioned prompts.
"""

import os
import requests
from typing import List, Dict, Any, Optional
from langchain_community.llms import Ollama
from .prompt_manager import prompt_manager
from .conversation import format_history

# Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "nvidia")  # "ollama" or "nvidia"

# Ollama Configuration
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "")

# NVIDIA Configuration
NVIDIA_API_KEY = os.getenv(
    "NVIDIA_API_KEY",
    "",
)
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "moonshotai/kimi-k2-instruct")
NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"

# Initialize Ollama LLM
_ollama_llm = Ollama(model=OLLAMA_MODEL, base_url=OLLAMA_BASE_URL)


def _call_nvidia_api(
    prompt: str, max_retries: int = 3, initial_delay: float = 1.0
) -> str:
    """
    Call NVIDIA API for text generation with retry logic.

    Args:
        prompt: The full prompt to send
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before retry (default: 1.0)

    Returns:
        Generated text response
    """
    import time

    if not NVIDIA_API_KEY:
        raise ValueError("NVIDIA_API_KEY environment variable not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {NVIDIA_API_KEY}",
    }

    payload = {
        "model": NVIDIA_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "temperature": 0.2,
        "max_tokens": 2048,
    }

    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                NVIDIA_API_URL,
                headers=headers,
                json=payload,
                timeout=180,  # Increased timeout for large responses
                verify=False,  # For corporate proxies - disable in production
            )
            response.raise_for_status()

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_exception = e
            if attempt < max_retries:
                delay = initial_delay * (2**attempt)  # Exponential backoff
                print(
                    f"NVIDIA API connection error (attempt {attempt + 1}/{max_retries + 1}): {e}"
                )
                print(f"Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print(f"NVIDIA API error after {max_retries + 1} attempts: {e}")
                raise
        except requests.exceptions.RequestException as e:
            # For non-connection errors (like HTTP errors), don't retry
            print(f"NVIDIA API error: {e}")
            raise

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception


def _invoke_llm(prompt: str) -> str:
    """
    Invoke LLM using configured provider.

    Args:
        prompt: The prompt to send

    Returns:
        Generated text response
    """
    if LLM_PROVIDER == "nvidia":
        return _call_nvidia_api(prompt)
    else:
        return _ollama_llm.invoke(prompt)


def format_context(context_chunks: List[Dict[str, Any]]) -> str:
    """
    Format context chunks into a string for the prompt.

    Args:
        context_chunks: List of chunks with 'text' and 'metadata'

    Returns:
        Formatted context string with source citations
    """
    context = ""
    for chunk in context_chunks:
        metadata = chunk.get("metadata", {})
        page_num = metadata.get("page_number", "?")
        filename = metadata.get("filename", "Unknown")
        section = metadata.get("section", "")
        text = chunk.get("text", "")

        source_info = f"[{filename}, Page {page_num}"
        if section:
            source_info += f", {section}"
        source_info += "]"

        context += f"Source {source_info}:\n{text}\n\n"

    return context


def generate_answer(query: str, context_chunks: List[Dict[str, Any]]) -> str:
    """
    Generate an answer based on query and retrieved context.

    Args:
        query: User question
        context_chunks: List of retrieved chunks with 'text' and 'metadata'

    Returns:
        Generated answer string
    """
    # Build context string
    context = format_context(context_chunks)

    prompt = f"""You are an expert assistant for vehicle test engineers. Your job is to answer questions using ONLY the provided context.

## INSTRUCTIONS:
1. **Answer directly** - Give the actual data/answer, not just where it's found
2. **Include tables** - If the context contains tables relevant to the question, reproduce them in your answer using proper Markdown table format
3. **Format properly** - Use Markdown: tables with |, headers with ##, lists with -
4. **Cite sources** - After each piece of information, add a citation like [Page X, Document Y]
5. **Be complete** - Include all relevant data from the context
6. If no relevant data exists, say: "No data found in uploaded documents."

## CONTEXT (Retrieved from documents):
{context}

## USER QUESTION:
{query}

## YOUR ANSWER (with tables in Markdown format and citations):
"""

    return _invoke_llm(prompt)


def generate_answer_with_history(
    query: str,
    context_chunks: List[Dict[str, Any]],
    history: Optional[List[Dict[str, str]]] = None,
    prompt_version: str = "latest",
) -> str:
    """
    Generate answer using versioned prompts and conversation history.

    Args:
        query: User question
        context_chunks: List of retrieved chunks
        history: Optional conversation history
        prompt_version: Prompt version to use (e.g., 'v1', 'latest')

    Returns:
        Generated answer string
    """
    # Format context
    context = format_context(context_chunks)

    # Format history
    history_text = ""
    if history:
        history_text = format_history(history)

    # Try to use versioned prompt, fall back to inline if not available
    try:
        system_prompt = prompt_manager.render_prompt(
            prompt_name="system_prompt",
            version=prompt_version,
            context=context,
            history=history_text,
            query=query,
        )
    except FileNotFoundError:
        # Fall back to inline prompt
        system_prompt = f"""You are an expert assistant for vehicle test engineers. Answer questions using ONLY the provided context.

## INSTRUCTIONS:
1. **Answer directly** - Give the actual data/answer, not just the location
2. **Include tables** - Reproduce relevant tables in proper Markdown format (| col1 | col2 |)
3. **Format properly** - Use Markdown formatting for clarity
4. **Cite sources** - Add citations like [Page X, Filename] after each fact
5. **Be complete** - Include all relevant data from the context
6. If no relevant data exists, say: "No data found in uploaded documents."

## CONTEXT (Retrieved from documents):
{context}

## CONVERSATION HISTORY:
{history_text}

## USER QUESTION:
{query}

## YOUR ANSWER (with tables in Markdown and citations):
"""

    return _invoke_llm(system_prompt)


def generate_with_system_prompt(query: str, context: str, system_prompt: str) -> str:
    """
    Generate answer with custom system prompt.

    Args:
        query: User question
        context: Context string
        system_prompt: Custom system instructions

    Returns:
        Generated answer string
    """
    prompt = f"""
{system_prompt}

Context:
{context}

Question: {query}
"""
    return _invoke_llm(prompt)


def get_current_provider() -> Dict[str, str]:
    """
    Get information about the current LLM provider.

    Returns:
        Dict with provider info
    """
    return {
        "provider": LLM_PROVIDER,
        "model": NVIDIA_MODEL if LLM_PROVIDER == "nvidia" else OLLAMA_MODEL,
        "endpoint": NVIDIA_API_URL if LLM_PROVIDER == "nvidia" else OLLAMA_BASE_URL,
    }
