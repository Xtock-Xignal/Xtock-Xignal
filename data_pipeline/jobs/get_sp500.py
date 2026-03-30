import json

import pandas as pd
import requests
from io import StringIO

OUTPUT_FILE = "frontend/data/sp500_list.js"


def generate_sp500_list():
    print("🚀 Fetching S&P 500 list from Wikipedia (with User-Agent)...")

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

        tables = pd.read_html(StringIO(response.text))
        df = tables[0]
        df = df[["Symbol", "Security"]]

        clean_list = []
        seen_companies = set()

        for _, row in df.iterrows():
            ticker = row["Symbol"]
            name = row["Security"]
            simple_name = name.split(" (Class")[0].strip()

            if simple_name in seen_companies:
                continue

            seen_companies.add(simple_name)
            clean_list.append({"symbol": ticker, "name": simple_name})

        print(f"✅ Processed {len(clean_list)} unique companies.")

        js_content = f"""// S&P 500 Companies List (Auto-generated)
// Total Companies: {len(clean_list)}

export const SP500_LIST = {json.dumps(clean_list, indent=2)};
"""

        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write(js_content)

        print(f"🎉 Successfully saved to {OUTPUT_FILE}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    generate_sp500_list()

