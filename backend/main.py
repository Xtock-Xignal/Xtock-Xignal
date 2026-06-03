import os
import re
import datetime as dt
from typing import Optional, List
from contextlib import asynccontextmanager
import json
import csv
import httpx
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pymongo import MongoClient
from passlib.context import CryptContext
import random

from app.api.news import router as news_router
from app.api.dashboard_router import create_dashboard_router
from app.api.industry_router import router as industry_router
from app.api.terms import router as terms_router
from app.api.x_signal_router import create_x_signal_router
from app.services import backtest_service
from chart.router import router as chart_router
from simulation.router import router as simulation_router
from search_service import search_engine

load_dotenv()

BEARER_TOKEN = os.getenv("BEARER_TOKEN") or os.getenv("TWEETER_BEARER_TOKEN")
if not BEARER_TOKEN:
    print("Warning: BEARER_TOKEN is not set in .env")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "stock_tweets.csv")
SP500_HANDLES_PATH = os.path.join(BASE_DIR, "sp500_handles.json")


IMPACT_TWEETS = []
SP500_HANDLES = {}

NAME_TO_TICKER = {
    # ---------------------------------------------------------
    # 1. Magnificent 7 & Big Tech (가장 검색량 많음)
    # ---------------------------------------------------------
    "TESLA": "TSLA", "테슬라": "TSLA", "일론머스크": "TSLA",
    "APPLE": "AAPL", "애플": "AAPL", "아이폰": "AAPL",
    "MICROSOFT": "MSFT", "마이크로소프트": "MSFT", "마소": "MSFT",
    "NVIDIA": "NVDA", "엔비디아": "NVDA", "엔비다": "NVDA",
    "GOOGLE": "GOOGL", "구글": "GOOGL", "ALPHABET": "GOOGL", "알파벳": "GOOGL", "유튜브": "GOOGL",
    "AMAZON": "AMZN", "아마존": "AMZN",
    "META": "META", "메타": "META", "FACEBOOK": "META", "페이스북": "META", "인스타그램": "META",
    "NETFLIX": "NFLX", "넷플릭스": "NFLX", "넷플": "NFLX",

    # ---------------------------------------------------------
    # 2. 반도체 & 하드웨어 (Semiconductors)
    # ---------------------------------------------------------
    "AMD": "AMD", "암드": "AMD", "에이엠디": "AMD",
    "INTEL": "INTC", "인텔": "INTC",
    "TSMC": "TSM", # (ADR로 상장되어 있어 미국 주식 거래 가능)
    "BROADCOM": "AVGO", "브로드컴": "AVGO",
    "QUALCOMM": "QCOM", "퀄컴": "QCOM",
    "MICRON": "MU", "마이크론": "MU",
    "TEXAS INSTRUMENTS": "TXN", "텍사스인스트루먼트": "TXN",
    "APPLIED MATERIALS": "AMAT", "어플라이드머티리얼즈": "AMAT",
    "LAM RESEARCH": "LRCX", "램리서치": "LRCX",
    "ANALOG DEVICES": "ADI", "아날로그디바이스": "ADI",

    # ---------------------------------------------------------
    # 3. 금융 & 결제 (Financials)
    # ---------------------------------------------------------
    "JPMORGAN": "JPM", "제이피모건": "JPM", "JPM": "JPM",
    "BERKSHIRE": "BRK.B", "버크셔": "BRK.B", "버크셔해서웨이": "BRK.B", "워렌버핏": "BRK.B",
    "VISA": "V", "비자": "V",
    "MASTERCARD": "MA", "마스터카드": "MA", "마카": "MA",
    "BANK OF AMERICA": "BAC", "뱅크오브아메리카": "BAC", "뱅오아": "BAC",
    "WELLS FARGO": "WFC", "웰스파고": "WFC",
    "GOLDMAN SACHS": "GS", "골드만삭스": "GS",
    "MORGAN STANLEY": "MS", "모건스탠리": "MS",
    "CITIGROUP": "C", "씨티그룹": "C", "시티": "C",
    "PAYPAL": "PYPL", "페이팔": "PYPL",
    "BLOCK": "SQ", "스퀘어": "SQ", "블록": "SQ",

    # ---------------------------------------------------------
    # 4. 소비재 & 유통 (Consumer)
    # ---------------------------------------------------------
    "COCA COLA": "KO", "COKE": "KO", "코카콜라": "KO", "코크": "KO",
    "PEPSI": "PEP", "PEPSICO": "PEP", "펩시": "PEP",
    "MCDONALDS": "MCD", "맥도날드": "MCD", "맥날": "MCD",
    "STARBUCKS": "SBUX", "스타벅스": "SBUX", "스벅": "SBUX",
    "NIKE": "NKE", "나이키": "NKE",
    "WALMART": "WMT", "월마트": "WMT",
    "COSTCO": "COST", "코스트코": "COST",
    "HOME DEPOT": "HD", "홈디포": "HD",
    "PROCTER & GAMBLE": "PG", "P&G": "PG", "피앤지": "PG",
    "DISNEY": "DIS", "디즈니": "DIS",
    "CHIPOTLE": "CMG", "치폴레": "CMG",
    "LULULEMON": "LULU", "룰루레몬": "LULU",

    # ---------------------------------------------------------
    # 5. 헬스케어 (Healthcare)
    # ---------------------------------------------------------
    "ELI LILLY": "LLY", "일라이릴리": "LLY", "릴리": "LLY",
    "NOVO NORDISK": "NVO", "노보노디스크": "NVO",
    "JOHNSON & JOHNSON": "JNJ", "존슨앤존슨": "JNJ",
    "UNITEDHEALTH": "UNH", "유나이티드헬스": "UNH",
    "PFIZER": "PFE", "화이자": "PFE",
    "MERCK": "MRK", "머크": "MRK",
    "ABBVIE": "ABBV", "애브비": "ABBV",
    "MODERNA": "MRNA", "모더나": "MRNA",

    # ---------------------------------------------------------
    # 6. 자동차 & 산업 (Auto & Industrial)
    # ---------------------------------------------------------
    "FORD": "F", "포드": "F",
    "GM": "GM", "제너럴모터스": "GM", "지엠": "GM",
    "BOEING": "BA", "보잉": "BA",
    "LOCKHEED MARTIN": "LMT", "록히드마틴": "LMT",
    "CATERPILLAR": "CAT", "캐터필러": "CAT",
    "GE": "GE", "제너럴일렉트릭": "GE",
    "3M": "MMM", "쓰리엠": "MMM",
    "HONEYWELL": "HON", "하니웰": "HON",
    "UBER": "UBER", "우버": "UBER",

    # ---------------------------------------------------------
    # 7. 소프트웨어 & 보안 (Software & Cloud)
    # ---------------------------------------------------------
    "ADOBE": "ADBE", "어도비": "ADBE",
    "SALESFORCE": "CRM", "세일즈포스": "CRM",
    "ORACLE": "ORCL", "오라클": "ORCL",
    "IBM": "IBM", "아이비엠": "IBM",
    "PALANTIR": "PLTR", "팔란티어": "PLTR",
    "SNOWFLAKE": "SNOW", "스노우플레이크": "SNOW",
    "CROWDSTRIKE": "CRWD", "크라우드스트라이크": "CRWD",
    "PALO ALTO": "PANW", "팔로알토": "PANW",

    # ---------------------------------------------------------
    # 8. 에너지 (Energy)
    # ---------------------------------------------------------
    "EXXON": "XOM", "EXXON MOBIL": "XOM", "엑슨모빌": "XOM",
    "CHEVRON": "CVX", "쉐브론": "CVX",

    # ---------------------------------------------------------
    # 9. 기타 S&P 500 주요 기업 (자동 매핑용)
    # ---------------------------------------------------------
    "AT&T": "T", "T": "T",
    "VERIZON": "VZ", "버라이즌": "VZ",
    "COMCAST": "CMCSA", "컴캐스트": "CMCSA",
    "INTUIT": "INTU", "인튜이트": "INTU",
    "SERVICENOW": "NOW", "서비스나우": "NOW",
    "AIRBNB": "ABNB", "에어비앤비": "ABNB",
    "BOOKING": "BKNG", "부킹홀딩스": "BKNG",
    "MONSTER": "MNST", "몬스터": "MNST",
    "BLACKROCK": "BLK", "블랙록": "BLK",
    "BLACKSTONE": "BX", "블랙스톤": "BX",
    "DELTA": "DAL", "델타항공": "DAL",
    "UNITED AIRLINES": "UAL", "유나이티드항공": "UAL",
    "AMERICAN AIRLINES": "AAL", "아메리칸항공": "AAL",
    "FEDEX": "FDX", "페덱스": "FDX",
    "UPS": "UPS", "유피에스": "UPS",
    "TARGET": "TGT", "타겟": "TGT",
    "LOWES": "LOW", "로우스": "LOW",
    "CVS": "CVS", "씨브이에스": "CVS",
    "ATLASSIAN": "TEAM", "아틀라시안": "TEAM",
    "SHOPIFY": "SHOP", "쇼피파이": "SHOP",
    "COINBASE": "COIN", "코인베이스": "COIN",
    "ROBLOX": "RBLX", "로블록스": "RBLX",
    "UNITY": "U", "유니티": "U"
}

def parse_csv_date(date_str):
    """
    CSV의 '2022-09-29 23:41:16+00:00' 형식을 datetime 객체로 변환
    """
    try:
        # 1. 일반적인 ISO 포맷 시도
        return dt.datetime.fromisoformat(date_str)
    except:
        try:
            # 2. 파이썬 버전에 따라 fromisoformat이 다를 수 있으므로 수동 파싱
            # 포맷: YYYY-MM-DD HH:MM:SS+00:00
            return dt.datetime.strptime(date_str.split('+')[0], "%Y-%m-%d %H:%M:%S")
        except:
            # 3. 실패 시 오늘 날짜 반환 (에러 방지)
            return dt.datetime.now()

def load_data():
    """데이터 로드 및 AI 엔진 인덱싱"""
    global IMPACT_TWEETS, SP500_HANDLES
    
    # 1. CSV 로드
    if os.path.exists(CSV_PATH):
        try:
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                IMPACT_TWEETS = []
                
                # AI 검색을 위한 데이터 준비
                documents = []
                ids = []
                metadatas = []
                
                for i, row in enumerate(reader):
                    if i == 0 and "Date" in row[0]:
                        continue
                    if len(row) < 3: continue
                    
                    try:
                        date_str = row[0]
                        
                        # 행의 길이가 4개보다 많으면(쉼표로 인해 쪼개짐), 중간을 모두 텍스트로 합침
                        if len(row) > 4:
                            symbol = row[-2].strip().upper()
                            company = row[-1]
                            # row[1]부터 row[-2] 전까지가 텍스트
                            text = ",".join(row[1:-2]).replace('"', '').strip()
                        else:
                            # 일반적인 경우 (Date, Text, Symbol, Company)
                            text = row[1]
                            symbol = row[2].strip().upper()
                            company = row[3] if len(row) > 3 else "Unknown"
                        
                        # 심볼에 이상한 문자가 섞였는지 방어적 체크
                        if len(symbol) > 6 or " " in symbol:
                            continue

                        tweet_obj = {
                            "id": f"csv_{i}",
                            "symbol": symbol,
                            "text": text,
                            "created_at": date_str,
                            "author_id": company,
                            "note": f"Historical Event ({date_str[:10]})"
                        }
                        IMPACT_TWEETS.append(tweet_obj)
                        
                        # AI 엔진 데이터 (최대 5000개)
                        if i < 5000:
                            ids.append(tweet_obj["id"])
                            documents.append(f"{text} {symbol}")
                            metadatas.append({"symbol": symbol, "name": symbol})
                            
                    except Exception as parse_err:
                        # 파싱 에러난 행은 건너뜀
                        continue

            print(f"[Data] Loaded {len(IMPACT_TWEETS)} historical tweets from CSV.")
            
            # [디버깅] TSLA 데이터가 실제로 들어갔는지 확인
            tsla_count = sum(1 for t in IMPACT_TWEETS if t['symbol'] == 'TSLA')
            print(f"[Data Debug] 'TSLA' count in memory: {tsla_count}")
            
            # AI 엔진(ChromaDB)에 데이터 주입
            if search_engine.col_static and documents:
                print(f"[AI] Indexing {len(documents)} documents to Vector DB...")
                # 기존 데이터가 있으면 중복 방지를 위해 확인하거나, 간단히 try-except 처리
                try:
                    # 임베딩 생성 (search_service 내부 모델 사용)
                    embeddings = search_engine.model.encode(documents).tolist()
                    search_engine.col_static.upsert(
                        ids=ids,
                        embeddings=embeddings,
                        documents=documents,
                        metadatas=metadatas
                    )
                    print("[AI] Indexing Complete!")
                except Exception as e:
                    print(f"[AI] Indexing Warning: {e}")
                    
        except Exception as e:
            print(f"[Data] Failed to load CSV: {e}")
    else:
        print("[Data] Tweet.csv not found!")
    
    # 2. 핸들 로드
    if os.path.exists(SP500_HANDLES_PATH):
        try:
            with open(SP500_HANDLES_PATH, 'r', encoding='utf-8') as f:
                SP500_HANDLES = json.load(f)
            print(f"[Data] Loaded {len(SP500_HANDLES)} handles.")
        except: pass
    
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_NAME = os.getenv("MONGODB_NAME", "xtock")
MONGODB_COLLECTION_LOGS = "search_history"

mongo_client = None
search_log_col = None

if MONGODB_URI:
    try:
        mongo_client = MongoClient(MONGODB_URI)
        db = mongo_client[MONGODB_NAME]
        search_log_col = db[MONGODB_COLLECTION_LOGS]
        print("[DB] MongoDB Connected for Logging.")
    except Exception as e:
        print(f"[DB] Connection Failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # load_data()
    global mongo_client
    mongo_client = MongoClient("mongodb://xtock-mongodb:27017")
    print("XTock-Xignal Backend Starting")
    yield
    # print("XTock-Xignal Backend Shutting Down")
    if mongo_client:
        mongo_client.close()
    
app = FastAPI(
    title = "Xtock-Xignal Backend",
    description = "Backend API for Xtock-Xignal Service",
    version = "1.0.0",
    lifespan = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins =["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(news_router, prefix="/api/news")
app.include_router(industry_router, prefix="/api/industry")
app.include_router(chart_router)
app.include_router(simulation_router)
app.include_router(create_x_signal_router(NAME_TO_TICKER, yf))
app.include_router(create_dashboard_router(yf))
app.include_router(terms_router, prefix="/api/terms")

BacktestPosition = backtest_service.BacktestPosition
BacktestRequest = backtest_service.BacktestRequest
BacktestSymbolItem = backtest_service.BacktestSymbolItem


def _normalize_backtest_positions(payload: BacktestRequest):
    return backtest_service.normalize_backtest_positions(payload, NAME_TO_TICKER)


def _get_backtest_symbol_catalog():
    return backtest_service.get_backtest_symbol_catalog(NAME_TO_TICKER)


def _get_backtest_symbol_detail(symbol: str):
    catalog = _get_backtest_symbol_catalog()
    fallback_name = next((item.get("name") for item in catalog if item.get("symbol") == symbol.upper()), None)
    return backtest_service.get_backtest_symbol_detail(symbol, fallback_name=fallback_name)


def _load_backtest_prices(symbol: str, start_date: Optional[str] = None, end_date: Optional[str] = None):
    return backtest_service.load_backtest_prices(symbol, start_date, end_date)


def _run_single_backtest(symbol: str, payload: BacktestRequest):
    return backtest_service.run_single_ma_cross_backtest(
        symbol,
        payload,
        price_loader=_load_backtest_prices,
    )


@app.get("/api/backtest/symbols")
def list_backtest_symbols(query: str = "", limit: int = Query(default=20, ge=1, le=500)):
    needle = (query or "").strip().upper()
    items = _get_backtest_symbol_catalog()
    if needle:
        items = [
            item
            for item in items
            if needle in item.get("symbol", "").upper() or needle in item.get("name", "").upper()
        ]
    return {"items": items[:limit]}


@app.get("/api/backtest/symbol-info")
def get_backtest_symbol_info(symbol: str):
    detail = _get_backtest_symbol_detail(symbol)
    if not detail:
        return {"success": False, "msg": "티커를 확인할 수 없습니다."}
    return {"success": True, "item": detail}


@app.post("/api/backtest/run")
def run_backtest(payload: BacktestRequest):
    return backtest_service.run_ma_cross_backtest(
        payload,
        normalize_positions_fn=_normalize_backtest_positions,
        run_single_fn=_run_single_backtest,
        name_to_ticker=NAME_TO_TICKER,
    )

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_collection():
    return mongo_client["xtock_db"]["users"]

def find_user_doc_by_email(users_col, raw_email: str):
    """회원가입 시 이메일 대소문자가 섞여 저장될 수 있어 대소문자 무시로 조회합니다."""
    raw = (raw_email or "").strip()
    if not raw:
        return None
    u = users_col.find_one({"email": raw})
    if u:
        return u
    try:
        return users_col.find_one(
            {"email": {"$regex": f"^{re.escape(raw)}$", "$options": "i"}}
        )
    except re.error:
        return None

def get_simulation_collection():
    return mongo_client["xtock_db"]["simulation_states"]

# 데이터 검증용 Pydantic 모델
class UserSignup(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class SimulationStatePayload(BaseModel):
    email: str
    cash: float = 0
    holdings: dict = Field(default_factory=dict)
    trades: list = Field(default_factory=list)
    simulation_started: bool = False

class SimulationStateGetPayload(BaseModel):
    email: str

class SimulationPinSetPayload(BaseModel):
    email: str
    pin: str = Field(..., min_length=4, max_length=4)
    old_pin: Optional[str] = None

class SimulationPinVerifyPayload(BaseModel):
    email: str
    pin: str = Field(..., min_length=4, max_length=4)

class UserProfileUpdatePayload(BaseModel):
    email: str
    current_password: str
    username: Optional[str] = None
    new_email: Optional[str] = None
    new_password: Optional[str] = None

class UserDeletePayload(BaseModel):
    email: str
    current_password: str

class UserRewardsPayload(BaseModel):
    email: str

class UserQuizRewardPayload(BaseModel):
    email: str
    amount: float = 50

class UserAttendancePayload(BaseModel):
    email: str
    date: Optional[str] = None
    amount: float = 30

# 비밀번호 관련 함수
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

class ChartRequest(BaseModel):
    symbol: str
    date: str
    
class SearchRequest(BaseModel):
    text: str
    # 시뮬/차트용 일봉 개수(최근 N개). start_date/end_date가 주어지지 않았을 때 사용합니다.
    stock_history_days: Optional[int] = Field(default=None, ge=5, le=400)
    # YYYY-MM-DD 형식의 시작일/종료일(기간 조회용). 둘 다 필요합니다.
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def parse_iso_date(date_str: str) -> dt.date:
    """
    YYYY-MM-DD 문자열을 dt.date로 변환합니다.
    """
    # datetime.fromisoformat은 "YYYY-MM-DD" 외 포맷에 관대할 수 있어서,
    # 여기서는 명시적으로 포맷을 고정합니다.
    try:
        return dt.datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception as e:
        raise ValueError(f"Invalid date: {date_str}") from e

# ===========================================
# X API 호출 함수
# 과거 7일간의 트윗만 가져올 수 있기 때문에 모델 성능 및 웹 페이지 구성때는 잠시 주석 처리
async def call_x_recent_search(query: str, max_results: int = 10):
    if not BEARER_TOKEN:
        return get_fallback_tweets(query)    
    
    # X API 호출 (기본 주소 or 대체 주소)
    base_url = "https://api.x.com/2/tweets/search/recent"
    # base_url = "https://api.twitter.com/2/tweets/search/recent" # 필요시 변경
    
    headers = {"Authorization": f"Bearer {BEARER_TOKEN}"}

    final_query = f"({query}) -is:retweet"

    params = {
        "query": final_query,
        "max_results": max_results,
        "tweet.fields": "created_at,author_id,public_metrics,lang",
        "expansions": "author_id",
        "user.fields": "name,username"
    }
    try:        
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, headers=headers, params=params)

        if resp.status_code == 200:
            data = resp.json()
            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            result = []
            for t in tweets:
                author_info = users.get(t["author_id"], {})
                result.append({
                    "text": t["text"],
                    "author": author_info.get("name", "Unknown"),
                    "username": author_info.get("username", ""),
                    "date": t["created_at"].split("T")[0],
                    "created_at": t["created_at"]
                })
            return result
        else:
            return get_fallback_tweets(query)
    except:
        return get_fallback_tweets(query)
    
def get_fallback_tweets(query):
    today = dt.datetime.now().strftime("%Y-%m-%d")
    return [
        {"text": f"Latest market update regarding {query}. Analysts are watching closely.", "author": "MarketWatch", "username": "MarketWatch", "date": today},
        {"text": f"Breaking news: {query} shows significant movement today.", "author": "Bloomberg", "username": "Bloomberg", "date": today},
        {"text": "Investors are reacting to the latest earnings report.", "author": "CNBC", "username": "CNBC", "date": today}
    ]
    
    
def get_stock_price_history(symbol: str, days: int = 30):
    try:
        end_date = dt.datetime.now()
        # 일봉 `days`개를 확보하려면 주말·휴장을 감안해 달력 구간을 넉넉히 잡음
        cal_lookback = max(days + 100, int(days * 1.75))
        start_date = end_date - dt.timedelta(days=cal_lookback)
        df = yf.download(symbol, start=start_date, end=end_date, interval="1d", progress=False, multi_level_index=False)
        if df.empty: return []
        
        df = df.reset_index()
        date_col = 'Date' if 'Date' in df.columns else df.columns[0]
        
        records = []
        for _, row in df.iterrows():
            if pd.isna(row[date_col]): continue
            records.append({
                "date": pd.to_datetime(row[date_col]).strftime("%Y-%m-%d"),
                "open": float(row.get("Open", 0)),
                "high": float(row.get("High", 0)),
                "low": float(row.get("Low", 0)),
                "close": float(row.get("Close", 0)),
                "volume": int(row.get("Volume", 0))
            })
        return records[-days:]
    except: return []


def get_stock_price_history_range(symbol: str, start_date_str: str, end_date_str: str):
    """
    start_date ~ end_date (둘 다 포함) 기간의 OHLCV를 반환합니다.
    """
    try:
        start_d = parse_iso_date(start_date_str)
        end_d = parse_iso_date(end_date_str)

        if end_d < start_d:
            return []

        # yfinance의 end 파라미터는 일반적으로 "exclusive"에 가깝기 때문에
        # 종료일을 하루 더해서 마지막 거래일이 포함되도록 합니다.
        df = yf.download(
            symbol,
            start=start_d.isoformat(),
            end=(end_d + dt.timedelta(days=1)).isoformat(),
            interval="1d",
            progress=False,
            multi_level_index=False,
        )
        if df.empty:
            return []

        df = df.reset_index()
        date_col = 'Date' if 'Date' in df.columns else df.columns[0]

        records = []
        for _, row in df.iterrows():
            if pd.isna(row[date_col]):
                continue

            d_str = pd.to_datetime(row[date_col]).strftime("%Y-%m-%d")
            d_d = dt.datetime.strptime(d_str, "%Y-%m-%d").date()
            if d_d < start_d or d_d > end_d:
                continue

            records.append({
                "date": d_str,
                "open": float(row.get("Open", 0)),
                "high": float(row.get("High", 0)),
                "low": float(row.get("Low", 0)),
                "close": float(row.get("Close", 0)),
                "volume": int(row.get("Volume", 0)),
            })

        # yfinance 결과는 보통 날짜 오름차순이지만,
        # 혹시 몰라 날짜 기준으로 한 번 더 정렬합니다.
        records.sort(key=lambda r: r["date"])
        return records
    except Exception as e:
        print(f"[StockRange] Error: {e}")
        return []

# def infer_base_date_from_tweet_created_at(created_at: str) -> dt.date:
#     """트윗 작성 시간(ISO8601) -> 날짜(Date) 변환"""
#     s = created_at.strip()
#     if s.endswith("Z"):
#         s = s[:-1] + "+00:00"
#     if len(s) == 19:
#         s += "+00:00"
    
#     return dt.datetime.fromisoformat(s).date()

# def fetch_price_history(symbol: str, start: str, end: str, interval: str = "1d"):
#     """yfinance 주가 조회"""
#     try:
#         df = yf.download(
#             symbol, start=start, end=end, interval=interval,
#             group_by="column", auto_adjust=False, progress=False
#         )
#         if df.empty:
#             return []

#         df = df.reset_index()
#         date_col = df.columns[0]
#         records = []
#         for _, row in df.iterrows():
#             records.append({
#                 "date": str(row[date_col])[:10],
#                 "open": float(row["Open"]),
#                 "high": float(row["High"]),
#                 "low": float(row["Low"]),
#                 "close": float(row["Close"]),
#                 "volume": int(row["Volume"]),
#             })
#         return records
#     except Exception as e:
#         print(f"Error fetching price for {symbol}: {e}")
#         return []

# def calculate_next_day_return(symbol: str, date_str: str):
#     """특정 날짜 기준 익일 수익률 계산"""
#     try:
#         base_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        
#         # 앞뒤 7일치 데이터 가져오기 (주말/휴일 고려)
#         start = base_date - dt.timedelta(days=7)
#         end = base_date + dt.timedelta(days=7)
        
#         df = yf.download(
#             symbol, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"),
#             interval="1d", group_by="column", auto_adjust=False, progress=False
#         )

#         if df.empty or len(df) < 2:
#             return None

#         df = df.reset_index()
#         date_col = df.columns[0]
#         # 날짜 타입 통일
#         df[date_col] = pd.to_datetime(df[date_col]).dt.date
#         df = df.sort_values(date_col).reset_index(drop=True)

#         # 기준일(base_date) 이하인 날짜 중 가장 최신 날짜 찾기
#         candidates = df[df[date_col] <= base_date]
#         if candidates.empty:
#             return None
            
#         base_idx = candidates.index[-1]
#         next_idx = base_idx + 1
        
#         if next_idx >= len(df):
#             return None

#         base_row = df.loc[base_idx]
#         next_row = df.loc[next_idx]

#         base_close = float(base_row["Close"])
#         next_close = float(next_row["Close"])
        
#         # 수익률 계산 ((다음날 - 오늘) / 오늘 * 100)
#         next_return = (next_close - base_close) / base_close * 100.0

#         return {
#             "symbol": symbol,
#             "base_date": str(base_row[date_col]),
#             "base_close": base_close,
#             "next_date": str(next_row[date_col]),
#             "next_close": next_close,
#             "next_day_return": next_return,
#         }
#     except Exception as e:
#         print(f"Error calculating return for {symbol}: {e}")
#         return None
# # ===========================================

# def find_impact_candidates(query: str):
#     """
#     사용자 검색어와 연관된 과거 사건(Case Study) 후보군을 모두 찾습니다.
#     """
#     query = query.lower().strip()
#     candidates = []
    
#     for tweet in IMPACT_TWEETS:
#         # 심볼, 내용, 설명, 작성자 어디든 키워드가 있으면 매칭
#         if (query in tweet['symbol'].lower() or 
#             query in tweet['text'].lower() or 
#             query in tweet['note'].lower() or 
#             query in tweet['author_id'].lower()):
#             candidates.append(tweet)
            
#     return candidates

# def fetch_historical_chart_data(symbol: str, tweet_date_str: str):
#     """
#     트윗 발생일 기준 전후 15일치 주가 데이터를 가져오고, 수익률을 계산합니다.
#     """
#     # UTC 'Z' 제거 및 날짜 변환
#     tweet_date_str = tweet_date_str.replace("Z", "")
#     try:
#         tweet_date = dt.datetime.fromisoformat(tweet_date_str).date()
#     except ValueError:
#         tweet_date = dt.datetime.strptime(tweet_date_str, "%Y-%m-%dT%H:%M:%S").date()
    
#     # 앞뒤 15일 (약 1달) 데이터 조회
#     start_date = tweet_date - dt.timedelta(days=15)
#     end_date = tweet_date + dt.timedelta(days=15)
    
#     print(f"Fetching History for {symbol}: {start_date} ~ {end_date}")

#     try:
#         df = yf.download(
#             symbol, 
#             start=start_date.strftime("%Y-%m-%d"), 
#             end=end_date.strftime("%Y-%m-%d"),
#             interval="1d", 
#             progress=False,
#             auto_adjust=False,
#             multi_level_index=False
#         )
#     except Exception as e:
#         print(f"yfinance error: {e}")
#         return [], 0, 0.0

#     if df.empty:
#         return [], 0, 0.0

#     df = df.reset_index()
#     # 컬럼명 통일 (Date, Close)
#     df.columns = [c.capitalize() for c in df.columns] 
    
#     records = []
    
#     # 1. 데이터 리스트 변환
#     for _, row in df.iterrows():
#         if 'Date' not in row: continue
#         d_val = pd.to_datetime(row['Date']).strftime("%Y-%m-%d")
#         close_val = float(row["Close"])
#         records.append({"date": d_val, "price": close_val})

#     # 2. 트윗 시점 인덱스 찾기
#     post_index = -1
#     target_date_str = tweet_date.strftime("%Y-%m-%d")
    
#     for i, rec in enumerate(records):
#         if rec["date"] >= target_date_str:
#             post_index = i
#             break
            
#     if post_index == -1: post_index = len(records) // 2

#     # 3. 수익률 계산 (Impact Return)
#     # 트윗 발생 전날(T-1) vs 발생 다음날(T+1) 비교
#     impact_return = 0.0
#     if post_index > 0 and post_index < len(records) - 1:
#         prev_price = records[post_index - 1]['price'] # 하루 전
#         next_price = records[post_index + 1]['price'] # 하루 후
#         if prev_price > 0:
#             impact_return = ((next_price - prev_price) / prev_price) * 100.0

#     return records, post_index, impact_return

# ==========================================
# [API 엔드포인트]
# ==========================================

# ==============================================================================
# [API 0] 회원가입 & 로그인 (MongoDB 연동)
# ==============================================================================

@app.post("/api/register")
def register_user(user: UserSignup):
    users_col = get_user_collection()
    
    # 1. 이메일 중복 체크
    if users_col.find_one({"email": user.email}):
        return {"success": False, "msg": "이미 가입된 이메일입니다."}
    
    # 2. 비밀번호 암호화
    hashed_pwd = get_password_hash(user.password)
    
    # 3. DB 저장
    new_user = {
        "username": user.username,
        "email": user.email,
        "password": hashed_pwd,
        "created_at": dt.datetime.now().isoformat()
    }
    users_col.insert_one(new_user)
    
    print(f"[Auth] New user registered: {user.email}")
    return {"success": True, "msg": "회원가입 성공!"}

@app.post("/api/login")
def login_user(user: UserLogin):
    users_col = get_user_collection()
    
    # 1. 사용자 조회
    db_user = users_col.find_one({"email": user.email})
    if not db_user:
        return {"success": False, "msg": "존재하지 않는 이메일입니다."}
    
    # 2. 비밀번호 검증
    if not verify_password(user.password, db_user["password"]):
        return {"success": False, "msg": "비밀번호가 일치하지 않습니다."}
    
    print(f"[Auth] Login successful: {user.email}")
    
    # 3. 성공 응답 (보안상 비번은 제외하고 닉네임 반환)
    return {
        "success": True, 
        "user": {
            "username": db_user["username"],
            "email": db_user["email"]
        }
    }

@app.post("/api/simulation/state/get")
def get_simulation_state(payload: SimulationStateGetPayload):
    sim_col = get_simulation_collection()
    email = payload.email.strip().lower()
    if not email:
        return {"success": False, "msg": "이메일이 필요합니다."}

    doc = sim_col.find_one({"email": email}, {"_id": 0})
    if not doc:
        return {"success": True, "exists": False}

    return {
        "success": True,
        "exists": True,
        "state": {
            "cash": float(doc.get("cash", 0)),
            "holdings": doc.get("holdings", {}),
            "trades": doc.get("trades", []),
            "simulation_started": bool(doc.get("simulation_started", False)),
            "updated_at": doc.get("updated_at"),
        }
    }

@app.post("/api/simulation/state/save")
def save_simulation_state(payload: SimulationStatePayload):
    sim_col = get_simulation_collection()
    email = payload.email.strip().lower()
    if not email:
        return {"success": False, "msg": "이메일이 필요합니다."}

    now = dt.datetime.now().isoformat()
    state_doc = {
        "email": email,
        "cash": float(payload.cash),
        "holdings": payload.holdings,
        "trades": payload.trades,
        "simulation_started": bool(payload.simulation_started),
        "updated_at": now,
    }

    sim_col.update_one({"email": email}, {"$set": state_doc}, upsert=True)
    return {"success": True, "updated_at": now}

@app.post("/api/simulation/state/delete")
def delete_simulation_state(payload: SimulationStateGetPayload):
    sim_col = get_simulation_collection()
    email = payload.email.strip().lower()
    if not email:
        return {"success": False, "msg": "이메일이 필요합니다."}

    result = sim_col.delete_one({"email": email})
    return {"success": True, "deleted": result.deleted_count > 0}

@app.post("/api/simulation/pin/status")
def simulation_pin_status(payload: SimulationStateGetPayload):
    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다.", "pin_set": False}
    pin_set = bool(user_doc.get("simulation_pin_hash"))
    return {"success": True, "pin_set": pin_set}

@app.post("/api/simulation/pin/set")
def simulation_pin_set(payload: SimulationPinSetPayload):
    pin = (payload.pin or "").strip()
    if len(pin) != 4 or not pin.isdigit():
        return {"success": False, "msg": "PIN은 4자리 숫자여야 합니다."}

    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}

    canon_email = user_doc["email"]
    existing_hash = user_doc.get("simulation_pin_hash")

    if existing_hash:
        old = (payload.old_pin or "").strip()
        if len(old) != 4 or not old.isdigit():
            return {"success": False, "msg": "기존 PIN 4자리를 입력해주세요."}
        if not verify_password(old, existing_hash):
            return {"success": False, "msg": "기존 PIN이 일치하지 않습니다."}

    users_col.update_one(
        {"email": canon_email},
        {
            "$set": {
                "simulation_pin_hash": get_password_hash(pin),
                "simulation_pin_set_at": dt.datetime.now().isoformat(),
            }
        },
    )
    return {"success": True, "msg": "거래 PIN이 저장되었습니다."}

@app.post("/api/simulation/pin/verify")
def simulation_pin_verify(payload: SimulationPinVerifyPayload):
    pin = (payload.pin or "").strip()
    if len(pin) != 4 or not pin.isdigit():
        return {"success": False, "msg": "PIN은 4자리 숫자여야 합니다."}

    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc or not user_doc.get("simulation_pin_hash"):
        return {"success": False, "msg": "먼저 거래 PIN을 설정해주세요."}

    if verify_password(pin, user_doc["simulation_pin_hash"]):
        return {"success": True}
    return {"success": False, "msg": "PIN이 일치하지 않습니다."}

@app.post("/api/user/profile")
def get_user_profile(payload: SimulationStateGetPayload):
    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}

    return {
        "success": True,
        "profile": {
            "username": user_doc.get("username", ""),
            "email": user_doc.get("email", ""),
            "created_at": user_doc.get("created_at"),
            "pin_set": bool(user_doc.get("simulation_pin_hash")),
            "simulation_pin_set_at": user_doc.get("simulation_pin_set_at"),
        },
    }

@app.post("/api/user/update")
def update_user_profile(payload: UserProfileUpdatePayload):
    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}

    current_password = (payload.current_password or "").strip()
    if not current_password:
        return {"success": False, "msg": "현재 비밀번호를 입력해주세요."}
    if not verify_password(current_password, user_doc["password"]):
        return {"success": False, "msg": "현재 비밀번호가 일치하지 않습니다."}

    canon_email = user_doc["email"]
    updates = {}

    new_username = (payload.username or "").strip()
    if new_username and new_username != user_doc.get("username"):
        updates["username"] = new_username

    new_email_raw = (payload.new_email or "").strip()
    if new_email_raw:
        new_email = new_email_raw.lower()
        if new_email != canon_email.lower():
            existing = find_user_doc_by_email(users_col, new_email)
            if existing and existing.get("email", "").lower() != canon_email.lower():
                return {"success": False, "msg": "이미 사용 중인 이메일입니다."}
            updates["email"] = new_email

    new_password = (payload.new_password or "").strip()
    if new_password:
        if len(new_password) < 4:
            return {"success": False, "msg": "새 비밀번호는 4자 이상이어야 합니다."}
        updates["password"] = get_password_hash(new_password)

    if not updates:
        return {"success": False, "msg": "변경할 항목이 없습니다."}

    users_col.update_one({"email": canon_email}, {"$set": updates})

    next_email = updates.get("email", canon_email)
    if "email" in updates:
        sim_col = get_simulation_collection()
        old_key = canon_email.strip().lower()
        new_key = next_email.strip().lower()
        sim_doc = sim_col.find_one({"email": old_key})
        if sim_doc:
            sim_doc["email"] = new_key
            sim_col.delete_one({"email": old_key})
            sim_col.update_one({"email": new_key}, {"$set": sim_doc}, upsert=True)

    refreshed = users_col.find_one({"email": next_email}) or user_doc
    return {
        "success": True,
        "msg": "계정 정보가 저장되었습니다.",
        "user": {
            "username": refreshed.get("username", updates.get("username", user_doc.get("username"))),
            "email": refreshed.get("email", next_email),
        },
    }

def _get_reward_state(user_doc):
    rewards = user_doc.get("simulation_rewards") or {}
    return {
        "quiz_reward_cash": float(rewards.get("quiz_reward_cash", 0) or 0),
        "attendance_reward_cash": float(rewards.get("attendance_reward_cash", 0) or 0),
        "attendance_last_date": rewards.get("attendance_last_date"),
    }

@app.post("/api/user/rewards/get")
def get_user_rewards(payload: UserRewardsPayload):
    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}
    return {"success": True, "rewards": _get_reward_state(user_doc)}

@app.post("/api/user/rewards/quiz")
def add_user_quiz_reward(payload: UserQuizRewardPayload):
    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}

    amount = max(0, float(payload.amount or 0))
    rewards = _get_reward_state(user_doc)
    rewards["quiz_reward_cash"] += amount
    users_col.update_one(
        {"email": user_doc["email"]},
        {"$set": {"simulation_rewards": rewards}},
    )
    return {"success": True, "rewards": rewards, "added": amount}

@app.post("/api/user/attendance/check")
def check_user_attendance(payload: UserAttendancePayload):
    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}

    check_date = (payload.date or dt.datetime.now().date().isoformat()).strip()
    try:
        dt.datetime.strptime(check_date, "%Y-%m-%d")
    except Exception:
        return {"success": False, "msg": "출석 날짜 형식은 YYYY-MM-DD여야 합니다."}

    rewards = _get_reward_state(user_doc)
    if rewards.get("attendance_last_date") == check_date:
        return {"success": True, "checked": False, "rewards": rewards}

    amount = max(0, float(payload.amount or 0))
    rewards["attendance_reward_cash"] += amount
    rewards["attendance_last_date"] = check_date
    users_col.update_one(
        {"email": user_doc["email"]},
        {"$set": {"simulation_rewards": rewards}},
    )
    return {"success": True, "checked": True, "rewards": rewards, "added": amount}

@app.post("/api/user/delete")
def delete_user_account(payload: UserDeletePayload):
    users_col = get_user_collection()
    user_doc = find_user_doc_by_email(users_col, payload.email)
    if not user_doc:
        return {"success": False, "msg": "사용자를 찾을 수 없습니다."}

    current_password = (payload.current_password or "").strip()
    if not current_password:
        return {"success": False, "msg": "현재 비밀번호를 입력해주세요."}
    if not verify_password(current_password, user_doc["password"]):
        return {"success": False, "msg": "현재 비밀번호가 일치하지 않습니다."}

    canon_email = user_doc["email"]
    users_col.delete_one({"email": canon_email})

    sim_col = get_simulation_collection()
    sim_col.delete_one({"email": canon_email.strip().lower()})

    sim_db_names = {os.getenv("MONGODB_DB_NAME", "xtock"), "xtock_db"}
    for db_name in sim_db_names:
        sim_db = mongo_client[db_name]
        sim_users = sim_db["simulation_users"]
        sim_user_docs = list(sim_users.find({"email": canon_email}))
        sim_user_ids = [str(doc.get("_id")) for doc in sim_user_docs if doc.get("_id")]
        sim_users.delete_many({"email": canon_email})
        for user_id in sim_user_ids:
            sim_db["simulation_portfolios"].delete_many({"user_id": user_id})
            sim_db["simulation_transactions"].delete_many({"user_id": user_id})
            sim_db["simulation_auto_trades"].delete_many({"user_id": user_id})

    print(f"[Auth] User account deleted: {canon_email}")
    return {"success": True, "msg": "회원탈퇴가 완료되었습니다."}

# ==========================================
# [API 1] 최근 기업 근황 (Recent Status) - 실시간 X API 사용
# ==========================================
# 1. 최근 기업 근황 (Real-time)
@app.post("/api/recent-status")
async def get_recent_status(payload: SearchRequest):
    raw_query = payload.text.strip().upper()
    
    # 이름 -> 티커 변환
    if raw_query in NAME_TO_TICKER:
        ticker = NAME_TO_TICKER[raw_query]
    else:
        ticker = raw_query
        
    # X 검색어 설정
    if ticker in SP500_HANDLES:
        twitter_query = SP500_HANDLES[ticker]
    else:
        twitter_query = f"${ticker} OR {ticker}"
        
    # 데이터 조회
    tweets = await call_x_recent_search(twitter_query, max_results=3)
    if (payload.start_date is not None) or (payload.end_date is not None):
        # 기간 조회는 start_date/end_date 둘 다 필요합니다.
        if payload.start_date is None or payload.end_date is None:
            return {
                "found": False,
                "msg": "start_date와 end_date를 모두 지정해주세요.",
                "symbol": ticker,
                "tweets": tweets,
                "stock_data": [],
            }

        try:
            # 날짜 파싱 및 기본 검증
            _ = parse_iso_date(payload.start_date)
            _ = parse_iso_date(payload.end_date)
        except Exception:
            return {
                "found": False,
                "msg": "날짜 형식은 YYYY-MM-DD로 입력해주세요.",
                "symbol": ticker,
                "tweets": tweets,
                "stock_data": [],
            }

        stock_data = get_stock_price_history_range(ticker, payload.start_date, payload.end_date)
    else:
        hist_days = payload.stock_history_days if payload.stock_history_days is not None else 100
        stock_data = get_stock_price_history(ticker, days=hist_days)

    if not stock_data:
        return {
            "found": False,
            "msg": "해당 기간의 주가 데이터를 불러올 수 없습니다.",
            "symbol": ticker,
            "tweets": tweets,
            "stock_data": [],
        }
    
    return {
        "found": True,
        "symbol": ticker,
        "tweets": tweets,
        "stock_data": stock_data
    }

# ==============================================================================
# [API 2] 과거 영향력 분석 (Real AI Engine Integration)
# ==============================================================================

# ==============================================================================
# [API 2-1] 검색어와 관련된 '트윗 리스트' 반환 (랜덤 셔플 적용)
# ==============================================================================
@app.post("/api/historical-impact")
def get_historical_impact(payload: SearchRequest):
    query = payload.text.strip()
    print(f"[AI Search] Query: {query}")
    
    target_symbol = None
    candidates = []
    
    # 1. AI 엔진 검색
    try:
        ai_results = search_engine.search(query, top_k=1)
        if ai_results:
            top_res = ai_results[0]
            target_symbol = top_res['symbol'].strip().upper()
            print(f"[AI Match] '{query}' -> '{target_symbol}'")
    except Exception as e:
        print(f"[AI Error] {e}")

    # 2. 매칭 로직
    if target_symbol:
        candidates = [t for t in IMPACT_TWEETS if target_symbol in t['symbol']]
        # 비상용 데이터
        if not candidates and target_symbol == "TSLA":
             candidates = [{
                "id": "emergency_tsla", "symbol": "TSLA", "text": "Tesla production hits record high. $TSLA", 
                "created_at": "2022-09-29 18:48:36+00:00", "author_id": "Tesla, Inc.", "note": "Recovered Data"
            }]

    # 3. Fallback
    if not candidates:
        print("[Fallback] Using keyword search")
        candidates = [t for t in IMPACT_TWEETS if query.lower() in t['text'].lower()]

    if not candidates:
        return {"found": False, "msg": f"'{query}'와 관련된 데이터를 찾을 수 없습니다."}

    # 20개 미만이어도 무조건 섞어서 다양한 시점의 트윗이 나오게 함
    random.shuffle(candidates) # 전체를 섞어버림
    final_candidates = candidates[:20] # 그 중 앞의 20개 선택
    final_candidates.sort(key = lambda x: x['created_at'], reverse = True)

    print(f"Shuffled & Selected {len(final_candidates)} tweets.")

    return {
        "found": True,
        "symbol": target_symbol if target_symbol else "KEYWORD",
        "candidates": final_candidates
    }

# ==============================================================================
# [API 2-2] 특정 사건의 '차트 데이터' 반환 (데이터 파싱 강력하게 수정)
# ==============================================================================
@app.post("/api/historical-chart")
def get_historical_chart(payload: ChartRequest):
    symbol = payload.symbol
    date_str = payload.date
    
    print(f"Fetching Chart: {symbol} at {date_str}")
    
    hist_data = []
    impact_return = 0.0
    post_index = -1
    
    try:
        event_dt = parse_csv_date(date_str)
        start_dt = event_dt - dt.timedelta(days=30)
        end_dt = event_dt + dt.timedelta(days=30)
        
        # multi_level_index=False로 평탄화
        df = yf.download(
            symbol, 
            start=start_dt.strftime("%Y-%m-%d"), 
            end=end_dt.strftime("%Y-%m-%d"), 
            interval="1d", 
            progress=False,
            multi_level_index=False
        )
        
        if not df.empty:
            df = df.reset_index()
            # 날짜 컬럼 찾기
            date_col = next((c for c in df.columns if 'date' in str(c).lower()), df.columns[0])
            
            for _, row in df.iterrows():
                try:
                    # 1. 날짜 처리
                    val = row[date_col]
                    # Series나 numpy 타입인 경우 값 추출
                    if hasattr(val, 'item'): val = val.item()
                    d_val = pd.to_datetime(val)
                    
                    # 2. 종가 처리 (강력한 파싱)
                    close_val = row.get("Close", 0)
                    # Series, numpy float 등 모든 경우의 수 처리
                    if hasattr(close_val, 'item'): 
                        close_val = float(close_val.item())
                    else:
                        close_val = float(close_val)

                    hist_data.append({
                        "date": d_val.strftime("%Y-%m-%d"),
                        "price": close_val
                    })
                except Exception as row_err:
                    # 행 하나 에러나도 무시하고 계속 진행
                    continue
            
            # 3. 이벤트 시점 및 수익률 계산
            target_str = event_dt.strftime("%Y-%m-%d")
            for i, d in enumerate(hist_data):
                if d['date'] >= target_str:
                    post_index = i
                    break
            
            if post_index != -1 and post_index < len(hist_data) - 5:
                base = hist_data[post_index]['price']
                future = hist_data[post_index+5]['price']
                if base > 0: impact_return = ((future - base) / base) * 100.0
                
    except Exception as e:
        print(f"Yahoo Finance Error: {e}")
        
    return {
        "stock_data": hist_data,
        "post_index": post_index,
        "impact_return": impact_return
    }
    
# 헬스체크
@app.get("/health")
def health_check():
    return {"status": "ok", "mongodb": mongo_client is not None}

# @app.get("/api/tweets")
# async def get_tweets(
#     q: str = Query(..., description="검색 쿼리 ($TSLA, Elon Musk 등)"),
#     max_results: int = Query(10, ge=10, le=100),
#     next_token: Optional[str] = Query(None),
# ):
#     """X(Twitter) 트윗 검색"""
#     data = await call_x_recent_search(q, max_results=max_results, next_token=next_token)
#     return {"query": q, "max_results": max_results, "raw": data}


# @app.get("/api/price")
# def get_price_history_endpoint(symbol: str, start: str, end: str):
#     """주가 히스토리 조회"""
#     data = fetch_price_history(symbol, start, end)
#     return {"symbol": symbol, "start": start, "end": end, "prices": data}


# @app.get("/api/next-return")
# def get_next_day_return(symbol: str, date: str):
#     """특정 날짜 기준 수익률 계산 조회"""
#     result = calculate_next_day_return(symbol, date)
#     if result is None:
#         raise HTTPException(status_code=404, detail="Not enough data to compute return")
#     return result


# @app.post("/api/tweet-impact")
# def tweet_impact(payload: TweetImpactRequest):
#     """
#     [ETL Pipeline] 트윗 정보 수신 -> 날짜 추출 -> 수익률 계산 -> DB 저장
#     """
#     # 1. 날짜 추출
#     try:
#         base_date = infer_base_date_from_tweet_created_at(payload.tweet_created_at)
#         base_date_str = base_date.strftime("%Y-%m-%d")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Invalid date format: {e}")

#     # 2. 수익률 계산
#     result = calculate_next_day_return(payload.symbol, base_date_str)
#     if result is None:
#         raise HTTPException(status_code=404, detail="Market data not found for calculation")

#     # 3. 데이터 조립 (MongoDB Schema)
#     doc = {
#         "tweet_id": payload.tweet_id,  # Unique Key
#         "symbol": payload.symbol,
#         "tweet_text": payload.tweet_text,
#         "tweet_created_at": payload.tweet_created_at,
        
#         # 계산된 주가 정보
#         "base_date": result["base_date"],
#         "base_close": result["base_close"],
#         "next_date": result["next_date"],
#         "next_close": result["next_close"],
#         "next_day_return": result["next_day_return"],
        
#         # 시스템 메타데이터
#         "created_at_system": dt.datetime.utcnow(),
        
#     }

#     # 4. MongoDB 저장 (Upsert)
#     if tweet_impact_col is not None:
#         try:
#             tweet_impact_col.update_one(
#                 {"tweet_id": payload.tweet_id}, 
#                 {"$set": doc}, 
#                 upsert=True
#             )
#             print(f"Saved impact data for {payload.symbol} (Tweet ID: {payload.tweet_id})")
#         except Exception as e:
#             print(f"MongoDB Save Error: {e}")
#     else:
#         print("MongoDB not connected! Data NOT saved.")

#     return doc


# @app.post("/api/match-company")
# def match_company(payload: SearchRequest):
#     """
#     [Main Scenario]
#     1. 사용자 검색어 수신
#     2. 연관된 과거 사건 후보군 탐색 -> 랜덤 1개 선택 (Dynamic Simulation)
#     3. 해당 시점의 주가 데이터 및 수익률 계산
#     4. 검색 로그 MongoDB 저장 (Data Accumulation)
#     5. 최종 결과 반환
#     """
#     query = payload.text.strip()
#     print(f"Analyzing Request: {query}")
    
#     # 1. 후보군 탐색
#     candidates = find_impact_candidates(query)
    
#     # 검색 결과가 없으면 랜덤으로 예시(Demo) 보여주기
#     if not candidates:
#         print("No match. Picking random sample.")
#         tweet = random.choice(IMPACT_TWEETS)
#         note_prefix = "[Demo: 검색어와 무관한 예시] "
#         is_exact_match = False
#     else:
#         tweet = random.choice(candidates) # 매번 다른 사례를 보여줌
#         note_prefix = ""
#         is_exact_match = True
    
#     print(f"Selected Case: {tweet['id']} ({tweet['symbol']})")
    
#     # 2. 주가 데이터 및 수익률 조회
#     stock_data, post_index, impact_return = fetch_historical_chart_data(tweet['symbol'], tweet['created_at'])
    
#     if not stock_data:
#         return {"matches": [], "note": "Failed to fetch price data."}

#     # 3. MongoDB 로그 저장 (Log History)
#     if search_log_col is not None:
#         try:
#             log_entry = {
#                 "query": query,
#                 "matched_symbol": tweet['symbol'],
#                 "matched_event_id": tweet['id'],
#                 "impact_return": impact_return,
#                 "is_exact_match": is_exact_match,
#                 "timestamp": dt.datetime.utcnow()
#             }
#             search_log_col.insert_one(log_entry)
#             print(f"Log saved to MongoDB.")
#         except Exception as e:
#             print(f"Log Save Error: {e}")

#     # 4. 결과 조립 (Frontend Compatible)
#     result = {
#         "symbol": tweet['symbol'],
#         "name": tweet['symbol'], # 필요 시 이름 매핑 가능
#         "score": 0.99, # 매칭 신뢰도
#         # note를 financial_summary에 넣어서 프론트엔드가 보여주게 함
#         "financial_summary": f"{note_prefix} 학습 포인트: {tweet['note']}",
        
#         # 트윗 정보
#         "tweet": {
#             "author_id": tweet['author_id'],
#             "text": tweet['text'],
#             "created_at": tweet['created_at'],
#             "impact_return": impact_return # 프론트엔드에서 색깔 표시용 등으로 사용 가능
#         },
        
#         # 차트 데이터
#         "stockData": stock_data,
#         "postIndex": post_index
#     }
    
#     return {
#         "input_text": query,
#         "matches": [result], 
#         "note": "Historical Impact Analysis Mode"
#     }
