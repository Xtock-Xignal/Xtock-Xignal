import yaml
import yfinance as yf
import pandas as pd
import os
import time
import sys
from pathlib import Path
from newspaper import Article, Config
from tqdm import tqdm

# 프로젝트 루트 및 모듈 경로 설정
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# 내부 모듈 임포트
try:
    from pipelines.common import ensure_dir
    from pipelines.fasttext.preprocessing import normalize_label as normalize_fasttext_label
    from pipelines.fasttext.preprocessing import normalize_text as normalize_fasttext_text
    from pipelines.fasttext.preprocessing import to_fasttext_line
    from pipelines.tfidf_randomforest.preprocessing import build_stopword_strategy, preprocess_text
except ImportError:
    def ensure_dir(path):
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
        return path

# 설정 경로
CONFIG_PATH = ROOT_DIR / "config" / "products_and_services.yaml"
DATASETS_DIR = ensure_dir(ROOT_DIR / "datasets")
RAW_OUTPUT_PATH = DATASETS_DIR / "news_raw.csv"
FASTTEXT_OUTPUT_PATH = DATASETS_DIR / "news_fasttext.csv"
TFIDF_OUTPUT_PATH = DATASETS_DIR / "news_tfidf.csv"

# newspaper3k 설정
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
config = Config()
config.browser_user_agent = user_agent
config.request_timeout = 5

def load_industry_mapping():
    if not CONFIG_PATH.exists(): return {}
    with open(CONFIG_PATH, 'r') as f:
        try: return yaml.safe_load(f)
        except: return {}

def extract_article_body(url):
    if not url: return ""
    try:
        article = Article(url, config=config)
        article.download()
        article.parse()
        return article.text.strip()
    except: return ""

def generate_datasets(raw_data_list):
    if not raw_data_list: return
    fasttext_rows = []
    for entry in raw_data_list:
        try:
            ft_line = to_fasttext_line(entry['Full Text'], entry['Industry'])
            if ft_line:
                fasttext_rows.append({
                    "text": entry['Full Text'],
                    "label": entry['Industry'],
                    "normalized_text": normalize_fasttext_text(entry['Full Text']),
                    "normalized_label": normalize_fasttext_label(entry['Industry']),
                    "fasttext_line": ft_line
                })
        except: continue
    
    try:
        pd.DataFrame(fasttext_rows).to_csv(FASTTEXT_OUTPUT_PATH, index=False, encoding='utf-8-sig')
    except: pass
    
    try:
        corpus = [entry['Full Text'] for entry in raw_data_list]
        custom_strategy = build_stopword_strategy(corpus, strategy="custom_tfidf")
        custom_stopwords = custom_strategy.stopwords
        
        tfidf_rows = []
        for entry in raw_data_list:
            tfidf_rows.append({
                "text": entry['Full Text'],
                "label": entry['Industry'],
                "tfidf_text_max_df": preprocess_text(entry['Full Text']),
                "tfidf_text_custom_stopwords": preprocess_text(entry['Full Text'], stopwords=custom_stopwords)
            })
        pd.DataFrame(tfidf_rows).to_csv(TFIDF_OUTPUT_PATH, index=False, encoding='utf-8-sig')
    except: pass
    print(f"  >>> Preprocessed datasets saved.")

def collect_and_process(limit_per_ticker=10): # 기본값을 10으로 변경
    mapping = load_industry_mapping()
    if not mapping: return

    all_data = []
    seen_urls = set()
    industries = list(mapping.keys())
    
    print(f"=== Unified Pipeline: Collecting & Preprocessing ({limit_per_ticker} per ticker) ===")

    pbar_industry = tqdm(industries, desc="Industries")
    for industry in pbar_industry:
        pbar_industry.set_description(f"Ind: {industry[:10]}...")
        tickers = mapping.get(industry, [])
        if not tickers: continue
        
        pbar_tickers = tqdm(tickers, desc=f"  Tickers", leave=False)
        for ticker_symbol in pbar_tickers:
            pbar_tickers.set_description(f"    Tkr: {ticker_symbol}")
            try:
                ticker = yf.Ticker(ticker_symbol)
                news_list = ticker.news
                if not news_list: continue
                
                ticker_count = 0
                for item in news_list:
                    if ticker_count >= limit_per_ticker: break
                    
                    content = item.get('content', {})
                    if not content: continue
                    
                    title = content.get('title')
                    link = None
                    for key in ['clickThroughUrl', 'canonicalUrl']:
                        if isinstance(content.get(key), dict):
                            link = content[key].get('url')
                            if link: break
                    if not link: link = content.get('link')

                    if link and link not in seen_urls:
                        body = extract_article_body(link)
                        if not body or len(body) < 100:
                            body = content.get('summary', content.get('description', title))
                        if body:
                            all_data.append({
                                'Title': title,
                                'Full Text': body,
                                'Industry': industry
                            })
                            seen_urls.add(link)
                            ticker_count += 1
                time.sleep(0.05) # 대량 수집을 위해 딜레이 약간 축소
            except: continue

    if all_data:
        pd.DataFrame(all_data).to_csv(RAW_OUTPUT_PATH, index=False, encoding='utf-8-sig')
        print(f"\n✅ Raw data saved to {RAW_OUTPUT_PATH}")
        print("💡 Generating preprocessed datasets...")
        generate_datasets(all_data)

if __name__ == "__main__":
    collect_and_process(limit_per_ticker=10) # 10개 수집 설정
    print("\n=== Unified Data Pipeline Complete ===")
