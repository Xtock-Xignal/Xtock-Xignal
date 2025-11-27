import pandas as pd
import wikipedia
import time
from tqdm import tqdm
import requests
from io import StringIO
import re

# Language Setting (한글보다는 영어가 더 정보가 많고 NLP 처리하기 쉬움)
wikipedia.set_lang("en")

def get_sp500_list():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers = headers)
        
        if response.status_code == 200:
            print("Access Success")
            dfs = pd.read_html(StringIO(response.text))
            print(f"Total Tables Extracted: {len(dfs)}")
            
            target_df = None
            for i, table in enumerate(dfs):
                if 'Symbol' in table.columns:
                    target_df = table
                    break
            if target_df is None:
                print("No table with 'Symbol' column found.")
                return None
            df = target_df[['Symbol', 'Security', 'GICS Sector']]
            
            df['Symbol'] = df['Symbol'].str.replace('.', '-', regex = False)
            return df
        else:
            print(f"Access Fail: {response.status_code}")
            return None
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
        return None
    
def clean_wiki_text(text):
    """Remove unnecessary bottom information"""
    if not text: return ""
    patterns = [r"==\s*References\s*==", r"==\s*External links\s*==", r"==\s*See also\s*=="]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            text = text[:match.start()]
    return text.strip()

def fetch_full_contents(df):
    """Collect full text for each company"""
    print(f"\n Starting FULL-TEXT crawler for {len(df)} companies...")
    results = []
    
    for idx, row in tqdm(df.iterrows(), total=len(df)):
        ticker = row['Symbol']
        name = row['Security']
        sector = row['GICS Sector']
        
        status = "Success"
        full_content = ""
        
        try:
            page = wikipedia.page(name, auto_suggest=False)
            full_content = clean_wiki_text(page.content)
        except wikipedia.exceptions.DisambiguationError as e:
            try:
                page = wikipedia.page(e.options[0], auto_suggest=False)
                full_content = clean_wiki_text(page.content)
                status = "Ambiguous_Resolved"
            except:
                status = "Fail_Ambiguous"
        except wikipedia.exceptions.PageError:
            status = "Fail_NotFound"
        except Exception:
            status = "Error"
            
        results.append({
            "Ticker": ticker,
            "Name": name,
            "Sector": sector,
            "Full_Wiki_Text": full_content,
            "Status": status
        })
        time.sleep(1.0)
        
    return pd.DataFrame(results)

if __name__ == "__main__":
    
    sp500 = get_sp500_list()
   
    target_df = sp500
    
    final_df = fetch_full_contents(target_df)
    
    filename = "sp500_full_wiki.jsonl"
    
    final_df.to_json(filename, orient='records', lines=True, force_ascii=False)
    
    print(f"\nDone! Saved to {filename}")