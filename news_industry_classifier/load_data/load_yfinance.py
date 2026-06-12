"""
yfinance(Ticker.news + Search)로 뉴스 기사를 수집, 스코어링, 누적 저장한다.

Config: config/class.yaml (GICS: sector → industry_group → ticker:company)
Two-pass 필터링:
  Pass 1 (title): 회사명/ticker alias 기반 관련성 필터 (boolean)
  Pass 2 (body):  newspaper3k 본문 → 점수 기반 필터, min_score=4

점수: industry_group keyword ratio(×10) > sector keyword ratio(×8) > company alias match(+5) > ticker(+2)
  sector match는 AND 대신 keyword hit ratio 사용.

Industry group 규모별 1회/누적 제한:
  1-5회사: 10/run, 150 max | 6-10: 6/run, 100 max
  11-30: 4/run, 60 max | 31+: 2/run, 30 max

출력: datasets/news.csv → article, company_name, ticker, sector, industry_group, collected_at
"""

from __future__ import annotations

import hashlib
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml
import yfinance as yf
from newspaper import Article, Config
from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

CLASS_YAML_PATH = ROOT_DIR / "IC2" / "config" / "class.yaml"
SNP500_PATH = ROOT_DIR / "IC2" / "config" / "snp500.yaml"
DATASETS_DIR = ROOT_DIR / "datasets"
DATASETS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_PATH = DATASETS_DIR / "news.csv"

# newspaper3k 설정
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
)
_NEWS_CONFIG = Config()
_NEWS_CONFIG.browser_user_agent = _USER_AGENT
_NEWS_CONFIG.request_timeout = 5

# ── Industry group 규모별 수집 제한 ─────────────────────────────
_IG_LIMITS = [
    ((1, 5),     {"per_run": 10, "cumulative_max": 150}),
    ((6, 10),    {"per_run": 6,  "cumulative_max": 100}),
    ((11, 30),   {"per_run": 4,  "cumulative_max": 60}),
    ((31, 9999), {"per_run": 2,  "cumulative_max": 30}),
]

_PASS2_MIN_SCORE = 4


# ──────────────────────────────────────────────
# 1. class.yaml 파싱
# ──────────────────────────────────────────────

def _parse_class_yaml(path: Path) -> tuple[dict[str, dict], dict[str, list[str]]]:
    """
    class.yaml을 파싱한다.

    Returns:
        ticker_info: dict[ticker] = {sector, industry_group, company_name}
        industry_groups: dict[industry_group] = [ticker, ...]
    """
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    ticker_info: dict[str, dict] = {}
    industry_groups: dict[str, list[str]] = defaultdict(list)

    for sector, igs in data.items():
        if not isinstance(igs, dict):
            continue
        for ig_name, tickers in igs.items():
            if not isinstance(tickers, list):
                continue
            for entry in tickers:
                if not isinstance(entry, dict):
                    continue
                for ticker, company in entry.items():
                    ticker_info[ticker] = {
                        "sector": sector,
                        "industry_group": ig_name,
                        "company_name": company,
                    }
                    if ticker not in industry_groups[ig_name]:
                        industry_groups[ig_name].append(ticker)

    return ticker_info, dict(industry_groups)


# ──────────────────────────────────────────────
# 2. snp500.yaml → 회사명 매핑 (fallback)
# ──────────────────────────────────────────────

def _load_company_names(path: Path) -> dict[str, str]:
    """snp500.yaml에서 ticker → company_name 매핑을 로드한다."""
    if not path.exists():
        return {}
    return yaml.safe_load(path.open("r", encoding="utf-8")).get("default_ticker_companies", {})


# ──────────────────────────────────────────────
# 3. 회사명 alias 생성
# ──────────────────────────────────────────────

def _get_company_aliases(company_name: str, ticker: str) -> list[str]:
    """회사명의 다양한 표기 변형을 생성한다."""
    aliases: set[str] = {company_name.lower(), ticker.lower()}

    # 법인 접미사를 단어 단위로 제거 (in-word 매칭 방지 위해 " Co" 등 제외)
    # " Inc"가 " Incorporate"/" Income" 내부 매칭할 위험은 데이터가 S&P 500 정식명이라 없음.
    name = company_name
    # trailing suffix removal (word-level, case-insensitive via raw string check)
    for suffix in [", Inc.", ", Inc", ", LLC",
                   " Corporation", " Corp.", " Corp",
                   " Incorporated", " Inc.", " Inc",
                   " Company", " Co.",
                   " plc", " PLC",
                   " Limited", " Ltd."]:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break  # 하나만 제거
    name = name.strip().rstrip(",").strip()
    cleaned = name

    # "(The)" 처리
    cleaned = cleaned.replace("(The)", "").replace("(the)", "").strip()
    if cleaned.endswith("The"):
        cleaned = cleaned[:-3].strip()
    if cleaned.endswith("the"):
        cleaned = cleaned[:-3].strip()

    if cleaned and len(cleaned) >= 2:
        aliases.add(cleaned.lower())

    # 쉼표 분할 (e.g. "Nike, Inc." → "Nike") — 단, class yaml의 표기만 처리
    if ", " in cleaned:
        parts = cleaned.split(", ")
        for p in parts:
            p = p.strip().rstrip(")")
            if p and len(p) >= 2:
                aliases.add(p.lower())

    # 수동 alias
    manual: dict[str, list[str]] = {
        "walt disney company (the)": ["disney", "walt disney"],
        "coca-cola company (the)": ["coca-cola", "coke"],
        "lilly (eli)": ["eli lilly", "lilly"],
        "home depot (the)": ["home depot"],
        "campbell's company (the)": ["campbell's", "campbell soup"],
        "travelers companies (the)": ["travelers"],
        "mosaic company (the)": ["mosaic"],
        "hershey company (the)": ["hershey"],
        "jm smucker company (the)": ["smucker's", "jm smucker"],
        "estée lauder companies (the)": ["estée lauder", "lauder"],
        "cooper companies (the)": ["cooper"],
        "hartford (the)": ["hartford"],
        "trade desk (the)": ["trade desk"],
        "rtx corporation": ["rtx"],
        "bxp, inc.": ["bxp"],
        "alphabet inc. (class a)": ["alphabet", "google"],
        "alphabet inc. (class c)": ["alphabet", "google"],
        "meta platforms": ["meta", "facebook"],
        "salesforce": ["salesforce", "crm"],
        "thermo fisher scientific": ["thermo fisher"],
        "booking holdings": ["booking"],
        "carrier global": ["carrier"],
        "deere & company": ["deere", "john deere"],
        "eaton corporation": ["eaton"],
        "illinois tool works": ["illinois tool works", "itw"],
        "fiserv": ["fiserv"],
        "fidelity national information services": ["fidelity national", "fis"],
        "s&p global": ["s&p global", "sp global"],
        "intuit": ["intuit"],
        "paypal": ["paypal"],
        "mastercard": ["mastercard"],
        "visa inc.": ["visa"],
        "berkshire hathaway": ["berkshire hathaway", "berkshire"],
        "ameriprise financial": ["ameriprise"],
        "morgan stanley": ["morgan stanley"],
        "goldman sachs": ["goldman sachs", "goldman"],
        "bank of america": ["bank of america", "bofa"],
        "jpmorgan chase": ["jpmorgan chase", "jpmorgan", "chase"],
        "wells fargo": ["wells fargo"],
        "citigroup": ["citigroup", "citi"],
        "unitedhealth group": ["unitedhealth", "united health"],
        "elevance health": ["elevance", "anthem"],
        "cvs health": ["cvs"],
        "centene corporation": ["centene"],
        "humana": ["humana"],
        "cigna": ["cigna"],
        "bristol myers squibb": ["bristol myers squibb", "bristol-myers"],
        "johnson & johnson": ["johnson & johnson", "jnj"],
        "merck & co.": ["merck"],
        "pfizer": ["pfizer"],
        "abbvie": ["abbvie"],
        "amgen": ["amgen"],
        "gilead sciences": ["gilead"],
        "moderna": ["moderna"],
        "vertex pharmaceuticals": ["vertex"],
        "regeneron pharmaceuticals": ["regeneron"],
        "biogen": ["biogen"],
        "starbucks": ["starbucks"],
        "mcdonald's": ["mcdonald's", "mcdonalds"],
        "yum! brands": ["yum brands", "yum"],
        "chipotle mexican grill": ["chipotle"],
        "nike, inc.": ["nike"],
        "caterpillar inc.": ["caterpillar", "cat"],
        "boeing": ["boeing"],
        "lockheed martin": ["lockheed martin", "lockheed"],
        "northrop grumman": ["northrop grumman", "northrop"],
        "chevron corporation": ["chevron"],
        "exxonmobil": ["exxonmobil", "exxon", "mobil"],
        "conocophillips": ["conocophillips", "conoco"],
        "occidental petroleum": ["occidental", "oxy"],
        "apple inc.": ["apple"],
        "microsoft": ["microsoft"],
        "amazon": ["amazon"],
        "nvidia": ["nvidia"],
        "tesla, inc.": ["tesla"],
        "netflix": ["netflix"],
        "adobe inc.": ["adobe"],
        "oracle corporation": ["oracle"],
        "cisco": ["cisco"],
        "ibm": ["ibm"],
        "qualcomm": ["qualcomm"],
        "texas instruments": ["texas instruments", "ti"],
        "broadcom": ["broadcom"],
        "3m": ["3m"],
        "ge aerospace": ["ge aerospace", "general electric"],
        "ge vernova": ["ge vernova"],
        "meta platforms": ["meta", "facebook"],
        "linde plc": ["linde"],
        "crh plc": ["crh"],
        "smurfit westrock": ["smurfit westrock"],
        "brown & brown": ["brown & brown", "brown and brown"],
        "marsh mclennan": ["marsh mclennan", "marsh"],
        "prudential financial": ["prudential"],
        "principal financial group": ["principal"],
        "m&t bank": ["m&t bank", "mt bank"],
        "pnc financial services": ["pnc"],
        "truist financial": ["truist"],
        "u.s. bancorp": ["u.s. bancorp", "us bancorp", "us bank"],
        "capital one": ["capital one"],
        "synchrony financial": ["synchrony"],
        "american express": ["american express", "amex"],
        "moody's corporation": ["moody's", "moodys"],
        "s&p global": ["s&p global"],
        "blackrock": ["blackrock"],
        "blackstone inc.": ["blackstone"],
        "kkr & co.": ["kkr"],
        "apollo global management": ["apollo"],
        "ares management": ["ares"],
        "coinbase": ["coinbase"],
        "robinhood markets": ["robinhood"],
    }

    name_lower = company_name.lower()
    extra = manual.get(name_lower, [])
    for e in extra:
        aliases.add(e.lower())

    return [a for a in aliases if a and len(a.strip()) >= 2]


# ──────────────────────────────────────────────
# 4. 텍스트 스코어링
# ──────────────────────────────────────────────

def _sector_match_score(sector_name: str, text: str) -> float:
    """sector명 키워드 중 text에 포함된 비율 (0.0 ~ 1.0)."""
    t = text.lower()
    stop_words = {"and", "or", "the", "a", "an", "of", "in", "for", "to", "with", "by", "on", "at", "&"}
    keywords = [
        w for w in sector_name.lower()
        .replace(" and ", " ").replace(" & ", " ")
        .replace(" - ", " ").replace("  ", " ").split()
        if w not in stop_words
    ]
    if not keywords:
        return 0.0
    hits = sum(1 for kw in keywords if kw in t)
    return hits / len(keywords)


def _pass1_filter(title: str, ticker: str, company_aliases: list[str]) -> bool:
    """제목에 ticker나 회사 alias가 하나라도 있으면 통과."""
    t = title.lower()
    if ticker.lower() in t:
        return True
    for alias in company_aliases:
        if alias in t:
            return True
    return False


def _score_body(
    body: str,
    company_aliases: list[str],
    ticker: str,
    sector: str,
    industry_group: str,
) -> int:
    """
    본문 스코어링.
    점수: industry_group keyword ratio(×10) + sector keyword ratio(×8) + company alias(+5) + ticker(+2)
    """
    score = 0
    b = body.lower()

    # industry_group keyword match
    ig_score = int(10 * _sector_match_score(industry_group, b))
    score += ig_score

    # sector keyword match
    s_score = int(8 * _sector_match_score(sector, b))
    score += s_score

    # company alias match
    if any(alias in b for alias in company_aliases):
        score += 5

    # ticker match
    if ticker.lower() in b:
        score += 2

    return score


# ──────────────────────────────────────────────
# 5. 기사 본문 추출 (newspaper3k)
# ──────────────────────────────────────────────

def _extract_article_body(url: str) -> str:
    """URL에서 기사 본문을 추출한다."""
    if not url:
        return ""
    try:
        article = Article(url, config=_NEWS_CONFIG)
        article.download()
        article.parse()
        return article.text.strip()
    except Exception as e:
        print(f"      [WARN] newspaper3k failed for {url}: {e}")
        return ""


# ──────────────────────────────────────────────
# 6. Ticker.news URL 추출
# ──────────────────────────────────────────────

def _get_ticker_news_url(item: dict) -> str | None:
    """Ticker.news item에서 URL을 추출한다."""
    content = item.get("content", {})
    if not content:
        return None

    for key in ("clickThroughUrl", "canonicalUrl"):
        if isinstance(content.get(key), dict):
            url = content[key].get("url")
            if url:
                return url
    return content.get("link") or None


# ──────────────────────────────────────────────
# 7. Search + Two-pass 수집 (단일 ticker)
# ──────────────────────────────────────────────

def _collect_for_ticker(
    ticker: str,
    company_name: str,
    sector: str,
    industry_group: str,
    per_run_limit: int,
) -> list[dict]:
    """
    (ticker, industry_group) 쌍에 대해 two-pass 수집.

    Source: Ticker.news (10 items) + Search (20 items) → merge → score → filter.
    """
    company_aliases = _get_company_aliases(company_name, ticker)
    raw_items: list[dict] = []
    seen_urls: set[str] = set()

    # 1. Ticker.news
    try:
        t = yf.Ticker(ticker)
        for item in (t.news or []):
            url = _get_ticker_news_url(item)
            if url and url not in seen_urls:
                seen_urls.add(url)
                content = item.get("content", {})
                raw_items.append({
                    "title": content.get("title", ""),
                    "link": url,
                    "summary": content.get("summary", ""),
                })
    except Exception as e:
        print(f"      [WARN] Ticker.news failed for {ticker}: {e}")

    # 2. Search
    try:
        search = yf.Search(f"{ticker} {company_name}", news_count=20)
        for item in (search.news or []):
            url = item.get("link", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                raw_items.append({
                    "title": item.get("title", ""),
                    "link": url,
                    "summary": "",
                })
    except Exception as e:
        print(f"      [WARN] yf.Search failed for {ticker}: {e}")

    if not raw_items:
        return []

    debug = {"raw": 0, "no_title_or_link": 0, "pass1_fail": 0, "body_empty": 0, "pass2_fail": 0, "collected": 0}
    collected: list[dict] = []
    details: list[str] = []

    for item in raw_items:
        debug["raw"] += 1
        if len(collected) >= per_run_limit:
            break

        title = (item.get("title") or "").strip()
        link = (item.get("link") or "").strip()

        if not title or not link:
            debug["no_title_or_link"] += 1
            continue

        # Pass 1: 회사/ticker 관련성
        if not _pass1_filter(title, ticker, company_aliases):
            debug["pass1_fail"] += 1
            if debug["pass1_fail"] <= 3:
                details.append(f"        PASS1_FAIL: title='{title[:80]}'")
            continue

        # newspaper3k 본문 추출
        body = _extract_article_body(link)
        if not body or len(body) < 100:
            summary = item.get("summary") or ""
            body = summary or title
        if not body:
            debug["body_empty"] += 1
            if debug["body_empty"] <= 3:
                details.append(f"        BODY_EMPTY: {link}")
            continue

        # Pass 2: 본문 스코어링
        pass2_score = _score_body(body, company_aliases, ticker, sector, industry_group)
        if pass2_score < _PASS2_MIN_SCORE:
            debug["pass2_fail"] += 1
            if debug["pass2_fail"] <= 3:
                details.append(f"        PASS2_FAIL: score={pass2_score} title='{title[:80]}'")
            continue

        collected.append({
            "article": body,
            "company_name": company_name,
            "ticker": ticker,
            "sector": sector,
            "industry_group": industry_group,
            "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "_pass2_score": pass2_score,
            "_url": link,
        })
        debug["collected"] += 1

    # 0개 수집 시 디버그 출력
    if not collected and debug["raw"] > 0:
        print(f"      ⚠️ 0 articles for {ticker}({company_name}) / {sector} > {industry_group}")
        print(f"         debug: {debug}")
        for d in details[:5]:
            print(d)

    collected.sort(key=lambda x: x["_pass2_score"], reverse=True)
    return collected[:per_run_limit]


# ──────────────────────────────────────────────
# 8. Industry group 규모별 제한 계산
# ──────────────────────────────────────────────

def _compute_ig_limits(
    industry_groups: dict[str, list[str]],
) -> dict[str, dict]:
    """각 industry_group별 회사 수와 제한을 계산한다."""
    limits: dict[str, dict] = {}
    for ig, tickers in industry_groups.items():
        n = len(tickers)
        matched = None
        for (lo, hi), limit in _IG_LIMITS:
            if lo <= n <= hi:
                matched = limit
                break
        if matched is None:
            matched = _IG_LIMITS[-1][1]
        limits[ig] = {
            "per_run": matched["per_run"],
            "cumulative_max": matched["cumulative_max"],
            "company_count": n,
        }
    return limits


# ──────────────────────────────────────────────
# 9. 누적 저장 (중복 제거 + capacity 관리)
# ──────────────────────────────────────────────

def _article_dedup_key(ticker: str, industry_group: str, article: str) -> str:
    """(ticker, industry_group, article) 조합의 해시 키."""
    raw = f"{ticker}||{industry_group}||{article}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _merge_with_existing(
    new_rows: list[dict],
    csv_path: Path = OUTPUT_PATH,
    ig_limits: dict[str, dict] | None = None,
) -> list[dict]:
    """
    새로 수집된 기사를 기존 CSV에 병합한다.

    1. 기존 CSV가 있으면 초기화 (신규 실행 시 리셋)
    2. 중복 제거: (ticker, industry_group, article) 해시 기준
    3. 각 (ticker, industry_group) pair의 누적 수가 cumulative_max 초과 시 오래된 기사 제거
    """
    existing_rows: list[dict] = []

    if csv_path.exists():
        try:
            df_existing = pd.read_csv(csv_path, encoding="utf-8-sig")
            existing_rows = df_existing.to_dict("records")
        except Exception:
            existing_rows = []

    # 기존 article 해시셋 구축
    existing_keys: set[str] = set()
    for row in existing_rows:
        key = _article_dedup_key(
            row.get("ticker", ""),
            row.get("industry_group", ""),
            row.get("article", ""),
        )
        existing_keys.add(key)

    # 새 기사 추가 (중복 제외)
    added = 0
    skipped = 0
    for row in new_rows:
        key = _article_dedup_key(
            row["ticker"],
            row["industry_group"],
            row["article"],
        )
        if key in existing_keys:
            skipped += 1
            continue
        existing_keys.add(key)
        clean_row = {
            "article": row["article"],
            "company_name": row["company_name"],
            "ticker": row["ticker"],
            "sector": row["sector"],
            "industry_group": row["industry_group"],
            "collected_at": row["collected_at"],
        }
        existing_rows.append(clean_row)
        added += 1

    # capacity 관리: (ticker, industry_group) pair별 누적 수 제한
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in existing_rows:
        key = (row.get("ticker", ""), row.get("industry_group", ""))
        groups[key].append(row)

    all_limits = ig_limits or {}

    trimmed_rows: list[dict] = []
    removed = 0
    for (tckr, ig), rows in groups.items():
        limit_info = all_limits.get(ig, {})
        cum_max = limit_info.get("cumulative_max", 150)
        rows_sorted = sorted(rows, key=lambda r: r.get("collected_at", ""))
        if len(rows_sorted) > cum_max:
            removed += len(rows_sorted) - cum_max
            rows_sorted = rows_sorted[-cum_max:]
        trimmed_rows.extend(rows_sorted)

    print(f"   New: {added} | Skipped (dup): {skipped} | Removed (over cap): {removed}")
    return trimmed_rows


# ──────────────────────────────────────────────
# 10. 메인
# ──────────────────────────────────────────────

def main() -> None:
    # 1. class.yaml 파싱
    print(f"Loading {CLASS_YAML_PATH} ...")
    ticker_info, industry_groups = _parse_class_yaml(CLASS_YAML_PATH)
    company_names_fallback = _load_company_names(SNP500_PATH)

    if not ticker_info:
        print(f"Error: No ticker mappings found in {CLASS_YAML_PATH}")
        return

    print(f"Loaded {len(ticker_info)} tickers across {len(industry_groups)} industry groups")

    # 2. industry_group별 제한 계산
    ig_limits = _compute_ig_limits(industry_groups)
    for ig, info in sorted(ig_limits.items()):
        print(f"   {ig:45s}: {info['company_count']:3d} companies → {info['per_run']}/run, max {info['cumulative_max']}")

    # 3. CSV 초기화 (기존 데이터 리셋)
    if OUTPUT_PATH.exists():
        print(f"\nResetting existing CSV: {OUTPUT_PATH}")
        df_empty = pd.DataFrame(columns=["article", "company_name", "ticker", "sector", "industry_group", "collected_at"])
        df_empty.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"   Cleared all existing data.")

    tickers_in_order: list[str] = []
    ig_order = sorted(industry_groups.keys())
    for ig in ig_order:
        for t in industry_groups[ig]:
            if t not in tickers_in_order:
                tickers_in_order.append(t)

    all_new_rows: list[dict] = []

    ig_stats: dict[str, dict] = {
        ig: {"possible": 0, "actual": 0, "zero_pairs": []}
        for ig in ig_limits
    }

    print(f"\n=== Collecting news for {len(tickers_in_order)} tickers ===")

    # ticker → 첫 번째 industry_group만 사용 (각 ticker는 class.yaml에서 unique)
    for ticker_symbol in tqdm(tickers_in_order, desc="Tickers"):
        info = ticker_info.get(ticker_symbol)
        if not info:
            continue

        company = info["company_name"] or company_names_fallback.get(ticker_symbol, ticker_symbol)
        sector = info["sector"]
        industry_group = info["industry_group"]

        limit = ig_limits.get(industry_group, {}).get("per_run", 4)
        ig_stats[industry_group]["possible"] += limit

        rows = _collect_for_ticker(
            ticker=ticker_symbol,
            company_name=company,
            sector=sector,
            industry_group=industry_group,
            per_run_limit=limit,
        )

        if not rows:
            ig_stats[industry_group]["zero_pairs"].append(f"{ticker_symbol}({company})")

        for row in rows:
            url = row.pop("_url", "")
            row.pop("_pass2_score", 0)
            # no global URL dedup — each pair independently collects
            all_new_rows.append(row)
            ig_stats[industry_group]["actual"] += 1

        time.sleep(0.3)

    # ── 보고서 출력 ──
    print(f"\n{'='*60}")
    print("  Industry Group Collection Report")
    print(f"{'='*60}")
    print(f"  {'Industry Group':45s} {'Poss':>5s} {'Got':>5s} {'Rate':>7s}")
    print(f"  {'-'*45} {'-'*5} {'-'*5} {'-'*7}")
    total_possible = 0
    total_actual = 0
    for ig in sorted(ig_stats):
        s = ig_stats[ig]
        rate = s["actual"] / s["possible"] * 100 if s["possible"] > 0 else 0
        total_possible += s["possible"]
        total_actual += s["actual"]
        marker = " ⚠️" if s["actual"] == 0 else ""
        print(f"  {ig:45s} {s['possible']:5d} {s['actual']:5d} {rate:6.1f}%{marker}")
    print(f"  {'-'*45} {'-'*5} {'-'*5} {'-'*7}")
    overall_rate = total_actual / total_possible * 100 if total_possible > 0 else 0
    print(f"  {'TOTAL':45s} {total_possible:5d} {total_actual:5d} {overall_rate:6.1f}%")

    # 0개 pair 출력
    zero_igs = {ig: s["zero_pairs"] for ig, s in ig_stats.items() if s["zero_pairs"]}
    if zero_igs:
        print(f"\n  ⚠️  (ticker, industry_group) pairs with 0 articles:")
        for ig, pairs in sorted(zero_igs.items()):
            print(f"     {ig}: {len(pairs)} pairs")
            for p in pairs[:5]:
                print(f"       - {p}")
            if len(pairs) > 5:
                print(f"       ... and {len(pairs) - 5} more")

    if not all_new_rows:
        print("\n  ⚠️  No new articles collected in this run")
        return

    print(f"\n=== Merging {len(all_new_rows)} new articles with existing dataset ===")
    merged_rows = _merge_with_existing(all_new_rows, OUTPUT_PATH, ig_limits)

    if merged_rows:
        df = pd.DataFrame(merged_rows)
        df = df[["article", "company_name", "ticker", "sector", "industry_group", "collected_at"]]
        df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
        print(f"\n✅ Saved {len(df)} rows to {OUTPUT_PATH}")
        print(f"   Columns: {list(df.columns)}")
        sector_counts = df["sector"].value_counts()
        for sector, count in sector_counts.items():
            print(f"   {sector}: {count} articles")
        print(f"\n   Per industry group:")
        ig_counts = df.groupby(["sector", "industry_group"]).size()
        for (sec, ig), cnt in ig_counts.items():
            print(f"      {sec} > {ig}: {cnt}")
    else:
        print("\n  ⚠️  No data after merge")


if __name__ == "__main__":
    main()
