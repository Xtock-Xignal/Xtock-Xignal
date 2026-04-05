from __future__ import annotations

import re
from typing import Optional


WHITESPACE_RE = re.compile(r"\s+")
PUNCTUATION_SPACING_RE = re.compile(r"([.\!?,'/()])")


def normalize_label(label: str) -> str:
    """라벨을 fastText 전용 접두사 형식으로 변환한다."""
    return "__label__" + label.strip().replace(" ", "_")


def decode_label(label: str) -> str:
    """fastText 예측 라벨을 원래 공백 포함 이름으로 복원한다."""
    return label.replace("__label__", "").replace("_", " ")


def normalize_text(text: str) -> str:
    """튜토리얼 스타일로 소문자화하고 구두점 간격을 맞춘다."""
    if not text:
        return ""

    normalized = text.strip().lower()
    normalized = PUNCTUATION_SPACING_RE.sub(r" \1 ", normalized)
    normalized = WHITESPACE_RE.sub(" ", normalized).strip()
    return normalized


def to_fasttext_line(text: str, label: str) -> Optional[str]:
    """문장과 라벨을 fastText 학습 라인으로 합친다."""
    normalized_text = normalize_text(text)
    if not normalized_text:
        return None

    return f"{normalize_label(label)} {normalized_text}"
