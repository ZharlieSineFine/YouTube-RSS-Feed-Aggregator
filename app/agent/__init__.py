"""LLM summarization layer for ingested articles."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# python -m app.agent loads this package before __main__.py; load .env first.
load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)

from .config import chat_model_name
from .llm_client import get_chat_client
from .summarize import summarize_pending, summarize_text
from .system_prompt import DEFAULT_SYSTEM_PROMPT

__all__ = [
    "DEFAULT_SYSTEM_PROMPT",
    "chat_model_name",
    "get_chat_client",
    "summarize_pending",
    "summarize_text",
]
