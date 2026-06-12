from __future__ import annotations


def get_dashboard_summary(yf_module):
    INDEX_TARGETS = [
        ("^GSPC", "S&P 500"),
        ("^IXIC", "NASDAQ"),
        ("^DJI", "다우존스"),
        ("^VIX", "VIX 공포지수"),
        ("^TNX", "10년 국채금리"),
        ("DX-Y.NYB", "달러 인덱스"),
    ]

    indices_data = []
    for symbol, name in INDEX_TARGETS:
        try:
            ticker = yf_module.Ticker(symbol)
            price = ticker.fast_info.last_price
            prev_close = ticker.fast_info.previous_close
            change = price - prev_close
            change_percent = (change / prev_close) * 100
            indices_data.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "price": round(price, 2),
                    "change": round(change, 2),
                    "changePercent": round(change_percent, 2),
                }
            )
        except Exception:
            indices_data.append(
                {
                    "name": name,
                    "symbol": symbol,
                    "price": 0,
                    "change": 0,
                    "changePercent": 0,
                }
            )

    top_stocks = ["AAPL", "NVDA", "MSFT"]
    top_stock_data = None
    max_cap = 0

    for symbol in top_stocks:
        try:
            ticker = yf_module.Ticker(symbol)
            cap = ticker.fast_info.market_cap
            if not cap or cap <= max_cap:
                continue

            max_cap = cap
            price = ticker.fast_info.last_price
            change = price - ticker.fast_info.previous_close
            pct = (change / ticker.fast_info.previous_close) * 100

            hist = ticker.history(period="1mo")
            chart_data = []
            if not hist.empty:
                hist = hist.reset_index()
                for _, row in hist.iterrows():
                    chart_data.append(
                        {
                            "date": row["Date"].strftime("%Y-%m-%d"),
                            "price": row["Close"],
                        }
                    )

            top_stock_data = {
                "symbol": symbol,
                "name": "Market Leader",
                "price": price,
                "change": change,
                "changePercent": pct,
                "marketCap": cap,
                "chartData": chart_data[-20:],
            }
        except Exception:
            continue

    return {"indices": indices_data, "topStock": top_stock_data}
