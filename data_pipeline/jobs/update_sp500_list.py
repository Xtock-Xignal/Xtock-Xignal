import os
import re
from io import StringIO

import pandas as pd
import requests


def clean_company_name_for_dedup(name):
    """
    중복 제거를 위해 기업 이름 단순화
    Ex: 'Alphabet Inc. (Class A)' -> 'Alphabet Inc.'
    """
    name = re.sub(r"\s*\(.*?\)", "", name)
    return name.strip()


def update_sp500_metadata():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    CSV_DIR = os.path.join(BASE_DIR, "../backend/csv")
    CSV_PATH = os.path.join(CSV_DIR, "sp500_list.csv")

    os.makedirs(CSV_DIR, exist_ok=True)

    print("Fetching latest S*P 500 list from Wikipedia")
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        dfs = pd.read_html(StringIO(response.text))
        df = dfs[0]

        df = df[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]]
        df.columns = ["ticker", "name", "sector", "industry_group"]
    except Exception as e:
        print(f"Failed to fetch from Wikipedia: {e}")
        return

    print("Cleaning and Deduplicating")

    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    df["CleanName"] = df["name"].apply(clean_company_name_for_dedup)

    before_count = len(df)
    df = df.drop_duplicates(subset=["CleanName"], keep="first")
    df = df.drop(columns=["CleanName"])
    after_count = len(df)
    removed_count = before_count - after_count

    print(f"   - Removed {removed_count} duplicates (e.g., GOOG/GOOGL).")
    print(f"   - Final count: {after_count} companies.")

    df.to_csv(CSV_PATH, index=False, encoding="utf-8")
    print(f"Saved updated list to :{CSV_PATH}")


if __name__ == "__main__":
    update_sp500_metadata()

