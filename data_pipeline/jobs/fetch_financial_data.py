import json
import os
import time

import pandas as pd
import yfinance as yf
from tqdm import tqdm

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "../backend/csv/sp500_list.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "sp500_financials.jsonl")


def format_large_number(num):
    """큰 숫자를 읽기 좋게 변환 (Billion, Trillion)"""
    if not num:
        return "N/A"
    if num >= 1_000_000_000_000:
        return f"${num / 1_000_000_000_000:.2f}T"
    if num >= 1_000_000_000:
        return f"${num / 1_000_000_000:.2f}B"
    if num >= 1_000_000:
        return f"${num / 1_000_000:.2f}M"
    return f"${num}"


def fetch_financial_metrics():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    df = pd.read_csv(CSV_PATH)
    financial_data = []

    print(f"Fetching Real-time Metrics for {len(df)} companies...")

    for _, row in tqdm(df.iterrows(), total=len(df)):
        ticker = row["ticker"]
        name = row["name"]

        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            price = info.get("currentPrice", info.get("regularMarketPrice", "N/A"))
            mkt_cap = format_large_number(info.get("marketCap"))
            revenue_growth = info.get("revenueGrowth", 0)
            if revenue_growth != "N/A":
                revenue_growth = f"{revenue_growth * 100:.1f}%"

            profit_margin = info.get("profitMargins", 0)
            if profit_margin != "N/A":
                profit_margin = f"{profit_margin * 100:.1f}%"

            sector = info.get("sector", "Unknown")
            recommendation = info.get("recommendationKey", "none").replace("_", " ").title()

            fin_text = (
                f"{name} ({ticker}) operates in the {sector} sector. "
                f"As of today, the stock is trading at ${price}. "
                f"It has a market capitalization of {mkt_cap}. "
                f"Recent revenue growth is {revenue_growth}, with a profit margin of {profit_margin}. "
                f"Analyst recommendation is currently '{recommendation}'."
            )

            financial_data.append(
                {
                    "Ticker": ticker,
                    "Name": name,
                    "Financial_Text": fin_text,
                    "Latest_Status": "Active",
                }
            )
        except Exception:
            financial_data.append(
                {
                    "Ticker": ticker,
                    "Name": name,
                    "Financial_Text": f"{name} ({ticker}) market data is currently unavailable.",
                    "Latest_Status": "Unknown",
                }
            )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for item in financial_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\nGenerated Financial Metrics Data: {OUTPUT_FILE}")
    time.sleep(0.1)


if __name__ == "__main__":
    fetch_financial_metrics()

