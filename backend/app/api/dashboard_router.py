from __future__ import annotations

from fastapi import APIRouter

from app.services import dashboard_service


def create_dashboard_router(yf_module):
    router = APIRouter()

    @router.get("/api/dashboard/summary")
    def get_dashboard_summary():
        return dashboard_service.get_dashboard_summary(yf_module)

    return router
