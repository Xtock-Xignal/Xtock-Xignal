from __future__ import annotations

import datetime as dt
from typing import Any, Optional

import pandas as pd


def infer_base_date_from_tweet_created_at(created_at: str) -> dt.date:
    value = created_at.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    if len(value) == 19:
        value += "+00:00"
    return dt.datetime.fromisoformat(value).date()


def _first_scalar(value: Any):
    if hasattr(value, "iloc"):
        return value.iloc[0]
    return value


def normalize_price_history(frame: pd.DataFrame) -> list[dict]:
    if frame is None or frame.empty:
        return []

    rows = frame.reset_index()
    date_col = rows.columns[0]
    rows[date_col] = pd.to_datetime(rows[date_col], errors="coerce")

    records = []
    for _, row in rows.iterrows():
        date_value = row[date_col]
        date_str = date_value.strftime("%Y-%m-%d") if hasattr(date_value, "strftime") else str(date_value)[:10]
        records.append(
            {
                "date": date_str,
                "open": float(_first_scalar(row["Open"])),
                "high": float(_first_scalar(row["High"])),
                "low": float(_first_scalar(row["Low"])),
                "close": float(_first_scalar(row["Close"])),
                "volume": int(_first_scalar(row["Volume"])),
            }
        )
    return records


def calculate_next_day_return_from_prices(frame: pd.DataFrame, symbol: str, base_date: dt.date) -> Optional[dict]:
    if frame is None or frame.empty or len(frame) < 2:
        return None

    rows = frame.reset_index()
    date_col = rows.columns[0]
    rows[date_col] = pd.to_datetime(rows[date_col], errors="coerce").dt.date
    rows = rows.sort_values(date_col).reset_index(drop=True)

    candidates = rows[rows[date_col] <= base_date]
    if candidates.empty:
        return None

    base_idx = candidates.index[-1]
    next_idx = base_idx + 1
    if next_idx >= len(rows):
        return None

    base_row = rows.loc[base_idx]
    next_row = rows.loc[next_idx]
    base_close = float(_first_scalar(base_row["Close"]))
    next_close = float(_first_scalar(next_row["Close"]))

    return {
        "symbol": symbol.upper(),
        "base_date": base_row[date_col].isoformat(),
        "base_close": base_close,
        "next_date": next_row[date_col].isoformat(),
        "next_close": next_close,
        "next_day_return": (next_close - base_close) / base_close * 100.0,
    }


def build_stock_points(prices: list[dict]) -> list[dict]:
    return [
        {
            "date": item["date"][5:] if len(item["date"]) >= 10 else item["date"],
            "price": round(float(item["close"]), 2),
            "change": 0 if index == 0 else round((float(item["close"]) - float(prices[index - 1]["close"])) / float(prices[index - 1]["close"]) * 100, 2),
        }
        for index, item in enumerate(prices)
    ]


def resolve_symbol(text: str, name_to_ticker: dict[str, str]) -> tuple[str, str]:
    query = text.strip()
    if not query:
        return "AAPL", "Apple"

    upper_query = query.upper()
    if upper_query in name_to_ticker:
        return name_to_ticker[upper_query], upper_query.title()

    for name, ticker in name_to_ticker.items():
        if upper_query in name.upper() or name.upper() in upper_query:
            return ticker, name.title()

    cleaned = "".join(ch for ch in upper_query if ch.isalnum() or ch in ".-")
    if 1 <= len(cleaned) <= 6:
        return cleaned, cleaned

    return "AAPL", query


def estimate_sentiment(text: str) -> dict:
    lower = text.lower()
    positive_words = ("good", "great", "up", "gain", "growth", "beat", "surge", "positive", "buy")
    negative_words = ("bad", "down", "loss", "miss", "fall", "drop", "negative", "sell", "risk")
    score = sum(word in lower for word in positive_words) - sum(word in lower for word in negative_words)
    if score > 0:
        return {"sentiment": "Positive", "confidence": min(0.95, 0.55 + score * 0.1)}
    if score < 0:
        return {"sentiment": "Negative", "confidence": min(0.95, 0.55 + abs(score) * 0.1)}
    return {"sentiment": "Neutral", "confidence": 0.5}
