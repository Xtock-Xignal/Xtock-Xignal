import os
import re
import json
from fastapi import APIRouter, Query
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
from google import genai

# 라우터 설정
router = APIRouter()

# MongoDB 연결 설정 (라우터 레벨에서 간단하게 연결)
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI", "mongodb://xtock-mongodb:27017")
client = MongoClient(MONGO_URI)
db = client["xtock_xignal"]
collection = db["financial_terms"]

def initialize_db():
    if collection.count_documents({}) == 0:
        print("[System] Database is empty. Starting auto-recovery from JSON...")
        
        # Docker 환경을 고려한 다중 경로 탐색
        paths_to_try = [
            os.path.join(os.getcwd(), "json", "seed.json"),
            os.path.join(os.getcwd(), "backend", "json", "seed.json"),
            "/app/json/seed.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "json", "seed.json")
        ]
        
        loaded = False
        for path in paths_to_try:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        initial_data = json.load(f)
                    
                    if initial_data:
                        collection.insert_many(initial_data)
                        print(f"[System] Successfully inserted {len(initial_data)} basic terms from {path}.")
                        loaded = True
                        break
                except Exception as e:
                    print(f"[Error] Failed to read or parse JSON at {path}: {str(e)}")
        
        if not loaded:
            print("[Warning] seed.json not found in any expected paths. Skipping auto-recovery.")

initialize_db()

GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

# 프론트엔드에서 받을 데이터 형식 (뉴스 기사 텍스트)
class ScanRequest(BaseModel):
    text: str

@router.post("/scan")
def scan_financial_terms(request: ScanRequest):
    text = request.text
    matched_terms = []
    
    # 1. DB에서 모든 용어 가져오기 (추후 Redis 캐싱 도입 가능)
    all_terms = list(collection.find({}, {"_id": 0}))
    
    # 2. 기사 텍스트 안에 우리 용어가 있는지 무자비하게 스캔
    for term in all_terms:
        en_term = term.get("en_term", "")
        ko_term = term.get("ko_term", "")
        
        is_matched = False
        
        # 영어 원문 매칭 (대소문자 무시, 단어 단위 매칭을 위해 정규식 \b 사용)
        if en_term:
            # 예: FOMC를 찾을 때 FOMCs 같은 건 안 걸리게 정확한 단어만 매칭
            pattern = r'\b' + re.escape(en_term) + r'\b'
            if re.search(pattern, text, re.IGNORECASE):
                is_matched = True
                
        # 한글 번역본 매칭 (한국어 기사일 경우 대비)
        if ko_term and ko_term in text:
            is_matched = True
            
        # 매칭된 단어면 결과 리스트에 추가
        if is_matched:
            # hit_count(조회수)를 1 올려주는 센스 로직
            collection.update_one(
                {"en_term": en_term},
                {"$inc": {"hit_count": 1}}
            )
            matched_terms.append(term)
            
    return {"matched_terms": matched_terms}

@router.get("/search")
async def search_term(keyword: str = Query(..., description="검색할 단어")):
    # 1. DB 검색
    query = {
        "$or": [
            {"en_term": {"$regex": f"^{keyword}$", "$options": "i"}},
            {"ko_term": {"$regex": f"^{keyword}$", "$options": "i"}}
        ]
    }
    
    term_data = collection.find_one(query, {"_id": 0})

    db_definition = None
    if term_data:
        db_definition = term_data.get("explanation") or term_data.get("description")

    en_term_db = term_data.get("en_term", "") if term_data else ""
    ko_term_db = term_data.get("ko_term", "") if term_data else ""

    has_korean = bool(re.search(r'[가-힣]', keyword))

    if term_data and db_definition and (ko_term_db or has_korean):
        if en_term_db:
            collection.update_one({"en_term": en_term_db}, {"$inc": {"hit_count": 1}})
        return {
            "found": True, 
            "term": f"{en_term_db} ({ko_term_db})" if ko_term_db else en_term_db,
            "definition": db_definition, 
            "source": "DB",
            "en_term": en_term_db,
            "ko_term": ko_term_db
        }
    
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return {"found": False, "term": keyword, "definition": "API Key Error", "source": "AI Error"}
        
    try:
        print(f"[Info] Requesting strict JSON definition for: {keyword}")
        
        # 1. 최신 SDK Client 생성
        client = genai.Client(api_key=api_key)
            
        # 프롬프트를 명확한 JSON 스키마 형태로 변경
        prompt = f"""
        Provide information about the financial term '{keyword}'.
        You MUST output a valid JSON object strictly matching this schema:
        {{
            "en_term": "The standard English term (e.g., The Federal Reserve)",
            "ko_term": "The standard, shortest Korean translation noun ONLY (e.g., 연방준비제도). Do not use prefixes like 미국.",
            "definition": "Explain the term in exactly 3 sentences using a relatable everyday analogy. This field MUST BE WRITTEN ENTIRELY IN KOREAN (한국어)."
        }}
        """
            
        # 2. 최신 SDK API 호출 문법 적용 및 JSON 강제화 설정 (config 사용)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        
        ai_result = json.loads(response.text.strip())
        
        ai_en_term = ai_result.get("en_term", keyword)
        ai_ko_term = ai_result.get("ko_term", "")
        ai_definition = ai_result.get("definition", "")

        if term_data:
            collection.update_one(
                {"en_term": term_data.get("en_term")},
                {"$set": {
                    "description": ai_definition if not db_definition else db_definition,
                    "ko_term": ai_ko_term,
                    "en_term": ai_en_term
                }, "$inc": {"hit_count": 1}}
            )
            print(f"[Info] Healed existing term with ko_term: {ai_ko_term}")
        else:
            new_term_doc = {
                "en_term": ai_en_term,
                "ko_term": ai_ko_term,
                "description": ai_definition,
                "hit_count": 1,
                "is_ai_generated": True
            }
            collection.insert_one(new_term_doc)
            print(f"[Info] Saved new term: {ai_en_term} ({ai_ko_term})")
            
        display_term = f"{ai_en_term} ({ai_ko_term})" if ai_ko_term else ai_en_term
            
        return {
            "found": True,
            "term": display_term,
            "definition": ai_definition,
            "source": "AI",
            "en_term": ai_en_term,
            "ko_term": ai_ko_term
        }
        
    except Exception as e:
        print(f"[Error] Gemini API or JSON parse failed. Reason: {str(e)}")
        if term_data:
            return {"found": True, "term": keyword, "definition": term_data.get("ko_term", "DB Error"), "source": "DB (Partial)"}
        return {"found": False, "term": keyword, "definition": "Communication Error", "source": "AI Error"}
    
@router.get("/seed")
def seed_database():
    """JSON 파일에서 데이터를 읽어와 DB를 강제 초기화하는 엔드포인트"""
    try:
        # 1. 기존 데이터 모두 삭제 (백지화)
        collection.delete_many({})
        
        # 2. JSON 파일 경로 탐색
        paths_to_try = [
            os.path.join(os.getcwd(), "json", "seed.json"),
            os.path.join(os.getcwd(), "backend", "json", "seed.json"),
            "/app/json/seed.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "json", "seed.json")
        ]
        
        for path in paths_to_try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    initial_data = json.load(f)
                
                if initial_data:
                    collection.insert_many(initial_data)
                    return {
                        "status": "success", 
                        "message": f"{len(initial_data)}개의 기본 용어가 DB에 성공적으로 덮어쓰기 되었습니다.", 
                        "path": path
                    }
        
        return {"status": "error", "message": "어떤 경로에서도 seed.json 파일을 찾을 수 없습니다."}
    except Exception as e:
        return {"status": "error", "message": f"DB 초기화 중 오류 발생: {str(e)}"}