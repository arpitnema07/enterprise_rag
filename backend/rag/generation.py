"""
Generation module for LLM answer generation.
Supports Ollama and NVIDIA API endpoints with versioned prompts.
"""

import os
import logging
import requests
from typing import List, Dict, Any, Optional
from langchain_community.llms import Ollama
from .prompt_manager import prompt_manager
from .conversation import format_history

logger = logging.getLogger(__name__)

# Mutable runtime config
_config_cache = None
_ollama_llm_cache = None

NVIDIA_API_URL = "https://integrate.api.nvidia.com/v1/chat/completions"


def _get_config():
    global _config_cache
    if _config_cache is None:
        _config_cache = {
            "provider": os.getenv("LLM_PROVIDER", "nvidia"),
            "ollama_model": os.getenv("OLLAMA_MODEL", ""),
            "ollama_base_url": os.getenv("OLLAMA_BASE_URL", ""),
            "nvidia_api_key": os.getenv("NVIDIA_API_KEY", ""),
            "nvidia_model": os.getenv("NVIDIA_MODEL", "moonshotai/kimi-k2-instruct"),
        }
    return _config_cache


def _get_ollama_llm():
    global _ollama_llm_cache
    if _ollama_llm_cache is None:
        cfg = _get_config()
        _ollama_llm_cache = Ollama(
            model=cfg["ollama_model"], base_url=cfg["ollama_base_url"]
        )
    return _ollama_llm_cache


# Convenience accessors (read from mutable config)
def _provider():
    return _get_config()["provider"]


def get_current_provider() -> Dict[str, str]:
    """Get information about the current LLM provider."""
    cfg = _get_config()
    return {
        "provider": cfg["provider"],
        "model": cfg["nvidia_model"]
        if cfg["provider"] == "nvidia"
        else cfg["ollama_model"],
        "endpoint": NVIDIA_API_URL
        if cfg["provider"] == "nvidia"
        else cfg["ollama_base_url"],
        "ollama_model": cfg["ollama_model"],
        "nvidia_model": cfg["nvidia_model"],
        "ollama_base_url": cfg["ollama_base_url"],
    }


def update_provider(changes: Dict[str, str]) -> Dict[str, str]:
    """
    Update LLM provider configuration at runtime.

    Args:
        changes: Dict with any of: provider, ollama_model, nvidia_model, nvidia_api_key

    Returns:
        Updated provider info
    """
    global _ollama_llm_cache
    cfg = _get_config()

    allowed = {
        "provider",
        "ollama_model",
        "nvidia_model",
        "nvidia_api_key",
        "ollama_base_url",
    }
    for key, value in changes.items():
        if key in allowed and value is not None:
            cfg[key] = value

    # Reinitialize Ollama LLM if model or URL changed
    if "ollama_model" in changes or "ollama_base_url" in changes:
        _ollama_llm_cache = Ollama(
            model=cfg["ollama_model"],
            base_url=cfg["ollama_base_url"],
        )

    logger.info(
        f"LLM config updated: provider={cfg['provider']}, model={get_current_provider()['model']}"
    )
    return get_current_provider()


def _call_nvidia_api(
    prompt: str,
    system_prompt: str = None,
    model_name: str = None,
    max_retries: int = 3,
    initial_delay: float = 1.0,
) -> str:
    """
    Call NVIDIA API for text generation with retry logic.
    Uses separate system and user messages for better grounding.

    Args:
        prompt: The user prompt to send
        system_prompt: Optional system prompt for grounding instructions
        model_name: Optional model override (defaults to NVIDIA_MODEL env var)
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before retry (default: 1.0)

    Returns:
        Generated text response
    """
    import time

    cfg = _get_config()

    if not cfg["nvidia_api_key"]:
        raise ValueError("NVIDIA_API_KEY not set")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg['nvidia_api_key']}",
    }

    # Build messages with proper role separation
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name or cfg["nvidia_model"],
        "messages": messages,
        "temperature": 0.1,  # Low temperature for factual, grounded responses
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


def _invoke_llm(
    prompt: str,
    system_prompt: str = None,
    model_provider: str = None,
    model_name: str = None,
) -> str:
    """
    Invoke LLM using configured or requested provider.

    Args:
        prompt: The user prompt to send
        system_prompt: Optional system-level instructions for grounding
        model_provider: Optional override — "ollama" or "nvidia" (defaults to LLM_PROVIDER env)
        model_name: Optional model name override

    Returns:
        Generated text response
    """
    cfg = _get_config()
    provider = model_provider or cfg["provider"]

    if provider == "nvidia":
        return _call_nvidia_api(
            prompt, system_prompt=system_prompt, model_name=model_name
        )
    else:
        # For Ollama, use per-request model if specified
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        if model_name and model_name != cfg["ollama_model"]:
            # Create a temporary Ollama instance for the requested model
            from langchain_community.llms import Ollama as OllamaLLM

            temp_llm = OllamaLLM(model=model_name, base_url=cfg["ollama_base_url"])
            return temp_llm.invoke(full_prompt)
        return _get_ollama_llm().invoke(full_prompt)


def _invoke_llm_stream(
    prompt: str,
    system_prompt: str = None,
    model_provider: str = None,
    model_name: str = None,
):
    """Generator that yields LLM chunks."""
    cfg = _get_config()
    provider = model_provider or cfg["provider"]

    if provider == "nvidia":
        if not cfg["nvidia_api_key"]:
            yield "Error: NVIDIA_API_KEY not set"
            return

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['nvidia_api_key']}",
        }
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model_name or cfg["nvidia_model"],
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 2048,
            "stream": True,
        }

        try:
            import json

            response = requests.post(
                NVIDIA_API_URL, headers=headers, json=payload, stream=True, verify=False
            )
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    line_str = line.decode("utf-8")
                    if line_str.startswith("data: ") and line_str != "data: [DONE]":
                        data_str = line_str[6:]
                        try:
                            data = json.loads(data_str)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            yield f"\n[NVIDIA API Error: {str(e)}]"

    else:
        # Ollama stream
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        if model_name and model_name != cfg["ollama_model"]:
            from langchain_community.llms import Ollama as OllamaLLM

            temp_llm = OllamaLLM(model=model_name, base_url=cfg["ollama_base_url"])
            for chunk in temp_llm.stream(full_prompt):
                yield chunk
        else:
            for chunk in _get_ollama_llm().stream(full_prompt):
                yield chunk


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

    system_prompt = """You are an expert assistant for vehicle test engineers.

## CRITICAL RULES - YOU MUST FOLLOW THESE:
1. Answer ONLY using information from the CONTEXT provided below. Do NOT use any external or pre-trained knowledge.
2. If the context does not contain the answer, respond ONLY with: "No data found in uploaded documents."
3. NEVER fabricate, invent, or hallucinate data, names, values, standards, or references.
4. Every claim MUST be directly traceable to the context. Cite sources as [Page X, Document Name].
5. Reproduce data exactly as it appears in the context — do not paraphrase numbers, units, or test results.
6. If a table is present in the context, reproduce it faithfully in Markdown format.

## FORMATTING RULES:
- Answer directly — give the actual data/answer, not just where it's found
- Include tables in proper Markdown format (| col1 | col2 |)
- Use Markdown: tables with |, headers with ##, lists with -
- Cite sources after each piece of information: [Page X, Document Y]"""

    user_prompt = f"""## CONTEXT (Retrieved from documents):
{context}

## USER QUESTION:
{query}"""

    return _invoke_llm(user_prompt, system_prompt=system_prompt)


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
        rendered_prompt = prompt_manager.render_prompt(
            prompt_name="system_prompt",
            version=prompt_version,
            context=context,
            history=history_text,
            query=query,
        )
        return _invoke_llm(rendered_prompt)
    except FileNotFoundError:
        pass

    # Fall back to inline prompt with system/user separation
    system_prompt = """You are an expert assistant for vehicle test engineers.

## CRITICAL RULES - YOU MUST FOLLOW THESE:
1. Answer ONLY using information from the CONTEXT provided below. Do NOT use any external or pre-trained knowledge.
2. If the context does not contain the answer, respond ONLY with: "No data found in uploaded documents."
3. NEVER fabricate, invent, or hallucinate data, names, values, standards, or references.
4. Every claim MUST be directly traceable to the context. Cite sources as [Page X, Document Name].
5. Reproduce data exactly as it appears in the context — do not paraphrase numbers, units, or test results.
6. If a table is present in the context, reproduce it faithfully in Markdown format.

## FORMATTING RULES:
- Answer directly — give the actual data/answer, not just the location
- Reproduce relevant tables in proper Markdown format (| col1 | col2 |)
- Use Markdown formatting for clarity
- Add citations like [Page X, Filename] after each fact"""

    user_prompt = f"""## CONTEXT (Retrieved from documents):
{context}

## CONVERSATION HISTORY:
{history_text}

## USER QUESTION:
{query}"""

    return _invoke_llm(user_prompt, system_prompt=system_prompt)


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
