from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pipelines.common import ensure_dir  # noqa: E402
from pipelines.fasttext.preprocessing import normalize_label as normalize_fasttext_label  # noqa: E402
from pipelines.fasttext.preprocessing import normalize_text as normalize_fasttext_text  # noqa: E402
from pipelines.fasttext.preprocessing import to_fasttext_line  # noqa: E402
from pipelines.tfidf_randomforest.preprocessing import build_stopword_strategy, preprocess_text  # noqa: E402
from utils.yaml_config import load_string_mapping  # noqa: E402


DATASETS_DIR = ensure_dir(ROOT_DIR / "datasets")
RAW_DATASET_PATH = DATASETS_DIR / "news_raw.csv"
# FASTTEXT_DATASET_PATH = DATASETS_DIR / "news_fastText.csv"
# TFIDF_DATASET_PATH = DATASETS_DIR / "news_tfidf.csv"
GICS_SECTORS = load_string_mapping(ROOT_DIR / "config" / "gics_sectors.yaml", "gics_sectors")

DEFAULT_GEMINI_MODEL = "gemini-3-pro-preview"
DEFAULT_GEMINI_KEY_PATH = ROOT_DIR / "geminiAPI.txt"
try:
    DEFAULT_TICKER_COMPANIES = load_string_mapping(ROOT_DIR / "config" / "snp500.yaml", "default_ticker_companies")
except (FileNotFoundError, ValueError):
    DEFAULT_TICKER_COMPANIES = OrderedDict(
        {
            "XOM": "Exxon Mobil",
            "LIN": "Linde",
            "CAT": "Caterpillar",
            "NEE": "NextEra Energy",
            "JNJ": "Johnson & Johnson",
            "JPM": "JPMorgan Chase",
            "AMZN": "Amazon",
            "PG": "Procter & Gamble",
            "MSFT": "Microsoft",
            "GOOGL": "Alphabet",
            "PLD": "Prologis",
        }
    )


@dataclass(frozen=True)
class NewsRecord:
    article_id: str
    ticker: str
    company_name: str
    title: str
    summary: str
    article_text: str
    publisher: str
    link: str
    published_at: str
    retrieval_query: str
    retrieved_at: str
    gemini_sector: str = ""
    gemini_rationale: str = ""


def build_argument_parser() -> argparse.ArgumentParser:
    """데이터 적재 스크립트의 CLI 인자를 정의한다."""
    parser = argparse.ArgumentParser(
        description="Fetch Yahoo Finance news, classify with Gemini, and build model-ready CSV datasets."
    )
    parser.add_argument("--tickers", nargs="*", default=list(DEFAULT_TICKER_COMPANIES.keys()))
    parser.add_argument("--news-per-ticker", type=int, default=5)
    parser.add_argument("--gemini-model", default=DEFAULT_GEMINI_MODEL)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def _now_iso() -> str:
    """현재 시각을 UTC ISO 문자열로 반환한다."""
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _to_iso8601(value: Any) -> str:
    """Yahoo 뉴스 시간 값을 ISO 8601 문자열로 변환한다."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC).replace(microsecond=0).isoformat()
    if isinstance(value, str) and value:
        return value
    return ""


def _extract_link(item: dict[str, Any]) -> str:
    """뉴스 항목에서 링크 필드를 최대한 안정적으로 추출한다."""
    for key in ("link", "url"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value

    for nested_key in ("canonicalUrl", "clickThroughUrl"):
        nested = item.get(nested_key)
        if isinstance(nested, dict):
            value = nested.get("url")
            if isinstance(value, str) and value:
                return value

    content = item.get("content")
    if isinstance(content, dict):
        for nested_key in ("canonicalUrl", "clickThroughUrl"):
            nested = content.get(nested_key)
            if isinstance(nested, dict):
                value = nested.get("url")
                if isinstance(value, str) and value:
                    return value
    return ""


def build_article_text(item: dict[str, Any]) -> str:
    """제목과 요약을 결합해 분류용 기사 본문 텍스트를 만든다."""
    parts: list[str] = []
    for key in ("title", "summary", "snippet"):
        value = item.get(key)
        if isinstance(value, str) and value:
            parts.append(value.strip())

    content = item.get("content")
    if isinstance(content, dict):
        for key in ("summary", "description"):
            value = content.get(key)
            if isinstance(value, str) and value:
                parts.append(value.strip())

    deduped = list(OrderedDict((part, None) for part in parts))
    return "\n\n".join(deduped).strip()


def build_article_id(ticker: str, link: str, title: str) -> str:
    """티커와 링크를 바탕으로 기사 식별자를 안정적으로 생성한다."""
    digest_source = f"{ticker}|{link}|{title}".encode("utf-8")
    return hashlib.sha1(digest_source).hexdigest()[:16]


def _load_yfinance():
    """뉴스 수집에 필요한 yfinance 모듈을 지연 로드한다."""
    import yfinance as yf

    return yf


def _load_gemini_client():
    """기사 분류에 필요한 Gemini 클라이언트를 지연 로드한다."""
    from google import genai

    return genai


def load_gemini_api_key() -> str:
    """환경변수 또는 geminiAPI.txt에서 Gemini API 키를 불러온다."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if api_key:
        return api_key

    if DEFAULT_GEMINI_KEY_PATH.exists():
        file_api_key = DEFAULT_GEMINI_KEY_PATH.read_text(encoding="utf-8").strip()
        if file_api_key:
            return file_api_key

    raise EnvironmentError("Set GEMINI_API_KEY or store the key in geminiAPI.txt before running this script.")


def collect_news_items(query: str, ticker: str, news_count: int) -> list[dict[str, Any]]:
    """yfinance 검색과 티커 뉴스에서 기사 후보를 수집한다."""
    yf = _load_yfinance()
    news_items: list[dict[str, Any]] = []

    try:
        news_items.extend(yf.Search(query, news_count=news_count).news)
    except Exception:
        pass

    try:
        news_items.extend(yf.Ticker(ticker).get_news(count=news_count, tab="news"))
    except Exception:
        pass

    deduped: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for item in news_items:
        title = str(item.get("title", "")).strip()
        link = _extract_link(item)
        deduped[build_article_id(ticker=ticker, link=link, title=title)] = item
    return list(deduped.values())


def classify_article(client: Any, model_name: str, article_text: str) -> tuple[str, str]:
    """Gemini로 기사 텍스트를 GICS 섹터 하나로 분류한다."""
    sectors = list(GICS_SECTORS.keys())
    response = client.models.generate_content(
        model=model_name,
        contents=(
            "You are classifying an English financial news article into exactly one GICS sector.\n"
            f"Allowed sectors: {', '.join(sectors)}.\n"
            "Return a JSON object with keys sector and rationale.\n\n"
            f"Article:\n{article_text}"
        ),
        config={
            "response_mime_type": "application/json",
            "response_json_schema": {
                "type": "object",
                "required": ["sector", "rationale"],
                "properties": {
                    "sector": {"type": "string", "enum": sectors},
                    "rationale": {"type": "string"},
                },
                "propertyOrdering": ["sector", "rationale"],
            },
        },
    )
    payload = response.parsed if getattr(response, "parsed", None) else json.loads(response.text)
    sector = payload["sector"]
    rationale = payload["rationale"]
    if sector not in GICS_SECTORS:
        raise ValueError(f"Unsupported sector from Gemini: {sector}")
    return sector, rationale


def build_raw_records(tickers: list[str], news_per_ticker: int) -> list[NewsRecord]:
    """뉴스 수집을 수행하여 raw 레코드로 변환한다. (Gemini 분류 제외)"""
    records: list[NewsRecord] = []
    retrieved_at = _now_iso()

    pbar = tqdm(tickers, desc="Collecting news")
    total_found = 0
    for ticker in pbar:
        company_name = DEFAULT_TICKER_COMPANIES.get(ticker, ticker)
        query = f"{ticker} {company_name}"
        
        current_ticker_news = collect_news_items(query=query, ticker=ticker, news_count=news_per_ticker)[:news_per_ticker]
        
        for item in current_ticker_news:
            title = str(item.get("title", "")).strip()
            summary = str(item.get("summary", "")).strip()
            article_text = build_article_text(item)
            if not article_text:
                continue

            link = _extract_link(item)
            # sector, rationale = classify_article(client=client, model_name=gemini_model, article_text=article_text)
            records.append(
                NewsRecord(
                    article_id=build_article_id(ticker=ticker, link=link, title=title),
                    ticker=ticker,
                    company_name=company_name,
                    title=title,
                    summary=summary,
                    article_text=article_text,
                    publisher=str(item.get("publisher") or item.get("provider") or "").strip(),
                    link=link,
                    published_at=_to_iso8601(item.get("providerPublishTime") or item.get("pubDate")),
                    # gemini_sector=sector,
                    # gemini_rationale=rationale,
                    retrieval_query=query,
                    retrieved_at=retrieved_at,
                )
            )
            total_found += 1
            
        pbar.set_postfix({"ticker": ticker, "total": total_found})

    return list(OrderedDict((record.article_id, record) for record in records).values())


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """딕셔너리 행 목록을 CSV 파일로 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"No rows to write for {path}.")

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def build_raw_rows(records: list[NewsRecord]) -> list[dict[str, str]]:
    """원문 텍스트만 포함한 raw 데이터 행을 만든다."""
    return [
        {
            "text": record.article_text,
            # "label": record.gemini_sector,
        }
        for record in records
        if record.article_text
    ]


def build_fasttext_rows(records: list[NewsRecord]) -> list[dict[str, Any]]:
    """raw 레코드를 fastText 전처리 결과 행으로 변환한다."""
    rows: list[dict[str, Any]] = []
    for record in records:
        fasttext_line = to_fasttext_line(record.article_text, record.gemini_sector)
        if not fasttext_line:
            continue
        rows.append(
            {
                "text": record.article_text,
                "label": record.gemini_sector,
                "normalized_text": normalize_fasttext_text(record.article_text),
                "normalized_label": normalize_fasttext_label(record.gemini_sector),
                "fasttext_line": fasttext_line,
            }
        )
    return rows


def build_tfidf_rows(records: list[NewsRecord]) -> list[dict[str, Any]]:
    """raw 레코드를 TF-IDF 전처리 결과 행으로 변환한다."""
    corpus = [record.article_text for record in records]
    custom_strategy = build_stopword_strategy(corpus, strategy="custom_tfidf")
    custom_stopwords = custom_strategy.stopwords

    rows: list[dict[str, Any]] = []
    for record in records:
        rows.append(
            {
                "text": record.article_text,
                "label": record.gemini_sector,
                "tfidf_text_max_df": preprocess_text(record.article_text),
                "tfidf_text_custom_stopwords": preprocess_text(record.article_text, stopwords=custom_stopwords),
            }
        )
    return rows


def validate_output_paths(overwrite: bool) -> None:
    """기존 출력 파일 존재 여부를 확인한다."""
    for path in (RAW_DATASET_PATH,):
        if path.exists() and not overwrite:
            raise FileExistsError(f"{path} already exists. Use --overwrite to replace it.")


def main() -> None:
    """뉴스 수집 및 전처리 CSV 생성을 실행한다. (Gemini 분류 비활성화)"""
    args = build_argument_parser().parse_args()
    validate_output_paths(overwrite=args.overwrite)

    # api_key = load_gemini_api_key()
    # genai = _load_gemini_client()
    # client = genai.Client(api_key=api_key)
    try:
        records = build_raw_records(
            tickers=args.tickers,
            news_per_ticker=args.news_per_ticker,
        )
    finally:
        pass
        # close = getattr(client, "close", None)
        # if callable(close):
        #     close()

    if not records:
        raise ValueError("No news records were collected.")

    write_csv(RAW_DATASET_PATH, build_raw_rows(records))
    # write_csv(FASTTEXT_DATASET_PATH, build_fasttext_rows(records))
    # write_csv(TFIDF_DATASET_PATH, build_tfidf_rows(records))

    print(f"saved raw dataset: {RAW_DATASET_PATH}")
    # print(f"saved fastText dataset: {FASTTEXT_DATASET_PATH}")
    # print(f"saved tf-idf dataset: {TFIDF_DATASET_PATH}")
    print(f"records: {len(records)}")


if __name__ == "__main__":
    main()
