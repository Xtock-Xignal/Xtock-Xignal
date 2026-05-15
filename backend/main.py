import os
import datetime as dt
from contextlib import asynccontextmanager
import json
import pandas as pd
import yfinance as yf
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pymongo import MongoClient
from passlib.context import CryptContext

from app import api as api_routers
from app.services import backtest_service

from app.api.terms import router as terms_router
from app.api.news import router as news_router
load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://xtock-mongodb:27017")
mongo_client = MongoClient(MONGO_URI)

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

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://xtock-mongodb:27017") # 기본 주소 강제 주입!
MONGODB_NAME = os.getenv("MONGODB_NAME", "xtock_xignal") # 진짜 DB 이름 강제 주입!
MONGODB_COLLECTION_LOGS = "search_history"

mongo_client = None
search_log_col = None

try:
    # if문 없애버리고 무조건 연결 시도!
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client[MONGODB_NAME]
    search_log_col = db[MONGODB_COLLECTION_LOGS]
    print("[DB] MongoDB Connected Successfully.")
except Exception as e:
    print(f"[DB] Connection Failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("XTock-Xignal Backend Starting")
    yield
    print("XTock-Xignal Backend Shutting Down")
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

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_user_collection():
    return mongo_client["xtock_xignal"]["users"]

# 비밀번호 관련 함수
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)

BacktestPosition = backtest_service.BacktestPosition
BacktestRequest = backtest_service.BacktestRequest
BacktestSymbolItem = backtest_service.BacktestSymbolItem

def get_stock_price_history(symbol: str, days: int = 30):
    try:
        end_date = dt.datetime.now()
        start_date = end_date - dt.timedelta(days = days + 20)
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


def _resolve_symbol(raw_symbol: str):
    return backtest_service.resolve_symbol(raw_symbol, NAME_TO_TICKER)


def _normalize_symbol_name(raw: str):
    return backtest_service.normalize_symbol_name(raw)


def _get_backtest_symbol_catalog():
    return backtest_service.get_backtest_symbol_catalog(NAME_TO_TICKER, _normalize_symbol_name)


def _get_backtest_symbol_detail(raw_symbol: str):
    symbol = _resolve_symbol(raw_symbol)
    if not symbol:
        return None

    catalog = {item["symbol"]: item["name"] for item in _get_backtest_symbol_catalog()}
    return backtest_service.get_backtest_symbol_detail(symbol, catalog.get(symbol))


def _load_backtest_prices(symbol: str, start_date: str = None, end_date: str = None):
    return backtest_service.load_backtest_prices(symbol, start_date, end_date)


def _normalize_backtest_positions(payload: BacktestRequest):
    return backtest_service.normalize_backtest_positions(payload, NAME_TO_TICKER)


def _run_ma_cross_backtest(payload: BacktestRequest):
    return backtest_service.run_ma_cross_backtest(
        payload,
        normalize_positions_fn=lambda req: backtest_service.normalize_backtest_positions(req, NAME_TO_TICKER),
        run_single_fn=lambda sym, req: backtest_service.run_single_ma_cross_backtest(
            sym,
            req,
            price_loader=lambda sym2, start_date2, end_date2: _load_backtest_prices(
                sym2,
                start_date2,
                end_date2,
            ),
        ),
        name_to_ticker=NAME_TO_TICKER,
    )


def _run_single_ma_cross_backtest(symbol: str, payload: BacktestRequest):
    return backtest_service.run_single_ma_cross_backtest(
        symbol,
        payload,
        price_loader=lambda sym, start_date2, end_date2: _load_backtest_prices(sym, start_date2, end_date2),
    )
def _download_stock_history_for_historical_chart(
    symbol: str,
    start: str,
    end: str,
    interval: str = "1d",
    progress: bool = False,
    multi_level_index: bool = False,
):
    return yf.download(
        symbol,
        start=start,
        end=end,
        interval=interval,
        progress=progress,
        multi_level_index=multi_level_index,
    )


app.include_router(
    api_routers.create_auth_router(
        get_user_collection=get_user_collection,
        get_password_hash=get_password_hash,
        verify_password=verify_password,
    )
)
app.include_router(
    api_routers.create_market_router(
        name_to_ticker=NAME_TO_TICKER,
        get_stock_price_history=get_stock_price_history,
    )
)
app.include_router(
    api_routers.create_portfolio_router(
        get_user_collection=get_user_collection,
    )
)
app.include_router(
    api_routers.create_dashboard_router(
        yf_module=yf,
    )
)

app.include_router(
    terms_router,
    prefix="/api/terms",
    tags=["Financial Terms"]
)

app.include_router(
    news_router, 
    prefix="/api/news",
    tags=["news"])

@app.post("/api/backtest/run")
def run_backtest(payload: BacktestRequest):
    try:
        strategy = payload.strategy.strip().lower()
        if strategy != "ma_cross":
            return {"success": False, "msg": "현재는 ma_cross 전략만 지원합니다."}

        return _run_ma_cross_backtest(payload)
    except ValueError as err:
        return {"success": False, "msg": str(err)}
    except Exception as err:
        print(f"[Backtest Error] {err}")
        return {"success": False, "msg": "백테스트 실행 중 오류가 발생했습니다."}
    

@app.get("/api/backtest/symbols")
def list_backtest_symbols(query: str = Query("", description="티커 검색어"), limit: int = Query(200, ge=1, le=1000)):
    symbols = _get_backtest_symbol_catalog()

    normalized_query = query.strip().upper()
    if normalized_query:
        filtered = []
        for item in symbols:
            if (
                normalized_query in item["symbol"].upper()
                or (item["name"] and normalized_query in item["name"].upper())
            ):
                filtered.append(item)
        symbols = filtered

    return {
        "items": symbols[:limit]
    }


@app.get("/api/backtest/symbol-info")
def get_backtest_symbol_info(symbol: str = Query("", description="심볼 또는 종목명")):
    info = _get_backtest_symbol_detail(symbol)
    if not info:
        return {
            "success": False,
            "msg": "티커를 확인할 수 없습니다.",
        }

    return {
        "success": True,
        "item": info,
    }
    
# 헬스체크
@app.get("/health")
def health_check():
    return {"status": "ok", "mongodb": mongo_client is not None}
