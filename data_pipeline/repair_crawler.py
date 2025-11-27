import pandas as pd
import wikipedia
import time
from tqdm import tqdm
import re

wikipedia.set_lang("en")

# 정확하게 매칭되지 않은 기업을 수동으로 매핑
MANUAL_MAPPING = {
    "PODD": "Insulet",            # Insulet Corporation -> Insulet
    "BF-B": "Brown-Forman",       # Brown-Forman Corp -> Brown-Forman
    "BRK-B": "Berkshire Hathaway",# Berkshire Hathaway Inc. -> Berkshire Hathaway
    "SOLV": "Solventum",          # Solventum -> Solventum (최근 분사 기업 등)
    "KVUE": "Kenvue"              # Kenvue -> Kenvue
}

def clean_company_name(name):
    """
    단순 .page로 찾지 못한 기업의 정보를 추출
    기업명에서 불필요한 접미사를 제거해서 검색 정확도를 올림
    """
    
    name = re.sub(r'\s*\(.*?\)', ' ', name)
    
    suffixes = [
        r'\bInc\.?', r'\bIncorporated\b', 
        r'\bCorp\.?', r'\bCorporation\b', 
        r'\bLtd\.?', r'\bLimited\b', 
        r'\bP\.?L\.?C\.?', 
        r'\bCompany\b', r'\bCo\.?'
        r'\bGroup\b', r'\bHoldings\b'
    ]
    
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)

    name = re.sub(r'\.com', '', name, flags=re.IGNORECASE)
    
    return name.strip()

def solve_disambiguation(options):
    """
    동명이인 목록 중에서 기업일 확률이 높은 부분을 찾음
    """
    keywords = ['company', 'corporation', 'inc', 'tech', 'retail', 'holdings']
    
    for opt in options:
        for k in keywords:
            if k in opt.lower():
                return opt
            
    return options[0]

def smart_search_company(name, ticker):
    """
    1. 정확한 이름으로 시도
    2. 실패 시 위키피디아 검색 API로 가장 유사한 페이지를 찾아서 시도
    """
    try:
        if ticker in MANUAL_MAPPING:
            search_query = MANUAL_MAPPING[ticker]
        else:
            search_query = clean_company_name(name)
        
        search_results = wikipedia.search(search_query)
        
        if not search_results:
            return "", "Fail_ReallyNotFound"
        
        best_match = search_results[0]
        
        try:
            page = wikipedia.page(best_match, auto_suggest = False)
        except wikipedia.exceptions.DisambiguationError as e:
            best_match = solve_disambiguation(e.options)
            try:
                page = wikipedia.page(best_match, auto_suggest = False)
            except:
                return "", "Fail_StillAmbiguous"
        except wikipedia.exceptions.PageError:
            try:
                page = wikipedia.page(name, auto_suggest = True)
            except:
                return "", "Fail_PageError"
            
        raw_content = page.content
        
        patterns = [r"==\s*References\s*==", r"==\s*External links\s*==", r"==\s*See also\s*=="]
        for pattern in patterns:
            match = re.search(pattern, raw_content, re.IGNORECASE)
            if match:
                raw_content = raw_content[:match.start()]
                
        return raw_content.strip(), "Success"
    
    except Exception as e:
        return "", "Fail_Error"
    
if __name__ == "__main__":
    input_file = "sp500_full_wiki_repaired.jsonl"
    
    df = pd.read_json(input_file, lines = True)
    
    df['Status'] = df['Status'].astype(str).str.strip()
    
    fail_mask = df['Status'].str.contains('Fail', case=False, na=False) | (df['Status'] == 'Error')
    
    fail_indices = df[fail_mask].index
    
    print(f"Retrying {len(fail_indices)} failed entries...")
    
    if len(fail_indices) > 0:
        for idx in tqdm(fail_indices):
            original_name = df.loc[idx, 'Name']
            ticker = df.loc[idx, 'Ticker']
            
            # 수리 시도
            content, status = smart_search_company(original_name, ticker)
            
            if status == "Success":
                df.loc[idx, 'Full_Wiki_Text'] = content
                df.loc[idx, 'Status'] = "Success_Repaired"
            else:
                df.loc[idx, 'Status'] = status
            
            time.sleep(1.0)
            
        output_file = 'sp500_full_wiki_repaired.jsonl'
        df.to_json(output_file, orient='records', lines=True, force_ascii=False)
        
        print("\nFinal Status Counts:")
        print(df['Status'].value_counts())
        print(f"Saved to {output_file}")
    else:
        print("실패한 항목을 찾지 못했습니다. 코드를 다시 확인해주세요.")