from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import market_service


class SearchRequest(BaseModel):
    text: str


def create_market_router(name_to_ticker, get_stock_price_history):
    router = APIRouter()

    @router.post("/api/recent-status")
    async def get_recent_status(payload: SearchRequest):
        return await market_service.get_recent_status(
            payload,
            name_to_ticker=name_to_ticker,
            stock_history_fn=get_stock_price_history,
        )

    return router
