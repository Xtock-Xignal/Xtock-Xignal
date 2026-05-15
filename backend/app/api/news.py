import os
import time
import json
import requests
import feedparser
import datetime
from email.utils import parsedate_to_datetime
from fastapi import APIRouter, Query
from pymongo import MongoClient
from google import genai
import os
from newspaper import Article, Config
from googletrans import Translator
from pydantic import BaseModel

router = APIRouter()

INITIAL_TEST_NEWS = [
    {
        "source": "XTock Tutorial",
        "link": "https://xtock.system/tutorial-1",
        "date": "2026-04-01T10:00:00",
        "timestamp": 1775017200,
        "title": "금융 용어 사전 테스트 (FOMC와 인플레이션)",
        "original": "The Federal Reserve is closely monitoring the FOMC meeting results. Inflation remains a key concern for the S&P 500 index. Jerome Powell mentioned that interest rate cuts depend on economic stability.",
        "translated": "연방준비제도는 FOMC 회의 결과를 면밀히 모니터링하고 있습니다. 인플레이션은 S&P 500 지수의 주요 우려 사항으로 남아 있습니다. 제롬 파월은 금리 인하가 경제 안정성에 달려 있다고 언급했습니다."
    },
    {
        "source": "XTock Tutorial",
        "link": "https://xtock.system/tutorial-2",
        "date": "2026-04-01T11:00:00",
        "timestamp": 1775020800,
        "title": "기업 백과사전 테스트 (NVIDIA와 반도체)",
        "original": "NVIDIA is leading the AI revolution with its advanced GPU technology. Tech giants like Apple and Microsoft are competing for semiconductor dominance in the Nasdaq market.",
        "translated": "엔비디아는 첨단 GPU 기술로 AI 혁명을 주도하고 있습니다. 애플과 마이크로소프트 같은 빅테크 기업들은 나스닥 시장에서 반도체 주도권을 잡기 위해 경쟁하고 있습니다."
    },
    {
        "source": "XTock Tutorial",
        "link": "https://xtock.system/tutorial-3",
        "date": "2026-04-01T12:00:00",
        "timestamp": 1775024400,
        "title": "공정성 및 시장 반응 테스트 (ETF와 배당)",
        "original": "Investors are moving towards high-yield dividend stocks and monthly distribution ETFs like JEPI or JEPQ. Asset management firms are adjusting their portfolios for the upcoming fiscal quarter.",
        "translated": "투자자들은 고배당주와 JEPI, JEPQ 같은 월배당 ETF로 이동하고 있습니다. 자산 운용사들은 다가오는 회계 분기를 위해 포트폴리오를 조정하고 있습니다."
    }
]

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://xtock-mongodb:27017")
MONGODB_NAME = os.getenv("MONGODB_NAME", "xtock_xignal")

try:
    mongo_client = MongoClient(MONGO_URI)
    db = mongo_client[MONGODB_NAME]
    
    # DB 컬렉션을 VIP(S&P500)와 일반(General) 두 개로 분리합니다.
    news_sp500_col = db["news_sp500"]
    news_sp500_col.create_index("link", unique=True)
    
    news_general_col = db["news_general"]
    news_general_col.create_index("link", unique=True)
    
    # 기존 코드 호환성을 위해 변수명 유지
    news_cache_col = db["news_cache"] 
except Exception as e:
    print(f"[Error] MongoDB Connection Failed: {e}")
    news_sp500_col = None
    news_general_col = None
    news_cache_col = None

# S&P 500 식별을 위한 키워드 풀 (추후 500개 전체로 확장 가능)
SP500_KEYWORDS = [
    "apple", "aapl", "nvidia", "nvda", "microsoft", "msft", 
    "tesla", "tsla", "amazon", "amzn", "s&p 500", "spx", "spy"
]

def is_sp500_related(title: str, text: str) -> bool:
    """제목이나 본문에 S&P 500 관련 키워드가 있는지 검사합니다."""
    combined_text = (title + " " + text).lower()
    for keyword in SP500_KEYWORDS:
        if keyword in combined_text:
            return True
    return False

SP500_DICT = {
    "apple": "AAPL", "aapl": "AAPL", 
    "nvidia": "NVDA", "nvda": "NVDA", 
    "microsoft": "MSFT", "msft": "MSFT", 
    "tesla": "TSLA", "tsla": "TSLA", 
    "amazon": "AMZN", "amzn": "AMZN"
}

def get_related_tickers(title: str, text: str) -> list:
    """S&P 500 관련 키워드를 찾아 티커(단축어) 리스트로 반환합니다."""
    combined_text = (title + " " + text).lower()
    found_tickers = set()
    for key, ticker in SP500_DICT.items():
        if key in combined_text:
            found_tickers.add(ticker)
    return list(found_tickers)


def extract_article_text(url: str) -> str:
    try:
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        config = Config()
        config.browser_user_agent = user_agent
        config.request_timeout = 10
        article = Article(url, config=config)
        article.download()
        article.parse()
        return article.text.strip()
    except Exception as e:
        print(f"[Warning] newspaper3k extraction failed for {url}")
        return ""

def init_test_news():
    if news_cache_col is not None:
        for news in INITIAL_TEST_NEWS:
            if not news_cache_col.find_one({"link": news["link"]}):
                news_cache_col.insert_one(news)
                print(f"[Init] Test article inserted: {news['title']}")

try:
    terms_col = db["terms_dict"]
    # 검색 속도 향상 및 중복 저장 방지를 위한 인덱스 생성
    terms_col.create_index("en_term", unique=True)
except Exception as e:
    print(f"[Warning] Terms Collection init failed: {e}")
    terms_col = None

class ScanRequest(BaseModel):
    text: str

# 2. 기사에 있는 단어 형광펜 칠하기용 API (DB 스캔)
@router.post("/terms/scan")
async def scan_terms(req: ScanRequest):
    """프론트엔드에서 기사 본문을 보내면, DB에 이미 저장된 단어들을 찾아 돌려줍니다."""
    if terms_col is None: 
        return {"matched_terms": []}
        
    try:
        # DB에 저장된 모든 단어 리스트 가져오기
        all_terms = list(terms_col.find({}, {"_id": 0, "en_term": 1, "ko_term": 1}))
        
        matched = []
        text_lower = req.text.lower()
        
        for t in all_terms:
            en_word = t.get("en_term", "")
            # 본문에 해당 단어가 존재하면 형광펜 처리 리스트에 추가
            if en_word and en_word.lower() in text_lower:
                matched.append(t)
                
        return {"matched_terms": matched}
    except Exception as e:
        print(f"[Error] Term Scan failed: {e}")
        return {"matched_terms": []}

# 3. 단어 뜻 검색 및 AI 저장 API (DB 캐싱)
@router.get("/terms/search")
async def search_term(keyword: str):
    """사용자가 단어를 클릭했을 때 DB를 먼저 뒤지고, 없으면 AI에게 물어본 뒤 저장합니다."""
    keyword = keyword.strip()
    if not keyword:
        return {"found": False}
        
    # DB에서 먼저 찾기 
    # 대소문자 구분 없이(regex) 완벽하게 일치하는 단어 검색
    existing = terms_col.find_one({
        "$or": [
            {"en_term": {"$regex": f"^{keyword}$", "$options": "i"}},
            {"aliases": {"$regex": f"^{keyword}$", "$options": "i"}}
        ]
    }, {"_id": 0})
    
    if existing:
        print(f"[Info] Dictionary Hit (DB): {keyword}")
        existing["source"] = "DB"
        existing["found"] = True
        return existing
        
    #  DB에 없으면 AI 호출 (최초 1회만 실행됨)
    print(f"[Info] Dictionary Miss, Calling AI: {keyword}")
    try:
        # 1. 프롬프트 먼저 선언 (aliases 동의어 포함)
        prompt = f"""
        당신은 금융/경제 전문가입니다. 영어 금융/경제 단어 '{keyword}'의 뜻을 일반인이 이해하기 쉽게 2~3문장으로 설명해주세요.
        만약 이 단어의 자주 쓰이는 동의어나 줄임말(약어)이 있다면 'aliases' 배열에 넣어주세요. (예: "Federal Reserve" -> ["Fed", "FRB"]). 없다면 빈 배열을 넣으세요.
        반드시 아래 JSON 형식으로만 응답해야 합니다. 마크다운 기호는 생략하십시오.
        {{
            "en_term": "{keyword}",
            "ko_term": "한국어 번역/독음",
            "aliases": ["동의어1", "동의어2"],
            "definition": "단어에 대한 쉬운 설명"
        }}
        """

        # 2. 최신 SDK로 API 호출
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        
        # 3. JSON 파싱
        res_text = response.text.replace('```json', '').replace('```', '').strip()
        data = json.loads(res_text)
        
        # 4. DB 영구 저장
        terms_col.insert_one({
            "en_term": data.get("en_term", keyword),
            "ko_term": data.get("ko_term", ""),
            "aliases": data.get("aliases", []),
            "definition": data.get("definition", "")
        })
        
        data["source"] = "AI"
        data["found"] = True
        return data
        
    except Exception as e:
        print(f"[Error] AI Dict Search: {e}")
        return {
            "found": True, 
            "en_term": keyword,
            "ko_term": keyword,
            "aliases": [],
            "definition": "AI 응답 지연 또는 일시적 오류입니다. 다시 시도해주세요.",
            "source": "AI",
            "error": str(e)
        }

class SummaryRequest(BaseModel):
    text: str
    url: str = None 

@router.post("/summary")
async def get_ai_summary(req: SummaryRequest):
    """원문을 받아 Gemini API를 통해 3줄 요약을 생성합니다."""

    target_link = req.url.strip() if req.url else None
    if not req.text or len(req.text) < 50:
        return {"summary": "본문이 너무 짧아 요약할 수 없습니다."}
    
    if target_link:
        existing_news = news_sp500_col.find_one({"link": target_link}) or news_general_col.find_one({"link": target_link})
        
        if existing_news and existing_news.get("summary"):
            print(f"[Cache Hit] 이미 요약된 기사입니다: {target_link}")
            return {"summary": existing_news["summary"]}
        
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # 503 에러 방지 (1500자 내외)
        if len(req.text) <= 1500:
            safe_text = req.text
        else:
            safe_text = req.text[:1000] + "\n[중략]\n" + req.text[-500:]

        prompt = f"""
        [Role]
        You are a Senior Wall Street Financial Analyst and a strict Data Extractor.

        [Context]
        You are provided with a raw financial news article. The text may be truncated or contain web scraping noise. Your objective is to extract only the most critical, market-moving facts without any distortion.

        [Requirements]
        1. Summarize the core content into exactly 3 lines, starting with numbers (1., 2., 3.).
        2. Filter out all noise: Ignore the journalist's subjective opinions, advertisements, clickbait rhetoric, and emotional adjectives. Focus strictly on objective facts (e.g., earnings, macroeconomic data, M&A, official statements).
        3. If any S&P 500 companies or their ticker symbols are relevant to the main event, explicitly mention them in the summary.
        4. Anti-Hallucination Strict Rule: You must ONLY use information explicitly stated in the provided text. Do not infer, guess, or bring in outside knowledge. If the text is incomplete, summarize only what is available.
        5. Output Language: The final output MUST be written entirely in Korean (한국어).
        6. Formatting Strict Rule: DO NOT use any Markdown formatting. Never use bolding (**), italics (*), or headers (#). The output must be strictly plain text.
        [Input Text]
        {safe_text} 
        """
        
        # 3. AI 요약 실행
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        ai_summary = response.text.strip()
        
        if target_link:
            update_payload = {"$set": {"summary": ai_summary}}
            
            # 기사가 들어있는 양쪽 컬렉션에 모두 업데이트 시도
            res_sp500 = news_sp500_col.update_one({"link": target_link}, update_payload)
            res_general = news_general_col.update_one({"link": target_link}, update_payload)
            
            # 매칭 및 수정 결과 합산
            total_matched = res_sp500.matched_count + res_general.matched_count
            total_modified = res_sp500.modified_count + res_general.modified_count
            
            # 추적 로그 출력
            if total_modified > 0:
                print(f"[DB Update Success] 요약본 DB 저장 완료: {target_link}")
            elif total_matched == 0:
                print(f"[DB Update Failed] 에러: DB에서 해당 URL을 찾을 수 없습니다: {target_link}")
            else:
                print(f"[DB Update Skipped] URL은 존재하나 요약 내용이 이미 동일함: {target_link}")
        else:
            print("[DB Update Failed] 에러: 프론트엔드에서 URL 파라미터가 누락되었습니다.")
        
        return {"summary": ai_summary}
    
    except Exception as e:
        print(f"[Error] AI 요약 실패: {e}")
        return {"error": "AI 서비스가 일시적으로 지연되고 있습니다."}
    
@router.get("/live")
async def get_live_news(
    force_refresh: bool = Query(False, description="강제 크롤링 여부"),
    latest_url: str = Query(None, description="현재 화면의 최신 기사 URL") 
):
    init_test_news()
    
    def get_latest_news_from_db(limit=50):
        all_news = []
        if news_sp500_col is not None:
            sp500_cursor = news_sp500_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            all_news.extend(list(sp500_cursor))
            
        if news_general_col is not None:
            general_cursor = news_general_col.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit)
            all_news.extend(list(general_cursor))
            
        all_news.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return all_news[:limit]

    # 새로고침 요청 시, RSS 목록만 빠르게 가져와서 최신 기사가 동일한지 확인 
    rss_url = "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY,QQQ,AAPL,NVDA,TSLA&region=US&lang=en-US"
    if latest_url and not force_refresh:
        try:
            quick_feed = feedparser.parse(rss_url)
            if quick_feed.entries:
                top_link = quick_feed.entries[0].get("link", "")
                if top_link == latest_url:
                    print("[Info] No new articles found. Early return.")
                    return {"has_new": False, "news": get_latest_news_from_db(50)}
        except Exception as e:
            print(f"[Error] Fast RSS check failed: {e}")

    if not force_refresh and not latest_url:
        cached_news = get_latest_news_from_db(50)
        if cached_news:
            return {"has_new": False, "news": cached_news}

    print("[System] Scanning for new articles...")
    
    YAHOO_MAX = 2
    FINNHUB_MAX = 2
    yahoo_added = 0
    finnhub_added = 0

    # 1. 야후 파이낸스 크롤링
    try:
        feed = feedparser.parse(rss_url)
        for entry in feed.entries:
            if yahoo_added >= YAHOO_MAX: break
            
            link = entry.get("link", "")
            title = entry.get("title", "")

            opinion_domains = [
                "fool.com", 
                "zacks.com", 
                "seekingalpha.com", 
                "investorplace.com"
            ]
            
            if any(domain in link for domain in opinion_domains):
                print(f"[Skip] 오피니언/칼럼 기사 배제: {title}")
                continue

            if not link or news_sp500_col.find_one({"link": link}) or news_general_col.find_one({"link": link}): 
                continue
                
            original_text = extract_article_text(link)
            if not original_text or len(original_text) < 50: continue
                
            try:
                dt_obj = parsedate_to_datetime(entry.published)
                timestamp = int(dt_obj.timestamp())
                iso_date = dt_obj.isoformat()
            except:
                timestamp = int(time.time())
                iso_date = datetime.datetime.now().isoformat()

            related_tickers = get_related_tickers(title, original_text)
            is_vip = len(related_tickers) > 0


            if is_vip:
                print(f"[Process] VIP SP500 article detected: {title}")
                col_to_insert = news_sp500_col
            else:
                print(f"[Process] General article detected: {title}")
                col_to_insert = news_general_col
            
            doc = {
                "source": "Yahoo RSS", 
                "link": link,
                "date": iso_date,
                "timestamp": timestamp,
                "title": title,
                "original": original_text, 
                "is_vip": is_vip,
                "related_tags": related_tickers
                
            }
            col_to_insert.insert_one(doc)
            yahoo_added += 1
            print(f"[Info] Yahoo article saved to {'SP500' if is_vip else 'General'}: {doc['title']}")
            
    except Exception as e:
        print(f"[Error] Yahoo RSS parsing failed: {e}")

    # 2. 핀허브 API 크롤링
    finnhub_api_key = os.getenv("FINNHUB_API_KEY")
    if finnhub_api_key:
        try:
            finnhub_url = f"https://finnhub.io/api/v1/news?category=general&token={finnhub_api_key}"
            res = requests.get(finnhub_url, timeout=10)
            if res.status_code == 200:
                finnhub_data = res.json()
                for item in finnhub_data:
                    if finnhub_added >= FINNHUB_MAX: break
                    
                    link = item.get("url", "")
                    title = item.get("headline", "")

                    title_lower = title.lower()
                    link_lower = link.lower()
                    
                    if "reuters" in title_lower or "bloomberg" in title_lower or "reuters.com" in link_lower or "bloomberg.com" in link_lower:
                        print(f"[Skip] 유료 매체 기사 배제 (제목 또는 URL 감지): {title}")
                        continue

                    finnhub_summary = item.get("summary", "")
                    
                    if not link or news_sp500_col.find_one({"link": link}) or news_general_col.find_one({"link": link}): 
                        continue
                        
                        
                    # 3. 정상 기사 스크래핑 처리
                    original_text = extract_article_text(link)
                    
                    # 스크래핑에 실패했거나 본문이 너무 짧은 경우 핀허브 요약본으로 대체
                    if not original_text or len(original_text) < 200:
                        original_text = finnhub_summary
                    
                    # 최종 텍스트 검증 (핀허브 요약본마저 부실한 경우 버림)
                    if not original_text or len(original_text) < 50:
                        print(f"[Skip] Insufficient text length: {title}")
                        continue
                        
                    timestamp = item.get("datetime", int(time.time()))
                    iso_date = datetime.datetime.fromtimestamp(timestamp).isoformat()
                    
                    related_tickers = get_related_tickers(title, original_text)
                    is_vip = len(related_tickers) > 0

                    if is_vip:
                        print(f"[Process] VIP SP500 article detected: {title}")
                        col_to_insert = news_sp500_col
                    else:
                        print(f"[Process] General article detected: {title}")
                        col_to_insert = news_general_col
                    
                    doc = {
                        "source": "Finnhub API",
                        "link": link,
                        "date": iso_date,
                        "timestamp": timestamp,
                        "title": title,
                        "original": original_text, 
                        "is_vip": is_vip,
                        "related_tags": related_tickers
                    }
                    col_to_insert.insert_one(doc)
                    finnhub_added += 1
                    print(f"[Info] Finnhub article saved to {'SP500' if is_vip else 'General'}: {doc['title']}")
        except Exception as e:
            print(f"[Error] Finnhub fetch failed: {e}")

    print(f"[System] Refresh complete. Yahoo: {yahoo_added}, Finnhub: {finnhub_added} added.")
    
    final_news = get_latest_news_from_db(50)
    return {"has_new": True, "news": final_news} 

class TranslateRequest(BaseModel):
    text: str
    url: str

@router.post("/translate")
async def translate_news(req: TranslateRequest):
    """프론트엔드 요청 시에만 동작하는 실시간 번역 API"""

    target_link = req.url.strip() if req.url else None

    if not req.text or len(req.text) < 5:
        return {"translated_text": ""}
    
    # 이미 번역된 내용이 DB에 존재하는지 확인
    if target_link:
        existing_news = news_sp500_col.find_one({"link": target_link}) or news_general_col.find_one({"link": target_link})
        if existing_news and existing_news.get("translated"):
            print(f"[Cache Hit] 이미 번역된 기사입니다.: {target_link}")
            return {"translated_text": existing_news["translated"]}
    
    # 번역 내용이 DB에 없는 경우 번역 수행
    try:
        translator = Translator()
        
        # 4000자로 자르는 대신, 문단 단위로 쪼개서 번역 후 이어붙임
        paragraphs = req.text.split('\n')
        translated_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                translated_paragraphs.append("")
                continue
            
            # 만약 하나의 문단이 너무 길 경우를 대비한 안전장치 (3000자씩 청크 분할)
            chunk_size = 3000
            para_chunks = [para[i:i+chunk_size] for i in range(0, len(para), chunk_size)]
            
            for chunk in para_chunks:
                result = translator.translate(chunk, src='en', dest='ko')
                translated_paragraphs.append(result.text)

        # 흩어진 한글 조각들을 다시 줄바꿈(\n)을 넣어 하나의 온전한 글로 조립
        final_translated_text = '\n'.join(translated_paragraphs)

        # DB에 번역본 저장 (translated 필드에 저장)
        if target_link:
            update_payload = {"$set": {"translated": final_translated_text}}
            
            res_sp500 = news_sp500_col.update_one({"link": target_link}, update_payload)
            res_general = news_general_col.update_one({"link": target_link}, update_payload)
            
            if (res_sp500.modified_count + res_general.modified_count) > 0:
                print(f"[DB Update Success] 번역본 DB 저장 완료: {target_link}")
            elif (res_sp500.matched_count + res_general.matched_count) == 0:
                print(f"[DB Update Failed] 번역을 저장할 기사를 찾지 못했습니다: {target_link}")

        return {"translated_text": final_translated_text}
        
    except Exception as e:
        print(f"[Error] Translation failed: {e}")
        return {"translated_text": "현재 번역 서비스를 일시적으로 사용할 수 없습니다."}
    

# Finnhub의 Rueter 등과 같은 유료 구독 매체 제거용
def cleanup_paywall_news():
    if news_sp500_col is None or news_general_col is None:
        return {"error": "DB 연결 안됨"}
        
    query = {
        "$or": [
            {"link": {"$regex": "reuters|bloomberg", "$options": "i"}},
            {"title": {"$regex": "reuters|bloomberg", "$options": "i"}}
        ]
    }
    
    try:
        res_sp500 = news_sp500_col.delete_many(query)
        res_general = news_general_col.delete_many(query)
        return {
            "sp500_deleted": res_sp500.deleted_count,
            "general_deleted": res_general.deleted_count
        }
    except Exception as e:
        return {"error": str(e)}

# # 2. 임시 실행용 API 엔드포인트
# @router.get("/admin/cleanup-paywall")
# async def trigger_cleanup():
#     result = cleanup_paywall_news()
#     return {"message": "정리 완료", "result": result}