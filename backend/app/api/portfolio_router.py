from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import portfolio_service


class PortfolioAdd(BaseModel):
    email: str
    symbol: str
    price: float
    quantity: int = 1


class PortfolioList(BaseModel):
    email: str


class PortfolioRemove(BaseModel):
    email: str
    symbol: str


def create_portfolio_router(get_user_collection):
    router = APIRouter()

    @router.post("/api/portfolio/list")
    def get_portfolio(req: PortfolioList):
        users_col = get_user_collection()
        return portfolio_service.get_portfolio(users_col, req.email)

    @router.post("/api/portfolio/add")
    def add_portfolio(req: PortfolioAdd):
        users_col = get_user_collection()
        return portfolio_service.add_portfolio_item(
            users_col, req.email, req.symbol, req.price, req.quantity
        )

    @router.post("/api/portfolio/remove")
    def remove_portfolio(req: PortfolioRemove):
        users_col = get_user_collection()
        return portfolio_service.remove_portfolio_item(users_col, req.email, req.symbol)

    return router
