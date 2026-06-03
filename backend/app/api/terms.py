from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import APIRouter, Query
from google import genai
from pydantic import BaseModel
from pymongo import MongoClient


router = APIRouter()

load_dotenv()

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://xtock-mongodb:27017"
MONGODB_NAME = os.getenv("MONGODB_NAME", "xtock_xignal")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGODB_NAME]
collection = db["financial_terms"]


class ScanRequest(BaseModel):
    text: str


def _seed_paths() -> list[Path]:
    base_dir = Path(__file__).resolve().parents[2]
    cwd = Path.cwd()
    return [
        cwd / "json" / "seed.json",
        cwd / "backend" / "json" / "seed.json",
        Path("/app/json/seed.json"),
        base_dir / "json" / "seed.json",
    ]


def initialize_db() -> None:
    if collection.count_documents({}) > 0:
        return

    for path in _seed_paths():
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as file:
                initial_data = json.load(file)
            if initial_data:
                collection.insert_many(initial_data)
                print(f"[terms] inserted {len(initial_data)} seed terms from {path}")
                return
        except Exception as exc:
            print(f"[terms] failed to load seed terms from {path}: {exc}")

    print("[terms] seed.json not found; starting with an empty terms collection")


def _definition_from_doc(term_data: dict | None) -> str:
    if not term_data:
        return ""
    return (
        term_data.get("definition")
        or term_data.get("explanation")
        or term_data.get("description")
        or ""
    )


def _term_query(keyword: str) -> dict:
    escaped = re.escape(keyword.strip())
    return {
        "$or": [
            {"en_term": {"$regex": f"^{escaped}$", "$options": "i"}},
            {"ko_term": {"$regex": f"^{escaped}$", "$options": "i"}},
            {"aliases": {"$regex": f"^{escaped}$", "$options": "i"}},
        ]
    }


def _display_term(en_term: str, ko_term: str) -> str:
    if en_term and ko_term:
        return f"{en_term} ({ko_term})"
    return en_term or ko_term


initialize_db()


@router.post("/scan")
def scan_financial_terms(request: ScanRequest):
    text = request.text or ""
    matched_terms = []

    all_terms = list(collection.find({}, {"_id": 0}))
    for term in all_terms:
        en_term = (term.get("en_term") or "").strip()
        ko_term = (term.get("ko_term") or "").strip()
        aliases = term.get("aliases") or []
        terms_to_match = [en_term, ko_term, *aliases]

        is_matched = False
        for candidate in terms_to_match:
            if not candidate:
                continue
            if re.search(r"[가-힣]", candidate):
                if candidate in text:
                    is_matched = True
                    break
            else:
                pattern = r"\b" + re.escape(candidate) + r"\b"
                if re.search(pattern, text, re.IGNORECASE):
                    is_matched = True
                    break

        if is_matched:
            if en_term:
                collection.update_one({"en_term": en_term}, {"$inc": {"hit_count": 1}})
            matched_terms.append(term)

    return {"matched_terms": matched_terms}


@router.get("/search")
async def search_term(keyword: str = Query(..., description="Financial term to search")):
    keyword = keyword.strip()
    if not keyword:
        return {"found": False, "term": "", "definition": "", "source": "empty"}

    term_data = collection.find_one(_term_query(keyword), {"_id": 0})
    db_definition = _definition_from_doc(term_data)
    en_term_db = (term_data or {}).get("en_term", "")
    ko_term_db = (term_data or {}).get("ko_term", "")

    if term_data and db_definition:
        if en_term_db:
            collection.update_one({"en_term": en_term_db}, {"$inc": {"hit_count": 1}})
        return {
            "found": True,
            "term": _display_term(en_term_db, ko_term_db),
            "definition": db_definition,
            "source": "DB",
            "en_term": en_term_db,
            "ko_term": ko_term_db,
            "aliases": term_data.get("aliases", []),
        }

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return {
            "found": False,
            "term": keyword,
            "definition": "AI 용어 검색을 사용하려면 GEMINI_API_KEY 또는 GOOGLE_API_KEY가 필요합니다.",
            "source": "AI Error",
        }

    try:
        client = genai.Client(api_key=api_key)
        prompt = f"""
Provide information about the financial term "{keyword}".
Return a valid JSON object only:
{{
  "en_term": "standard English term",
  "ko_term": "short Korean translation",
  "definition": "Korean explanation in exactly 3 beginner-friendly sentences"
}}
"""
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        ai_result = json.loads(response.text.strip())
        ai_en_term = ai_result.get("en_term") or keyword
        ai_ko_term = ai_result.get("ko_term") or ""
        ai_definition = ai_result.get("definition") or ""

        collection.update_one(
            {"en_term": ai_en_term},
            {
                "$set": {
                    "en_term": ai_en_term,
                    "ko_term": ai_ko_term,
                    "definition": ai_definition,
                    "is_ai_generated": True,
                },
                "$inc": {"hit_count": 1},
            },
            upsert=True,
        )

        return {
            "found": True,
            "term": _display_term(ai_en_term, ai_ko_term),
            "definition": ai_definition,
            "source": "AI",
            "en_term": ai_en_term,
            "ko_term": ai_ko_term,
            "aliases": [],
        }
    except Exception as exc:
        print(f"[terms] AI term lookup failed: {exc}")
        return {
            "found": False,
            "term": keyword,
            "definition": "용어 검색 중 일시적인 오류가 발생했습니다.",
            "source": "AI Error",
        }


@router.get("/seed")
def seed_database():
    try:
        collection.delete_many({})
        for path in _seed_paths():
            if not path.exists():
                continue
            with path.open("r", encoding="utf-8") as file:
                initial_data = json.load(file)
            if initial_data:
                collection.insert_many(initial_data)
                return {
                    "status": "success",
                    "message": f"Inserted {len(initial_data)} terms.",
                    "path": str(path),
                }
        return {"status": "error", "message": "seed.json was not found."}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}
