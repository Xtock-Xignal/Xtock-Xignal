from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import market_service


class SearchRequest(BaseModel):
    text: str


def create_market_router(name_to_ticker, sp500_handles, call_x_recent_search, get_stock_price_history):
    router = APIRouter()

    @router.post("/api/recent-status")
    async def get_recent_status(payload: SearchRequest):
        return await market_service.get_recent_status(
            payload,
            name_to_ticker=name_to_ticker,
            sp500_handles=sp500_handles,
            search_fn=call_x_recent_search,
            stock_history_fn=get_stock_price_history,
        )

    return router
