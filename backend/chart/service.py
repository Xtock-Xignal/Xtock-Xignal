from typing import List, Optional
import pandas as pd
import yfinance as yf


def get_chart_history_data(
    symbol: str,
    period: str = "1d",
    interval: str = "1m",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    ticker = yf.Ticker(symbol.upper())
    history_kwargs = {"interval": interval}
    if start_date or end_date:
        if start_date:
            history_kwargs["start"] = start_date
        if end_date:
            history_kwargs["end"] = end_date
    else:
        history_kwargs["period"] = period

    hist = ticker.history(**history_kwargs)

    points: List[dict] = []
    rows: List[dict] = []
    if not hist.empty:
        for idx, row in hist.iterrows():
            close_val = row.get("Close")
            if close_val is None or pd.isna(close_val):
                continue

            py_dt = idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx

            if hasattr(py_dt, "isoformat"):
                time_iso = py_dt.isoformat()
            else:
                time_iso = str(py_dt)

            points.append({
                "time": time_iso,
                "price": float(close_val),
            })
            open_val = row.get("Open", close_val)
            high_val = row.get("High", close_val)
            low_val = row.get("Low", close_val)
            rows.append({
                "date": time_iso[:10],
                "open": float(open_val) if not pd.isna(open_val) else float(close_val),
                "high": float(high_val) if not pd.isna(high_val) else float(close_val),
                "low": float(low_val) if not pd.isna(low_val) else float(close_val),
                "close": float(close_val),
                "volume": int(row.get("Volume", 0) or 0),
            })

    return {
        "symbol": symbol.upper(),
        "period": period,
        "interval": interval,
        "points": points,
        "rows": rows,
    }
