from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.industry_classifier_service import classify_industry


router = APIRouter()


class IndustryClassifyRequest(BaseModel):
    title: str = ""
    text: str


@router.post("/classify")
def classify_industry_endpoint(payload: IndustryClassifyRequest):
    return classify_industry(text=payload.text, title=payload.title)
