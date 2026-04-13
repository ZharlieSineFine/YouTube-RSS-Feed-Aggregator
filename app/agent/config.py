"""Agent / LLM settings (environment overrides)."""

from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# --- Backend: OpenAI API (default) or local Ollama (OpenAI-compatible /v1) ---
# Set AGENT_LLM_BACKEND=ollama to use a local model (no OPENAI_API_KEY needed).
AGENT_LLM_BACKEND = os.environ.get("AGENT_LLM_BACKEND", "openai").strip().lower()

# Cloud OpenAI (when AGENT_LLM_BACKEND=openai).
OPENAI_SUMMARY_MODEL = os.environ.get("OPENAI_SUMMARY_MODEL", "gpt-4o-mini")

# Ollama: base URL must include /v1 (see https://ollama.com/blog/openai-compatibility).
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
# Default local model: Qwen3 14B (`ollama pull qwen3:14b`). Override if your library uses another tag.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:14b")

# Any OpenAI-compatible HTTP API (optional). If set, used instead of default OpenAI URL
# even for backend=openai — useful for LiteLLM, vLLM, etc.
AGENT_OPENAI_BASE_URL = os.environ.get("AGENT_OPENAI_BASE_URL", "").strip()

# Hard cap on characters sent to the model (very long transcripts are truncated).
MAX_INPUT_CHARS = _int("AGENT_MAX_INPUT_CHARS", 48_000)


def chat_model_name() -> str:
    """Resolved model id for the active backend."""
    if AGENT_LLM_BACKEND == "ollama":
        return OLLAMA_MODEL
    return OPENAI_SUMMARY_MODEL
