"""System prompt for the summarization agent — edit to match reader persona and tone."""

from __future__ import annotations

DEFAULT_SYSTEM_PROMPT = """You are an editorial assistant for a technical reader who tracks AI industry news, research, and commentary.

Your job is to produce a concise, accurate summary of the article or transcript you receive.

Rules:
- Lead with the most newsworthy or actionable point in 1–2 sentences.
- Then add short bullets (3–6) for key facts, claims, names, products, dates, or numbers — only if present in the text.
- If the source is a video transcript, focus on substance (arguments, examples) not filler or intros.
- Do not invent facts, links, or quotes. If the text is unclear or empty, say what is missing briefly.
- Use clear, direct language in the output language requested below. Avoid hype and marketing language unless quoting.
- Keep the total summary under about 350 words unless the content is extraordinarily dense.
"""


def _is_simplified_chinese(lang: str) -> bool:
    return lang in (
        "zh-cn",
        "zh_cn",
        "zh-hans",
        "zh_hans",
        "zh",
        "chinese",
        "cn",
        "简体",
    )


def get_effective_system_prompt_for_language(lang_code: str) -> str:
    """System prompt for one output language: ``en``, ``zh-cn``, or other hints."""
    lang = (lang_code or "").strip().lower()
    base = DEFAULT_SYSTEM_PROMPT
    if lang in ("en", "english", ""):
        return (
            base
            + "\n\n**Language:** Write the **entire** summary in **English**.\n"
        )
    if _is_simplified_chinese(lang) or lang == "zh-cn":
        return (
            base
            + "\n\n**Language:** Write the **entire** summary in **Simplified Chinese (简体中文)**. "
            "Use conventional mainland tech wording; keep well-known product, company, and person names "
            "in Latin or common Chinese usage as appropriate.\n"
            "\n**Output format (required):** Line 1 must be exactly: `TITLE_ZH: ` followed by a "
            "faithful Simplified Chinese translation of the source title only (no quotes). "
            "Line 2 must be blank. Line 3 onward is the summary body as usual (no `TITLE_ZH` line repeated).\n"
        )
    return (
        base
        + f"\n\n**Language:** Write the entire summary in the requested locale (hint: {lang!r}).\n"
    )


def get_effective_system_prompt() -> str:
    """Backward-compatible single-language prompt (legacy ``AGENT_SUMMARY_LANGUAGE`` only)."""
    from .config import AGENT_SUMMARY_LANGUAGE

    if not AGENT_SUMMARY_LANGUAGE:
        return get_effective_system_prompt_for_language("en")
    return get_effective_system_prompt_for_language(AGENT_SUMMARY_LANGUAGE)
