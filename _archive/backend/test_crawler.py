import requests
import xml.etree.ElementTree as ET
from newspaper import Article, Config
from googletrans import Translator
from keybert import KeyBERT
import nltk
from nltk import pos_tag, word_tokenize

# NLTK 필수 데이터 다운로드 (최초 1회 실행 시 필요)
try:
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
    nltk.download("averaged_perceptron_tagger", quiet=True)
    nltk.download("averaged_perceptron_tagger_eng", quiet=True) # <--- 요 녀석이 범인!
except Exception:
    print("[Warning] NLTK resources download failed.")
    
# 네가 만든 constants.py에서 불용어 사전 가져오기 (같은 폴더에 있다고 가정)
try:
    from constants import STOPWORDS, GENERIC_KEYWORDS
    FINAL_STOPWORDS = list(STOPWORDS.union(GENERIC_KEYWORDS))
    print("[Info] Successfully loaded custom stopwords from constants.py")
except ImportError:
    print("[Warning] constants.py not found. Using default english stopwords.")
    FINAL_STOPWORDS = 'english'

print("[Info] Loading KeyBERT Model for Keyword Extraction...")
kw_model = KeyBERT()

def fetch_general_market_news(limit=2):
    """
    야후 파이낸스(Yahoo Finance) 다이렉트 RSS 피드에서 최신 시장 뉴스를 가져오는 함수
    (구글 뉴스의 리다이렉트 트랩을 우회하기 위함)
    """
    print("[Info] Fetching latest general market news from Yahoo Finance Direct RSS...")
    # 야후 파이낸스 다이렉트 마켓 뉴스 RSS
    url = "https://finance.yahoo.com/news/rss"
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        parsed_news = []
        
        # RSS 2.0 규격에 맞춰 item 파싱
        items = root.findall('.//channel/item')
        
        if not items:
            print("[Warning] No news items found in the RSS feed.")
            return []

        for item in items[:limit]:
            title_elem = item.find('title')
            link_elem = item.find('link')
            pub_date_elem = item.find('pubDate')
            
            parsed_news.append({
                "title": title_elem.text if title_elem is not None else "No Title",
                "publisher": "Yahoo Finance", # 다이렉트 피드이므로 고정
                "link": link_elem.text if link_elem is not None else "",
                "published_at": pub_date_elem.text if pub_date_elem is not None else "Unknown Time"
            })
            
        print("[Success] Successfully fetched " + str(len(parsed_news)) + " market news items.")
        return parsed_news

    except Exception as e:
        print("[Error] Failed to fetch general market news. Reason: " + str(e))
        return []

def extract_and_translate_article(url):
    """
    newspaper3k 본문 추출 -> googletrans 번역 파이프라인
    """
    print("[Info] Target Direct URL: " + url)
    print("[Info] Extracting article using newspaper3k...")
    result = {"original_text": "", "translated_text": ""}
    
    try:
        # newspaper3k 설정 (위장막 씌우기)
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        config = Config()
        config.browser_user_agent = user_agent
        config.request_timeout = 15
        
        # 다이렉트 URL이므로 리다이렉트 추적 없이 바로 파싱
        article = Article(url, config=config)
        article.download()
        article.parse()
        
        original_text = article.text.strip()
        
        if not original_text:
            print("[Warning] Article parsed but text is empty. Might be a video-only article or blocked.")
            return result
            
        result["original_text"] = original_text
        print("[Success] Original text extracted. Length: " + str(len(original_text)) + " characters.")
        
        # Googletrans로 한글 번역 (안전성을 위해 최대 1500자 제한)
        print("[Info] Translating text to Korean...")
        translator = Translator()
        
        text_to_translate = original_text[:1500] 
        translation = translator.translate(text_to_translate, src='en', dest='ko')
        
        result["translated_text"] = translation.text
        print("[Success] Translation completed.")
        
        return result
        
    except Exception as e:
        print("[Error] Extraction or translation failed. Reason: " + str(e))
        return result
    
def extract_fact_keywords(text, top_n=4):
    """
    기사 본문에서 객관적 팩트 키워드(#)를 추출하는 함수 (NLTK 품사 필터링 적용)
    """
    print("[Info] Extracting key facts with advanced NLP filtering...")
    try:
        # 1. 야후 파이낸스 특유의 광고 문구 1차 제거 (전처리)
        clean_text = text.replace("Will AI create the world's first trillionaire?", "")
        clean_text = clean_text.replace("Image source: Getty Images.", "")
        
        # 2. KeyBERT로 넉넉하게 후보군 추출 (불용어 사전 적용)
        candidates = kw_model.extract_keywords(
            clean_text,
            keyphrase_ngram_range=(1, 2),
            stop_words=FINAL_STOPWORDS,
            use_mmr=True,
            diversity=0.7,
            top_n=top_n * 4  # 필터링을 위해 후보를 많이 뽑음
        )
        
        # 3. NLTK를 활용해 명사(Noun) 위주로만 필터링 (pipeline.py 로직 차용)
        final_keywords = []
        seen_kws = set()
        
        for kw, score in candidates:
            if kw in seen_kws:
                continue
                
            tokens = word_tokenize(kw)
            tags = pos_tag(tokens)
            
            has_noun = False
            is_bad = False
            
            for word, tag in tags:
                if tag.startswith("NN"): # 명사가 포함되어 있는지 확인
                    has_noun = True
                if tag.startswith(("VB", "RB", "IN", "CC", "DT")): # 동사, 부사, 전치사 등 쓰레기 품사 제외
                    is_bad = True
                    break
                    
            if has_noun and not is_bad:
                # 띄어쓰기를 언더바(_)로 바꾸고 해시태그 붙이기
                formatted_kw = "#" + kw.replace(" ", "_")
                final_keywords.append(formatted_kw)
                seen_kws.add(kw)
                
            if len(final_keywords) >= top_n:
                break
                
        print("[Success] Extracted " + str(len(final_keywords)) + " high-quality keywords.")
        return final_keywords
        
    except Exception as e:
        print("[Error] Keyword extraction failed. Reason: " + str(e))
        return []

if __name__ == "__main__":
    recent_news = fetch_general_market_news(limit=2) 
    
    if recent_news:
        target_news = recent_news[0]
        print("-" * 70)
        print("Target Title: " + target_news['title'])
        print("Target Link: " + target_news['link'])
        print("-" * 70)
        
        extracted_data = extract_and_translate_article(target_news['link'])
        
        if extracted_data['original_text']:
            print("\n[ ORIGINAL ENGLISH TEXT (First 500 chars) ]")
            print(extracted_data['original_text'][:500] + "...\n")
            
            print("-" * 70)
            
            print("[ TRANSLATED KOREAN TEXT (First 500 chars) ]")
            print(extracted_data['translated_text'][:500] + "...\n")
            print("-" * 70)
            
        if extracted_data['original_text']:
            print("\n[ EXTRACTED FACT KEYWORDS ]")
            # 영어 원문에서 키워드를 뽑는 것이 정확도가 훨씬 높음
            tags = extract_fact_keywords(extracted_data['original_text'])
            print("Tags: " + " ".join(tags))
            print("-" * 70)