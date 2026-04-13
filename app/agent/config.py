"""Agent / LLM settings (environment overrides)."""

from __future__ import annotations

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


# --- Backend: local Ollama (default) or cloud OpenAI API ---
# Default is Ollama + qwen3:14b (no OPENAI_API_KEY). Set AGENT_LLM_BACKEND=openai for the OpenAI API.
AGENT_LLM_BACKEND = os.environ.get("AGENT_LLM_BACKEND", "ollama").strip().lower()

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

# Legacy single language (used if ``AGENT_SUMMARY_LANGUAGES`` is unset).
AGENT_SUMMARY_LANGUAGE = os.environ.get("AGENT_SUMMARY_LANGUAGE", "").strip().lower()


def _norm_lang_token(tok: str) -> str:
    t = tok.strip().lower()
    if not t:
        return ""
    if t in ("en", "english"):
        return "en"
    if t in ("zh-cn", "zh_cn", "zh-hans", "zh_hans", "zh", "chinese", "cn"):
        return "zh-cn"
    return t


def agent_summary_languages() -> list[str]:
    """
    Ordered list of summary variants to generate per article: ``en`` -> ``Article.summary``,
    ``zh-cn`` -> ``Article.summary_zh``. Parsed from ``AGENT_SUMMARY_LANGUAGES`` (comma-separated),
    or from legacy ``AGENT_SUMMARY_LANGUAGE``, or default ``["en"]``.
    """
    raw = os.environ.get("AGENT_SUMMARY_LANGUAGES", "").strip()
    if raw:
        out: list[str] = []
        for part in raw.split(","):
            n = _norm_lang_token(part)
            if n and n not in out:
                out.append(n)
        return out if out else ["en"]
    if AGENT_SUMMARY_LANGUAGE:
        return [_norm_lang_token(AGENT_SUMMARY_LANGUAGE)]
    return ["en"]


def chat_model_name() -> str:
    """Resolved model id for the active backend."""
    if AGENT_LLM_BACKEND == "ollama":
        return OLLAMA_MODEL
    return OPENAI_SUMMARY_MODEL
