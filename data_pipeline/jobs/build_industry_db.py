import json
from pathlib import Path

import pandas as pd
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parent

SP500_CSV = BASE_DIR / "../backend/csv/sp500_list.csv"
INPUT_JSONL = BASE_DIR / "sp500_sbert_input.jsonl"
OUT_DIR = BASE_DIR / "../backend/json/industry_group"


def build_industry_keywords():
    print("Checking inputs")
    if not SP500_CSV.exists():
        print(f"Error: {SP500_CSV} not found. Run update_sp500_list.py")
        return
    if not INPUT_JSONL.exists():
        print(f"Error: {INPUT_JSONL} not found. Run pipeline.py")
        return

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading Industry Mapping")
    df_sp = pd.read_csv(SP500_CSV)
    ticker_to_group = dict(zip(df_sp["ticker"], df_sp["industry_group"]))

    print("Aggregating Keywords by Industry")
    industry_keywords_map = {}

    with open(INPUT_JSONL, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc="Processing Tickers"):
            try:
                item = json.loads(line)
                ticker = item["Ticker"]

                group = ticker_to_group.get(ticker, "Unknown")
                if group == "Unknown":
                    continue

                raw_kwd = item.get("Generated_Keywords", "")
                if not raw_kwd:
                    continue

                kw_list = [k.strip().lower() for k in raw_kwd.split(",") if k.strip()]
                if group not in industry_keywords_map:
                    industry_keywords_map[group] = set()
                industry_keywords_map[group].update(kw_list)
            except Exception:
                continue

    print(f"Saving {len(industry_keywords_map)} Industry Groups to {OUT_DIR}")

    for group, keywords in industry_keywords_map.items():
        safe_name = group.replace("/", "_").replace(" ", "_").replace("&", "and")
        file_path = OUT_DIR / f"{safe_name}.json"
        payload = {
            "industry_group": group,
            "keywords": sorted(list(keywords)),
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)

    print("Industry Database Build Complete")


if __name__ == "__main__":
    build_industry_keywords()

