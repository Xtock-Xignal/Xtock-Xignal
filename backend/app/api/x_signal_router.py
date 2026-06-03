from __future__ import annotations

import datetime as dt
import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services import x_signal_service


class TweetImpactRequest(BaseModel):
    symbol: str
    tweet_created_at: str
    tweet_id: Optional[str] = None
    tweet_text: Optional[str] = None


class TextRequest(BaseModel):
    text: str


def create_x_signal_router(name_to_ticker, yf_module, tweet_impact_collection=None):
    router = APIRouter()

    async def call_x_recent_search(query: str, max_results: int = 10, next_token: Optional[str] = None):
        bearer_token = os.getenv("X_BEARER_TOKEN") or os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer_token:
            raise HTTPException(
                status_code=503,
                detail="X API token is not configured. Set X_BEARER_TOKEN or TWITTER_BEARER_TOKEN.",
            )

        params = {
            "query": query,
            "max_results": max_results,
            "tweet.fields": "created_at,author_id,public_metrics,lang",
        }
        if next_token:
            params["next_token"] = next_token

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://api.x.com/2/tweets/search/recent",
                headers={"Authorization": f"Bearer {bearer_token}"},
                params=params,
            )

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail={"msg": "X API error", "body": response.text})
        return response.json()

    def download_price_history(symbol: str, start: str, end: str, interval: str = "1d"):
        return yf_module.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            group_by="column",
            auto_adjust=False,
            progress=False,
        )

    def calculate_next_day_return(symbol: str, date_str: str):
        base_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        frame = download_price_history(
            symbol,
            (base_date - dt.timedelta(days=7)).strftime("%Y-%m-%d"),
            (base_date + dt.timedelta(days=7)).strftime("%Y-%m-%d"),
        )
        return x_signal_service.calculate_next_day_return_from_prices(frame, symbol, base_date)

    def save_tweet_impact(doc: dict):
        if tweet_impact_collection is None:
            return
        key = {"tweet_id": doc["tweet_id"]} if doc.get("tweet_id") else {"symbol": doc.get("symbol"), "base_date": doc.get("base_date")}
        try:
            tweet_impact_collection.update_one(key, {"$set": doc}, upsert=True)
        except Exception as exc:
            print(f"[tweet-impact] MongoDB save skipped: {exc}")

    @router.get("/api/tweets")
    async def get_tweets(
        q: str = Query(..., description="X recent search query"),
        max_results: int = Query(10, ge=10, le=100),
        next_token: Optional[str] = Query(None),
    ):
        data = await call_x_recent_search(q, max_results=max_results, next_token=next_token)
        return {"query": q, "max_results": max_results, "raw": data}

    @router.get("/api/price")
    def get_price_history(symbol: str, start: str, end: str):
        frame = download_price_history(symbol, start, end)
        return {
            "symbol": symbol.upper(),
            "start": start,
            "end": end,
            "prices": x_signal_service.normalize_price_history(frame),
        }

    @router.get("/api/next-return")
    def get_next_day_return(symbol: str, date: str):
        result = calculate_next_day_return(symbol, date)
        if result is None:
            raise HTTPException(status_code=404, detail="Not enough data to compute return")
        return result

    @router.post("/api/tweet-impact")
    def tweet_impact(payload: TweetImpactRequest):
        try:
            base_date = x_signal_service.infer_base_date_from_tweet_created_at(payload.tweet_created_at)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid tweet_created_at format: {exc}") from exc

        result = calculate_next_day_return(payload.symbol, base_date.strftime("%Y-%m-%d"))
        if result is None:
            raise HTTPException(status_code=404, detail="Not enough data to compute return for this tweet")

        doc = {
            "symbol": payload.symbol.upper(),
            "tweet_id": payload.tweet_id,
            "tweet_text": payload.tweet_text,
            "tweet_created_at": payload.tweet_created_at,
            **result,
            "sentiment": None,
            "matches": [],
        }
        save_tweet_impact(doc)
        return doc

    @router.post("/api/match-company")
    def match_company(payload: TextRequest):
        symbol, display_name = x_signal_service.resolve_symbol(payload.text, name_to_ticker)
        end_date = dt.datetime.now().date()
        start_date = end_date - dt.timedelta(days=21)
        frame = download_price_history(symbol, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))
        prices = x_signal_service.normalize_price_history(frame)
        stock_data = x_signal_service.build_stock_points(prices)
        if not stock_data:
            raise HTTPException(status_code=404, detail=f"No price history found for {symbol}")

        latest = stock_data[-1]["price"]
        first = stock_data[0]["price"]
        trend = "Positive" if latest >= first else "Negative"
        return {
            "input_text": payload.text,
            "matches": [
                {
                    "symbol": symbol,
                    "score": 0.8,
                    "name": display_name,
                    "financial_summary": f"{symbol} 최근 가격 흐름을 기준으로 초보자가 이해하기 쉽게 요약했습니다.",
                    "tweet": {
                        "author": "XTock Xignal",
                        "author_id": "X",
                        "handle": "xtock",
                        "time": "최근",
                        "text": f"{display_name}({symbol}) 관련 검색어를 가격 흐름과 함께 분석했습니다.",
                        "sentiment": trend,
                        "score": 0.75,
                    },
                    "stockData": stock_data,
                    "postIndex": max(0, len(stock_data) // 2),
                }
            ],
            "note": "Matched by ticker/name and recent yfinance price history.",
        }

    @router.post("/api/sentiment")
    def analyze_sentiment(payload: TextRequest):
        return {"input_text": payload.text, **x_signal_service.estimate_sentiment(payload.text)}

    return router
