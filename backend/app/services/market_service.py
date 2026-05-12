from __future__ import annotations

from typing import Callable, Dict, List


def normalize_query_to_ticker(raw_query: str, name_to_ticker: Dict[str, str]) -> str:
    query = raw_query.strip().upper()
    return name_to_ticker.get(query, query)


def resolve_twitter_query(
    ticker: str,
    sp500_handles: Dict[str, str],
) -> str:
    if ticker in sp500_handles:
        return sp500_handles[ticker]
    return f"${ticker} OR {ticker}"


async def get_recent_status(
    payload,
    name_to_ticker: Dict[str, str],
    sp500_handles: Dict[str, str],
    search_fn: Callable[[str, int], List[dict]],
    stock_history_fn: Callable[[str, int], list],
):
    ticker = normalize_query_to_ticker(payload.text, name_to_ticker)
    twitter_query = resolve_twitter_query(ticker, sp500_handles)

    tweets = await search_fn(twitter_query, 3)
    stock_data = stock_history_fn(ticker, 20)

    return {
        "found": True,
        "symbol": ticker,
        "tweets": tweets,
        "stock_data": stock_data,
    }
