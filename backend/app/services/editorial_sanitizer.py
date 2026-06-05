"""Audience text sanitizer fallback."""

from __future__ import annotations

import re


def clean_audience_text(text: str | None) -> str:
    text = text or ""
    text = re.sub(r"(?i)\b(as an ai|как ии|языковая модель)\b", "", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
