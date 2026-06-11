from app.api.auth_router import create_auth_router
from app.api.dashboard_router import create_dashboard_router
from app.api.market_router import create_market_router
from app.api.portfolio_router import create_portfolio_router

__all__ = [
    "create_auth_router",
    "create_dashboard_router",
    "create_market_router",
    "create_portfolio_router",
]
