from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Iterable


@dataclass(frozen=True)
class IndustryClassification:
    sector: str
    industry_group: str
    confidence: float
    matched_terms: list[str]
    explanation: str
    source: str = "keyword_rules"


_RULES: tuple[dict, ...] = (
    {
        "sector": "Information Technology",
        "industry_group": "Semiconductors & Semiconductor Equipment",
        "terms": ("semiconductor", "chip", "gpu", "ai accelerator", "foundry", "wafer", "nvidia", "amd", "tsmc", "micron"),
    },
    {
        "sector": "Information Technology",
        "industry_group": "Software & Services",
        "terms": ("software", "cloud", "saas", "cybersecurity", "database", "artificial intelligence", "ai platform", "microsoft", "oracle", "adobe"),
    },
    {
        "sector": "Communication Services",
        "industry_group": "Media & Entertainment",
        "terms": ("streaming", "advertising", "media", "entertainment", "gaming", "netflix", "disney", "youtube", "meta"),
    },
    {
        "sector": "Financials",
        "industry_group": "Banks",
        "terms": ("bank", "deposit", "loan", "lending", "credit", "jpmorgan", "wells fargo", "bank of america", "citigroup"),
    },
    {
        "sector": "Financials",
        "industry_group": "Financial Services",
        "terms": ("asset management", "brokerage", "payment", "card network", "visa", "mastercard", "blackrock", "paypal"),
    },
    {
        "sector": "Health Care",
        "industry_group": "Pharmaceuticals, Biotechnology & Life Sciences",
        "terms": ("drug", "vaccine", "clinical trial", "fda", "biotech", "pharma", "pfizer", "moderna", "eli lilly", "merck"),
    },
    {
        "sector": "Consumer Discretionary",
        "industry_group": "Automobiles & Components",
        "terms": ("vehicle", "ev", "electric vehicle", "automaker", "car sales", "tesla", "ford", "general motors"),
    },
    {
        "sector": "Consumer Discretionary",
        "industry_group": "Consumer Services",
        "terms": ("restaurant", "hotel", "travel", "booking", "airbnb", "starbucks", "mcdonald", "chipotle"),
    },
    {
        "sector": "Consumer Staples",
        "industry_group": "Food, Beverage & Tobacco",
        "terms": ("food", "beverage", "grocery", "coca-cola", "pepsi", "tobacco", "walmart", "costco"),
    },
    {
        "sector": "Energy",
        "industry_group": "Energy",
        "terms": ("oil", "gas", "crude", "lng", "refinery", "energy", "exxon", "chevron"),
    },
    {
        "sector": "Industrials",
        "industry_group": "Capital Goods",
        "terms": ("aerospace", "defense", "machinery", "factory", "manufacturing", "boeing", "caterpillar", "lockheed"),
    },
    {
        "sector": "Industrials",
        "industry_group": "Transportation",
        "terms": ("airline", "railroad", "shipping", "logistics", "freight", "delta", "fedex", "ups", "uber"),
    },
    {
        "sector": "Real Estate",
        "industry_group": "Equity Real Estate Investment Trusts (REITs)",
        "terms": ("reit", "real estate", "property", "rent", "office building", "mortgage"),
    },
    {
        "sector": "Utilities",
        "industry_group": "Utilities",
        "terms": ("utility", "electricity", "power grid", "water utility", "renewable power"),
    },
    {
        "sector": "Materials",
        "industry_group": "Materials",
        "terms": ("mining", "chemical", "steel", "copper", "aluminum", "materials", "lithium"),
    },
)


def _normalize_text(parts: Iterable[str | None]) -> str:
    return " ".join(part or "" for part in parts).lower()


def _term_hits(text: str, terms: Iterable[str]) -> list[str]:
    hits = []
    for term in terms:
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            hits.append(term)
    return hits


def classify_industry(text: str, title: str = "") -> IndustryClassification:
    combined = _normalize_text((title, text))
    if not combined.strip():
        return IndustryClassification(
            sector="Unclassified",
            industry_group="Unclassified",
            confidence=0.0,
            matched_terms=[],
            explanation="분류할 기사 내용이 충분하지 않습니다.",
        )

    scored = []
    for rule in _RULES:
        hits = _term_hits(combined, rule["terms"])
        if hits:
            scored.append((len(hits), hits, rule))

    if not scored:
        return IndustryClassification(
            sector="Unclassified",
            industry_group="Unclassified",
            confidence=0.25,
            matched_terms=[],
            explanation="뚜렷한 산업 키워드를 찾지 못해 특정 업종으로 단정하지 않았습니다.",
        )

    score, hits, rule = max(scored, key=lambda item: item[0])
    confidence = min(0.95, 0.55 + score * 0.1)
    return IndustryClassification(
        sector=rule["sector"],
        industry_group=rule["industry_group"],
        confidence=round(confidence, 2),
        matched_terms=hits[:5],
        explanation=f"{', '.join(hits[:3])} 키워드를 기준으로 {rule['sector']} 섹터와 연결했습니다.",
    )


def classify_article(article: dict) -> dict:
    result = classify_industry(
        text=article.get("original") or article.get("summary") or "",
        title=article.get("title") or "",
    )
    return asdict(result)
