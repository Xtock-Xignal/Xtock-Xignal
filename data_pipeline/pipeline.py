import pandas as pd
import wikipedia
import yfinance as yf
from keybert import KeyBERT
from tqdm import tqdm
import re
import time
import nltk
import os
from nltk.corpus import stopwords

wikipedia.set_lang("en")

kw_model = KeyBERT(model = 'all-MiniLM-L6-v2')

nltk.download('stopwords')
stop_words = stopwords.words('english')
custom_stopwords = ['inc', 'corp', 'company', 'ltd', 'incorporated', 'group', 'class', 'plc', 'holding', 'holdings']
stop_words.extend(custom_stopwords)

MANUAL_MAPPING = {
    "POOD": "Insulet",
    "BF-B": "Brown-Forman",
    "BPK-B": "Berkshire Hathaway",
    "SOLV": "Solventum",
    "KVUE": "Kenvue"
}

def clean_company_name(name):
    name = re.sub(r'\s*\(.*?\)', ' ', name)
    suffixes = [
        r'\bInc\.?', r'\bIncorporated\b', 
        r'\bCorp\.?', r'\bCorporation\b', 
        r'\bLtd\.?', r'\bLimited\b', 
        r'\bP\.?L\.?C\.?', 
        r'\bCompany\b', r'\bCo\.?',
        r'\bGroup\b', r'\bHoldings\b'
    ]
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags = re.IGNORECASE)
    name = re.sub(r'\.com', '', name, flags = re.IGNORECASE)
    return name.strip()

def solve_disambiguation(options):
    keywords = ['company', 'corporation', 'inc', 'tech', 'retail', 'holdings']
    for opt in options:
        for k in keywords:
            if k in opt.lowe():
                return opt
    return options[0]

def smart_search_company(name, ticker):
    try:
        if ticker in MANUAL_MAPPING:
            search_query = MANUAL_MAPPING[ticker]
        else:
            search_query = clean_company_name(name)
            
        search_results = wikipedia.search(search_query)
        if not search_results:
            search_results = wikipedia.search(ticker)
            if not search_results:
                return "", "Fail_NotFound"
            
        target_page_title = search_results[0]
        
        try:
            page = wikipedia.page(target_page_title, auto_suggest = False)
        except wikipedia.DisambiguationError as e:
            target_page_title = solve_disambiguation(e.options)
            try:
                page = wikipedia.page(target_page_title, auto_suggest = False)
            except: return "", "Fail_Ambiguous"
        except wikipedia.exceptions.PageError:
            try:
                page = wikipedia.page(search_query, auto_suggest = True)
            except: return "", "Fail_PageError"
        
        raw_content = page.content
        patterns = [r"== See also ==.*", r"== References ==.*", r"== External links ==.*"]
        for pattern in patterns:
            match = re.search(pattern, raw_content, flags = re.IGNORECASE)
            if match:
                raw_content = raw_content[:match.start()]
        
        return raw_content, "Success"
    except:
        return "", "Fail_UnknownError"
    
def fetch_yfinance_summary(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.info.get('longBusinessSummary', "")
    except:
        return ""
    
def clean_text_basic(text):
    if not text:
        return ""
    text = re.sub(r'\[d+\]', ' ', text)
    text = re.sub(r'http\S+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

if __name__ == "__main__":
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(BASE_DIR, 'sp500_full_wiki.jsonl')
    output_file = os.path.join(BASE_DIR, 'sp500_sbert_input.jsonl')
    
    df = pd.read_json(input_file, lines = True)
    
    df['Status'] = df['Status'].astype(str).str.strip()
    
    final_data = []
    
    for idx, row in tqdm(df.iterrows(), total = len(df)):
        ticker = row['Ticker']
        name = row['Name']
        status = row['Status']
        wiki_text = row.get('Full_Wiki_Text', "")
        
        is_failed = "Fail" in status or status == "Error" or len(wiki_text) < 50
        
        if is_failed:
            new_content, new_status = smart_search_company(name, ticker)
            
            if "Success" in new_status:
                wiki_text = new_content
                
            else:
                wiki_text = ""
                
        yf_summary = fetch_yfinance_summary(ticker)
        
        combined_text = f"{yf_summary} {wiki_text}"
        cleaned_source = clean_text_basic(combined_text)
        
        auto_keywords = ""
        try:
            if len(cleaned_source) > 50:
                keywords_list = kw_model.extract_keywords(
                    cleaned_source,
                    keyphrase_ngram_range = (1, 2),
                    stop_words = stop_words,
                    top_n = 50
                )
                auto_keywords = ", ".join([k[0] for k in keywords_list])
        except:
            pass
        
        enriched_text = (
            f"Ticker: {ticker}. Name: {name}. "
            f"Keywords: {auto_keywords}. "
            f"Summary: {yf_summary}. "
        )
        
        if len(cleaned_source) < 100 and len(wiki_text) > 100:
            enriched_text += f" Context: {clean_text_basic(wiki_text)[:500]}"
            
        final_data.append({
            "Ticker": ticker,
            "Name": name,
            "Enriched_Text": enriched_text,
            "Generated_Keywords": auto_keywords
        })
        
        time.sleep(0.1)
        
    result_df = pd.DataFrame(final_data)
    result_df.to_json(output_file, orient = 'records', lines = True, force_ascii = False)
    
    print("Pipeline Complete")