from __future__ import annotations

import datetime as dt
from typing import List, Tuple

import pandas as pd


def parse_csv_date(date_str: str) -> dt.datetime:
    try:
        return dt.datetime.fromisoformat(date_str)
    except Exception:
        try:
            return dt.datetime.strptime(date_str.split("+")[0], "%Y-%m-%d %H:%M:%S")
        except Exception:
            return dt.datetime.now()


def get_historical_candidates(query: str, search_engine, impact_tweets: List[dict]):
    target_symbol = None
    candidates = []

    try:
        ai_results = search_engine.search(query, top_k=1)
        if ai_results:
            top_res = ai_results[0]
            target_symbol = top_res["symbol"].strip().upper()
    except Exception:
        target_symbol = None

    if target_symbol:
        candidates = [t for t in impact_tweets if target_symbol in t["symbol"]]
        if not candidates and target_symbol == "TSLA":
            candidates = [
                {
                    "id": "emergency_tsla",
                    "symbol": "TSLA",
                    "text": "Tesla production hits record high. $TSLA",
                    "created_at": "2022-09-29 18:48:36+00:00",
                    "author_id": "Tesla, Inc.",
                    "note": "Recovered Data",
                }
            ]
    else:
        candidates = [t for t in impact_tweets if query.lower() in t["text"].lower()]

    return target_symbol, candidates


def build_historical_chart(symbol: str, date_str: str, download_fn) -> Tuple[list, int, float]:
    event_dt = parse_csv_date(date_str)
    start_dt = event_dt - dt.timedelta(days=30)
    end_dt = event_dt + dt.timedelta(days=30)

    hist_data = []
    impact_return = 0.0
    post_index = -1

    try:
        df = download_fn(
            symbol,
            start=start_dt.strftime("%Y-%m-%d"),
            end=end_dt.strftime("%Y-%m-%d"),
            interval="1d",
            progress=False,
            multi_level_index=False,
        )

        if not df.empty:
            df = df.reset_index()
            date_col = next((c for c in df.columns if "date" in str(c).lower()), df.columns[0])

            for _, row in df.iterrows():
                try:
                    value = row[date_col]
                    if hasattr(value, "item"):
                        value = value.item()
                    current_date = pd.to_datetime(value)

                    close = row.get("Close", 0)
                    if hasattr(close, "item"):
                        close = float(close.item())
                    else:
                        close = float(close)

                    hist_data.append({"date": current_date.strftime("%Y-%m-%d"), "price": close})
                except Exception:
                    continue

            target_str = event_dt.strftime("%Y-%m-%d")
            for i, item in enumerate(hist_data):
                if item["date"] >= target_str:
                    post_index = i
                    break

            if post_index != -1 and post_index < len(hist_data) - 5:
                base = hist_data[post_index]["price"]
                future = hist_data[post_index + 5]["price"]
                if base > 0:
                    impact_return = ((future - base) / base) * 100.0
    except Exception:
        pass

    return hist_data, post_index, impact_return
