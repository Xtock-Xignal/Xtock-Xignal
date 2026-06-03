from __future__ import annotations


def get_dashboard_summary(yf_module):
    indices_data = []
    for symbol, name in [("^GSPC", "S&P 500"), ("^VIX", "VIX (공포지수)")]:
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
                    "price": price,
                    "change": change,
                    "changePercent": change_percent,
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
