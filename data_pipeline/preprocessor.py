import pandas as pd
import re
import nltk
from nltk.corpus import stopwords
from tqdm import tqdm

nltk.download('stopwords')
nltk.download('punkt')
nltk.download('punkt_tab')

def clean_text_basic(text):
    """
    기본적인 노이즈(인용 번호, 특수 문자 등)만 제거하여 문장의 context를 보존
    SBERT는 문장의 context를 파악하기 때문에 keyword만 남길 경우 성능 하락 가능성
    """
    if not text:
        return ""
    
    # 인용 번호 제거 ([1], [2], ...)
    text = re.sub(r'\[\d+\]', ' ', text)
    
    # URL 제거
    text = re.sub(r'http\S+', ' ', text)
    
    # 연속된 공백, 줄바꿈을 공백 하나로 통일
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()

def extract_keywords(text, top_n = 50):
    """
    stopwords 및 특수문자를 전부 제거 후 상위 n개의 단어는 추출
    SBERT는 full text를 입력하지 못하기 때문에 keyword + full text의 초반 1000자의 조합으로 사용
    """
    
    if not text:
        return ""
    
    # 소문자 변환 및 알파벳만 남기기
    text = re.sub(r'[^a-zA-Z\s]', ' ', text.lower())
    
    # 단어 토큰화
    words = text.split()
    
    # stopwords load
    stop_words = set(stopwords.words('english'))
    
    # stopword 제거 및 의미있는 단어 필터링
    meaningful_words = [w for w in words if w not in stop_words and len(w) > 2]
    
    # 순서를 유지하면서 중복 제거
    seen = set()
    keywords = []
    for w in meaningful_words:
        if w not in seen:
            seen.add(w)
            keywords.append(w)
            if len(keywords) >= top_n:
                break
    
    return ", ".join(keywords)

if __name__ == "__main__":
    input_file = "sp500_full_wiki_repaired.jsonl"
    print(f"Loading data from {input_file}")
    df = pd.read_json(input_file, lines = True)
    
    processed_data = []
    
    print("Cleaninfd data & Creating SBERT inputs")
    for idx, row in tqdm(df.iterrows(), total = len(df)):
        raw_text = row.get('Full_Wiki_Text', "")
        
        clean_body = clean_text_basic(raw_text)
        
        truncated_body = clean_body[:1000]
        
        keywords = extract_keywords(raw_text, top_n = 50)
        
        enriched_text = (
            f"Ticker: {row['Ticker']}. "
            f"Name: {row['Name']}. "
            f"Keywords: {keywords}. "
            f"Summary: {truncated_body}"
        )
        
        processed_data.append({
            "Ticker": row['Ticker'],
            "Name": row['Name'],
            "Enriched_Text": enriched_text,
            "Keywords_only": keywords
        })
        
    result_df = pd.DataFrame(processed_data)
    output_file = "sp500_sbert_input.jsonl"
    result_df.to_json(output_file, orient='records', lines = True, force_ascii = False)
    
    print(f"\n Preprocessing Complete")
    
    print(result_df.iloc[0]['Enriched_Text'][:300] + "...")