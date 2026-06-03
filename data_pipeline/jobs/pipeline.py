import os
import re
import sys
import pandas as pd
import wikipedia
import yfinance as yf
import torch
from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from nltk import pos_tag, word_tokenize

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.constants import MANUAL_MAPPING, STOPWORDS, GENERIC_KEYWORDS

wikipedia.set_lang("en")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = os.path.join(BASE_DIR, "../sp500_full_wiki.jsonl")
OUTPUT_FILE = os.path.join(BASE_DIR, "../sp500_sbert_input.jsonl")

print("Loading KeyBERT Model (BGE-M3)")

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using Device: {device.upper()}")

sentence_model = SentenceTransformer("BAAI/bge-m3", device=device)
kw_model = KeyBERT(model=sentence_model)

try:
    import nltk

    nltk.download("stopwords", quiet=True)
    nltk.download("punkt", quiet=True)
    nltk.download("punkt_tab", quiet=True)
    nltk.download("averaged_perceptron_tagger", quiet=True)
except Exception:
    print("NLTK resources are unavailable; please prepare preprocessing environment.")


FINAL_STOPWORDS = set(STOPWORDS)
FINAL_STOPWORDS.update(GENERIC_KEYWORDS)


def clean_company_name(name):
    name = re.sub(r"\s*\(.*?\)", "", name)
    name = re.sub(r"\.com", "", name)
    return name.strip()


def clean_text_basic(text):
    if not text:
        return ""
    text = re.sub(r"\[\d+\]", " ", text)
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"\b\d+\b", " ", text)
    text = re.sub(r"[^a-zA-Z\s.,]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def fetch_yfinance_summary(ticker):
    try:
        stock = yf.Ticker(ticker)
        return stock.info.get("longBusinessSummary", "")
    except:
        return ""


def solve_disambiguation(options):
    keywords = ["company", "corporation", "inc", "tech", "retail", "holdings"]
    for opt in options:
        for k in keywords:
            if k in opt.lower():
                return opt
    return options[0]


def get_wiki_data(name, ticker):
    """
    위키피디아에서 '요약문(Summary)'과 '본문(Content)'를 분리해서 가져옴
    """
    try:
        query = MANUAL_MAPPING.get(ticker, clean_company_name(name))

        # 1. 검색
        search_results = wikipedia.search(query)
        if not search_results:
            search_results = wikipedia.search(ticker)
            if not search_results:
                return "", ""

        target_page = search_results[0]

        # 2. 페이지 객체 생성
        try:
            page = wikipedia.page(target_page, auto_suggest=False)
        except wikipedia.DisambiguationError as e:
            resolved_page = solve_disambiguation(e.options)
            try:
                page = wikipedia.page(resolved_page, auto_suggest=False)
            except:
                return "", ""
        except wikipedia.PageError:
            return "", ""

        # 요약문과 본문을 따로 가져옴
        summary = page.summary
        content = page.content

        # 본문 정제 (레퍼런스 제거)
        if "== References ==" in content:
            content = content.split("== References ==")[0]

        return summary.strip(), content.strip()

    except Exception:
        return "", ""


def extract_strict_keywords(text, ticker_name_parts, top_n=30):
    current_stops = list(FINAL_STOPWORDS) + ticker_name_parts

    candidates = kw_model.extract_keywords(
        text,
        keyphrase_ngram_range=(1, 2),
        stop_words=current_stops,
        use_mmr=True,
        diversity=0.7,
        top_n=top_n * 3,
    )

    final_keywords = []
    seen_kws = set()

    for kw, score in candidates:
        if kw in seen_kws:
            continue

        try:
            tokens = word_tokenize(kw)
            tags = pos_tag(tokens)
        except Exception:
            tags = []

        has_noun = False
        is_bad = False

        for word, tag in tags:
            if tag.startswith("NN"):
                has_noun = True
            if tag.startswith(("VB", "RB", "IN", "CC", "DT")):
                is_bad = True
                break

        if len(kw) < 3 and kw != "ai":
            is_bad = True

        if has_noun and not is_bad:
            final_keywords.append(kw)
            seen_kws.add(kw)

        if len(final_keywords) >= top_n:
            break

    return ", ".join(final_keywords)


def run():
    if not os.path.exists(INPUT_FILE):
        print(f"{INPUT_FILE} not found. Run 'crawling.py'")
        return

    df = pd.read_json(INPUT_FILE, lines=True)
    final_data = []
    seen_companies = set()

    for idx, row in tqdm(df.iterrows(), total=len(df)):
        ticker = row["Ticker"]
        raw_name = row["Name"]

        clean_name = clean_company_name(raw_name)
        if clean_name in seen_companies:
            continue
        seen_companies.add(clean_name)

        wiki_summary, wiki_content = get_wiki_data(raw_name, ticker)
        yf_summary = fetch_yfinance_summary(ticker)

        keyword_source = f"{yf_summary} {wiki_summary}"
        cleaned_source = clean_text_basic(keyword_source)

        auto_keywords = ""
        try:
            if len(cleaned_source) > 50:
                name_parts = clean_name.lower().split() + [ticker.lower()]
                auto_keywords = extract_strict_keywords(cleaned_source, name_parts)
        except Exception:
            auto_keywords = ""

        context_text = clean_text_basic(wiki_content)
        if len(context_text) > 3000:
            context_text = context_text[:3000]

        enriched_text = (
            f"Ticker: {ticker}. Name: {clean_name}. "
            f"Keywords: {auto_keywords}. "
            f"Summary: {yf_summary}. {wiki_summary}"
        )

        if context_text:
            enriched_text += f" Context: {context_text}"

        final_data.append(
            {
                "Ticker": ticker,
                "Name": clean_name,
                "Enriched_Text": enriched_text,
                "Generated_Keywords": auto_keywords,
            }
        )

    result_df = pd.DataFrame(final_data)
    result_df.to_json(OUTPUT_FILE, orient="records", lines=True, force_ascii=False)
    print("Pipeline Complete")


if __name__ == "__main__":
    run()
