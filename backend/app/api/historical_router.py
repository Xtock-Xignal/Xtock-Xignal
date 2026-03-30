from __future__ import annotations

import random

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import historical_service


class SearchRequest(BaseModel):
    text: str


class ChartRequest(BaseModel):
    symbol: str
    date: str


def create_historical_router(search_engine, impact_tweets_ref, stock_price_downloader):
    router = APIRouter()

    @router.post("/api/historical-impact")
    def get_historical_impact(payload: SearchRequest):
        target_symbol, candidates = historical_service.get_historical_candidates(
            payload.text.strip(),
            search_engine,
            impact_tweets_ref,
        )

        if not candidates:
            return {"found": False, "msg": f"'{payload.text}'와 관련된 데이터를 찾을 수 없습니다."}

        random.shuffle(candidates)
        final_candidates = candidates[:20]
        final_candidates.sort(key=lambda x: x["created_at"], reverse=True)
        return {
            "found": True,
            "symbol": target_symbol if target_symbol else "KEYWORD",
            "candidates": final_candidates,
        }

    @router.post("/api/historical-chart")
    def get_historical_chart(payload: ChartRequest):
        hist_data, post_index, impact_return = historical_service.build_historical_chart(
            payload.symbol,
            payload.date,
            stock_price_downloader,
        )
        return {
            "stock_data": hist_data,
            "post_index": post_index,
            "impact_return": impact_return,
        }

    return router
