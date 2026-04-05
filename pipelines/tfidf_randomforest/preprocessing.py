from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

try:
    import nltk
    from nltk import pos_tag
    from nltk.corpus import wordnet
    from nltk.stem import WordNetLemmatizer
except ModuleNotFoundError:  # pragma: no cover - optional at local verification time
    nltk = None
    pos_tag = None
    wordnet = None
    WordNetLemmatizer = None


TOKEN_RE = re.compile(r"[a-z0-9가-힣]+")

RAW_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "those",
    "to",
    "was",
    "were",
    "will",
    "with",
}

NLTK_RESOURCES = {
    "taggers/averaged_perceptron_tagger_eng": "averaged_perceptron_tagger_eng",
    "corpora/wordnet": "wordnet",
    "corpora/omw-1.4": "omw-1.4",
}

LEMMATIZER = WordNetLemmatizer() if WordNetLemmatizer is not None else None
_NLTK_RESOURCES_READY: bool | None = None


@dataclass(frozen=True)
class StopwordSelectionResult:
    strategy: str
    stopwords: set[str]
    metadata: dict[str, float | int | list[str] | bool]


def _ensure_nltk_resources() -> bool:
    """필요한 NLTK lemmatization 리소스 준비 상태를 확인한다."""
    global _NLTK_RESOURCES_READY

    if _NLTK_RESOURCES_READY is not None:
        return _NLTK_RESOURCES_READY

    if nltk is None:
        _NLTK_RESOURCES_READY = False
        return _NLTK_RESOURCES_READY

    try:
        for resource_path in NLTK_RESOURCES:
            nltk.data.find(resource_path)
        _NLTK_RESOURCES_READY = True
    except LookupError:
        _NLTK_RESOURCES_READY = False

    return _NLTK_RESOURCES_READY


def download_nltk_resources(download_dir: str | None = None, quiet: bool = False) -> dict[str, bool]:
    """TF-IDF lemmatization 에 필요한 NLTK 리소스를 다운로드한다."""
    global _NLTK_RESOURCES_READY

    if nltk is None:
        raise ModuleNotFoundError("nltk is required to download lemmatization resources.")

    results: dict[str, bool] = {}
    for package_name in NLTK_RESOURCES.values():
        results[package_name] = bool(nltk.download(package_name, download_dir=download_dir, quiet=quiet))

    _NLTK_RESOURCES_READY = all(results.values())
    return results


def _wordnet_pos(treebank_tag: str):
    """Penn Treebank 품사를 WordNet 품사로 변환한다."""
    if wordnet is None:
        return None
    if treebank_tag.startswith("J"):
        return wordnet.ADJ
    if treebank_tag.startswith("V"):
        return wordnet.VERB
    if treebank_tag.startswith("N"):
        return wordnet.NOUN
    if treebank_tag.startswith("R"):
        return wordnet.ADV
    return wordnet.NOUN


def tokenize(text: str) -> list[str]:
    """소문자 기준 영문·숫자·한글 토큰 목록을 추출한다."""
    return TOKEN_RE.findall(text.lower())


def lemmatize_tokens(text: str) -> list[str]:
    """토큰을 표제어로 정규화해 TF-IDF 입력 품질을 높인다."""
    tokens = tokenize(text)
    if not tokens or LEMMATIZER is None or pos_tag is None or not _ensure_nltk_resources():
        return tokens

    tagged_tokens = pos_tag(tokens)
    lemmas: list[str] = []
    for token, tag in tagged_tokens:
        lemma = LEMMATIZER.lemmatize(token, pos=_wordnet_pos(tag))
        lemmas.append(lemma)
    return lemmas


BASE_STOPWORDS = set(RAW_STOPWORDS)


def normalize_tokens(text: str) -> list[str]:
    """토큰화 후 각 토큰에 lemmatization을 적용한다."""
    return lemmatize_tokens(text)


def preprocess_text(text: str, stopwords: set[str] | None = None) -> str:
    """불용어를 제거한 TF-IDF 입력 문자열을 생성한다."""
    active_stopwords = stopwords or BASE_STOPWORDS
    processed_tokens = [token for token in normalize_tokens(text) if token and token not in active_stopwords]
    return " ".join(processed_tokens)


def derive_custom_stopwords_by_tfidf(
    texts: list[str],
    top_k: int = 25,
    min_doc_frequency: float = 0.6,
) -> StopwordSelectionResult:
    """높은 문서빈도·낮은 평균 TF-IDF 단어를 불용어로 고른다."""
    documents = [normalize_tokens(text) for text in texts]
    document_count = len(documents)
    if document_count == 0:
        return StopwordSelectionResult(
            strategy="custom_tfidf",
            stopwords=set(BASE_STOPWORDS),
            metadata={"selected_terms": [], "document_count": 0, "lemmatization_enabled": _ensure_nltk_resources()},
        )

    doc_frequency: Counter[str] = Counter()
    term_scores: Counter[str] = Counter()

    for tokens in documents:
        filtered_tokens = [token for token in tokens if token not in BASE_STOPWORDS]
        if not filtered_tokens:
            continue

        unique_tokens = set(filtered_tokens)
        for token in unique_tokens:
            doc_frequency[token] += 1

        counts = Counter(filtered_tokens)
        total = sum(counts.values())
        for token, count in counts.items():
            term_scores[token] += count / total

    ranked_terms: list[tuple[float, int, str]] = []
    for token, df in doc_frequency.items():
        ratio = df / document_count
        if ratio < min_doc_frequency:
            continue

        idf = math.log((1 + document_count) / (1 + df)) + 1.0
        average_tf = term_scores[token] / df
        average_tfidf = average_tf * idf
        ranked_terms.append((average_tfidf, -df, token))

    ranked_terms.sort()
    selected_terms = [token for _, _, token in ranked_terms[:top_k]]
    combined_stopwords = set(BASE_STOPWORDS) | set(selected_terms)

    return StopwordSelectionResult(
        strategy="custom_tfidf",
        stopwords=combined_stopwords,
        metadata={
            "selected_terms": selected_terms,
            "top_k": top_k,
            "min_doc_frequency": min_doc_frequency,
            "document_count": document_count,
            "lemmatization_enabled": _ensure_nltk_resources(),
        },
    )


def build_stopword_strategy(
    texts: list[str],
    strategy: str,
    max_df: float = 0.85,
    custom_top_k: int = 25,
    custom_min_doc_frequency: float = 0.6,
) -> StopwordSelectionResult:
    """선택한 전략에 맞는 불용어 집합과 메타데이터를 만든다."""
    if strategy == "max_df":
        return StopwordSelectionResult(
            strategy="max_df",
            stopwords=set(BASE_STOPWORDS),
            metadata={
                "max_df": max_df,
                "lemmatization_enabled": _ensure_nltk_resources(),
            },
        )

    if strategy == "custom_tfidf":
        return derive_custom_stopwords_by_tfidf(
            texts,
            top_k=custom_top_k,
            min_doc_frequency=custom_min_doc_frequency,
        )

    raise ValueError(f"Unsupported stopword strategy: {strategy}")
