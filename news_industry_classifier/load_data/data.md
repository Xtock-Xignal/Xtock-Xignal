# Data Pipeline & Dataset

## Overview

The dataset (`datasets/news.csv`) contains 1,702 financial news articles across 501 unique tickers, covering all 11 GICS sectors and 25 industry groups. All articles were collected on **2026-05-31** via Yahoo Finance (`yfinance` library).

---

## Collection Pipeline

### Source

- **API**: `yfinance` (`Ticker.news` + `Search`)
- **Ticker universe**: S&P 500, Dow Jones, NASDAQ 100 constituents (defined in `IC2/config/class.yaml`)
- **Article body**: Extracted via `newspaper3k`

### Two-Pass Filtering

Each (ticker, industry_group) pair goes through two filtering passes:

#### Pass 1 — Title Relevance (boolean)
Title must contain the ticker or at least one company alias (name variations, manual aliases).

#### Pass 2 — Body Scoring (threshold)
Article body is scored by four signals — passes only if score ≥ 4:

| Signal | Weight | Max |
|---|---|---|
| Industry group keyword hit ratio | ×10 | 10 |
| Sector keyword hit ratio | ×8 | 8 |
| Company name alias match (body) | +5 | 5 |
| Ticker mention (body) | +2 | 2 |
| **Total** | | **25** |

### Collection Sources per Ticker

1. **Ticker.news** — up to 10 items
2. **yf.Search** — up to 20 items (`{ticker} {company_name}`)

Sources are merged, deduplicated by URL, two-pass filtered, and the top N (per-run limit) are kept per ticker.

### Deduplication & Capacity Management

- **Dedup key**: MD5 hash of `(ticker || industry_group || article)`
- **Per-pair cap**: Each (ticker, industry_group) pair is limited by `cumulative_max` (see limits below)
- On merge, old articles beyond the cap are trimmed (FIFO — keep newest)

---

## Industry Group Size-Based Limits

Industry groups are binned by number of constituent companies. Each bucket has a **per-run limit** (max articles per ticker per collection run) and a **cumulative max** (max total articles per (ticker, IG) pair).

| IG Company Count | Per-Run Limit | Cumulative Max |
|---|---|---|
| 1–5 | 10 | 150 |
| 6–10 | 6 | 100 |
| 11–30 | 4 | 60 |
| 31+ | 2 | 30 |

---

## Dataset Statistics

### Overall

| Metric | Value |
|---|---|
| Total articles | 1,702 |
| Unique tickers | 501 |
| Unique sectors | 11 |
| Unique industry groups | 25 |
| Collection date | 2026-05-31 (single day) |

### By Sector

| Sector | Articles | Industry Groups |
|---|---|---|
| Information Technology | 283 | 3 |
| Financials | 221 | 3 |
| Industrials | 203 | 3 |
| Consumer Discretionary | 197 | 4 |
| Consumer Staples | 164 | 3 |
| Health Care | 161 | 2 |
| Real Estate | 132 | 2 |
| Materials | 104 | 1 |
| Communication Services | 95 | 2 |
| Energy | 80 | 1 |
| Utilities | 62 | 1 |

### By Industry Group

| Industry Group | Articles | Tickers | Avg/Ticker |
|---|---|---|---|
| Software & Services | 116 | 29 | 4.0 |
| Equity Real Estate Investment Trusts (REITs) | 113 | 29 | 3.9 |
| Capital Goods | 108 | 54 | 2.0 |
| Materials | 104 | 26 | 4.0 |
| Technology Hardware & Equipment | 98 | 25 | 3.9 |
| Insurance | 89 | 23 | 3.9 |
| Pharmaceuticals, Biotechnology & Life Sciences | 89 | 23 | 3.9 |
| Food, Beverage & Tobacco | 81 | 21 | 3.9 |
| Energy | 80 | 21 | 3.8 |
| Financial Services | 80 | 40 | 2.0 |
| Health Care Equipment & Services | 72 | 36 | 2.0 |
| Consumer Services | 69 | 18 | 3.8 |
| Semiconductors & Semiconductor Equipment | 69 | 18 | 3.8 |
| Media & Entertainment | 63 | 18 | 3.5 |
| Utilities | 62 | 31 | 2.0 |
| Consumer Discretionary Distribution & Retail | 57 | 15 | 3.8 |
| Banks | 52 | 13 | 4.0 |
| Commercial & Professional Services | 48 | 12 | 4.0 |
| Transportation | 47 | 13 | 3.6 |
| Consumer Staples Distribution & Retail | 45 | 8 | 5.6 |
| Consumer Durables & Apparel | 40 | 11 | 3.6 |
| Household & Personal Products | 38 | 7 | 5.4 |
| Telecommunication Services | 32 | 4 | 8.0 |
| Automobiles & Components | 31 | 4 | 7.8 |
| Real Estate Management & Development | 19 | 2 | 9.5 |

### Article Length

| Metric | Value |
|---|---|
| Min | 107 chars |
| Max | 59,657 chars |
| Average | ~3,060 chars |

---

## Schema

| Column | Type | Description |
|---|---|---|
| `article` | string | Full article body text |
| `company_name` | string | Official company name |
| `ticker` | string | Ticker symbol |
| `sector` | string | GICS sector |
| `industry_group` | string | GICS industry group |
| `collected_at` | datetime | ISO timestamp of collection (UTC) |

---

## Files

| File | Description |
|---|---|
| `datasets/news.csv` | Final aggregated dataset — 1,702 articles, 501 tickers, 11 sectors |
| `load_data/load_yfinance.py` | Collection script — yfinance → two-pass filter → merge → CSV |
| `IC2/config/class.yaml` | GICS hierarchy: sector → industry_group → ticker:company |
| `IC2/config/snp500.yaml` | Fallback company names for tickers |
