from __future__ import annotations

from typing import Callable, Dict, List


def normalize_query_to_ticker(raw_query: str, name_to_ticker: Dict[str, str]) -> str:
    query = raw_query.strip().upper()
    return name_to_ticker.get(query, query)


async def get_recent_status(
    payload,
    name_to_ticker: Dict[str, str],
    stock_history_fn: Callable[[str, int], list],
):
    ticker = normalize_query_to_ticker(payload.text, name_to_ticker)
    
    stock_data = stock_history_fn(ticker, 20)

    return {
        "found": True,
        "symbol": ticker,
        "stock_data": stock_data,
    }
