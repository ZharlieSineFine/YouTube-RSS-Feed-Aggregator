"""Clean scraped article titles by removing date prefixes and category labels."""

from __future__ import annotations

import re

# Date patterns that may appear at the start of titles
_DATE_PATTERNS = [
    # "Apr 14, 2026" or "April 14, 2026"
    r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\s*",
    # "2026-04-14" or "2026/04/14"
    r"^\d{4}[-/]\d{2}[-/]\d{2}\s*",
    # "14 Apr 2026" or "14 April 2026"
    r"^\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*",
    # "04/14/2026" or "04-14-2026"
    r"^\d{2}[-/]\d{2}[-/]\d{4}\s*",
]

# Category labels that may appear at the start of titles (case-insensitive match).
# These are only stripped when followed by a separator OR directly concatenated
# with the next word (no space, next char is uppercase).
# Longer phrases must come before shorter ones to match first.
_CATEGORY_LABELS = [
    "Economic Research",
    "Announcements",
    "Announcement",
    "Interpretability",
    "Engineering",
    "Alignment",
    "Research",
    "Security",
    "Science",
    "Product",
    "Company",
    "Release",
    "Safety",
    "Policy",
    "Update",
    "News",
    "Blog",
    "API",
]


def clean_title(raw: str) -> str:
    """
    Remove date prefixes/suffixes and category labels from a scraped title.

    Only strips category labels when they appear as clear prefixes or suffixes:
    - Followed by a separator (: - — etc.) and then text
    - Directly concatenated with title (no space, adjacent char uppercase)
    - At the end of title, directly after a lowercase letter

    Examples:
        "Apr 14, 2026AlignmentAutomated Alignment..."
        → "Automated Alignment..."

        "2026-04-14 Engineering: New API Feature"
        → "New API Feature"

        "Research Safety in AI Systems"
        → "Research Safety in AI Systems"  (unchanged — "Research" is content)

        "Trusted access for cyber defenseSecurity"
        → "Trusted access for cyber defense"
    """
    if not raw:
        return raw

    title = raw.strip()

    # Remove leading date patterns (may appear multiple times if malformed)
    for _ in range(2):
        for pattern in _DATE_PATTERNS:
            title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip()

    # Remove leading category labels only when clearly a prefix
    changed = True
    while changed:
        changed = False
        for label in _CATEGORY_LABELS:
            # Pattern 1: label followed by separator (: - — etc.) then content
            # e.g. "Alignment: How We..." or "Engineering - New..."
            pat_sep = rf"^{re.escape(label)}\s*[:–—\-]\s*"
            new_title = re.sub(pat_sep, "", title, flags=re.IGNORECASE).strip()
            if new_title != title and new_title:
                title = new_title
                changed = True
                break

            # Pattern 2: label directly concatenated (no space) with uppercase letter
            # e.g. "AlignmentAutomated..." → "Automated..."
            pat_concat = rf"^{re.escape(label)}(?=[A-Z])"
            new_title = re.sub(pat_concat, "", title).strip()
            if new_title != title and new_title:
                title = new_title
                changed = True
                break

    # Remove trailing category labels (directly after lowercase letter)
    # e.g. "...cyber defenseSecurity" → "...cyber defense"
    changed = True
    while changed:
        changed = False
        for label in _CATEGORY_LABELS:
            # Match lowercase letter followed immediately by the label at end
            pat_trail = rf"(?<=[a-z]){re.escape(label)}$"
            new_title = re.sub(pat_trail, "", title, flags=re.IGNORECASE).strip()
            if new_title != title and new_title:
                title = new_title
                changed = True
                break

    # Final cleanup: collapse multiple spaces
    title = re.sub(r"\s{2,}", " ", title).strip()

    return title if title else raw.strip()
