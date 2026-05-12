from __future__ import annotations

import datetime as dt
from typing import Callable, Dict, List, Optional

import pandas as pd
import yfinance as yf
from pydantic import BaseModel


class BacktestPosition(BaseModel):
    symbol: str
    weight: Optional[float] = None


class BacktestRequest(BaseModel):
    symbol: Optional[str] = None
    strategy: str = "ma_cross"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_cash: float = 100000
    short_window: int = 5
    long_window: int = 20
    fee_rate: float = 0.0015
    positions: Optional[List[BacktestPosition]] = None


class BacktestSymbolItem(BaseModel):
    symbol: str
    name: Optional[str] = None


def resolve_symbol(raw_symbol: str, name_to_ticker: Dict[str, str]) -> Optional[str]:
    if not raw_symbol:
        return None

    symbol = raw_symbol.strip().upper()
    if symbol in name_to_ticker:
        return name_to_ticker[symbol]
    return symbol


def normalize_symbol_name(raw: str) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None

    normalized = raw.replace("from:", "").strip()
    normalized = normalized.replace("From:", "").strip()

    if " OR " in normalized:
        return normalized.split(" OR ")[0].strip()
    return normalized


def get_backtest_symbol_catalog(
    name_to_ticker: Dict[str, str],
    sp500_handles: Dict[str, str],
    normalize_fn: Callable[[str], Optional[str]] = normalize_symbol_name,
) -> List[dict]:
    catalog = {}

    for symbol in set(name_to_ticker.values()):
        if symbol and len(symbol) <= 8:
            catalog[symbol] = catalog.get(symbol, symbol)

    for symbol, query in sp500_handles.items():
        if not symbol:
            continue
        if symbol not in catalog:
            catalog[symbol] = normalize_fn(query) or symbol

    return sorted(
        [{"symbol": symbol, "name": name} for symbol, name in catalog.items()],
        key=lambda item: item["symbol"],
    )


def get_backtest_symbol_detail(symbol: str, fallback_name: Optional[str] = None) -> dict:
    normalized = (symbol or "").strip().upper()
    if not normalized:
        return {
            "symbol": "",
            "name": "",
        }

    try:
        info = (yf.Ticker(normalized).info or {})
        name = info.get("shortName") or info.get("longName") or fallback_name or normalized
        summary = info.get("longBusinessSummary")

        return {
            "symbol": normalized,
            "name": name,
            "exchange": info.get("exchange") or "",
            "country": info.get("country") or "",
            "sector": info.get("sector") or "",
            "industry": info.get("industry") or "",
            "website": info.get("website") or "",
            "market_cap": info.get("marketCap"),
            "employees": info.get("fullTimeEmployees"),
            "summary": summary if isinstance(summary, str) and summary.strip() else "",
        }
    except Exception:
        return {
            "symbol": normalized,
            "name": fallback_name or normalized,
            "exchange": "",
            "country": "",
            "sector": "",
            "industry": "",
            "website": "",
            "market_cap": None,
            "employees": None,
            "summary": "",
        }


def _default_price_loader(symbol: str, start_dt: dt.datetime, end_dt: dt.datetime):
    return yf.download(
        symbol,
        start=start_dt,
        end=end_dt,
        interval="1d",
        progress=False,
        multi_level_index=False,
    )


def load_backtest_prices(
    symbol: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    *,
    price_loader: Callable[[str, dt.datetime, dt.datetime], pd.DataFrame] = _default_price_loader,
) -> List[dict]:
    start_dt = dt.datetime.fromisoformat(start_date.strip()) if start_date else dt.datetime.now() - dt.timedelta(days=365)
    end_dt = dt.datetime.fromisoformat(end_date.strip()) if end_date else dt.datetime.now()

    df = price_loader(symbol, start_dt, end_dt)
    if df is None or df.empty:
        return []

    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]

    rows = []
    for _, row in df.iterrows():
        if pd.isna(row[date_col]):
            continue

        close = row.get("Close", 0)
        if pd.isna(close):
            continue

        rows.append({
            "date": pd.to_datetime(row[date_col]).strftime("%Y-%m-%d"),
            "close": float(close),
        })

    return rows


def normalize_backtest_positions(payload: BacktestRequest, name_to_ticker: Dict[str, str]) -> dict:
    if not payload.positions:
        symbol = resolve_symbol(payload.symbol or "", name_to_ticker)
        if not symbol:
            return {
                "success": False,
                "msg": "심볼을 입력해 주세요.",
            }
        return {
            "success": True,
            "positions": [
                {
                    "symbol": symbol,
                    "weight": 1.0,
                    "label": symbol,
                }
            ],
        }

    parsed_positions: List[dict] = []
    total_weight = 0.0
    unweighted_count = 0

    for idx, item in enumerate(payload.positions):
        symbol = resolve_symbol(item.symbol, name_to_ticker)
        if not symbol:
            return {
                "success": False,
                "msg": f"{idx + 1}번째 포트폴리오 종목의 티커를 확인해 주세요.",
            }

        if item.weight is None:
            unweighted_count += 1
            parsed_positions.append({
                "symbol": symbol,
                "weight": None,
                "label": symbol,
            })
            continue

        if item.weight < 0:
            return {
                "success": False,
                "msg": f"가중치 값은 0 이상이어야 합니다. ({symbol})",
            }

        weight = item.weight
        if weight > 1.0 and weight <= 100.0:
            weight = weight / 100.0

        if weight > 1.0:
            return {
                "success": False,
                "msg": f"가중치는 1.0 이하(또는 100 이하의 퍼센트)로 입력해 주세요. ({symbol})",
            }

        if weight == 0:
            continue

        parsed_positions.append({
            "symbol": symbol,
            "weight": weight,
            "label": symbol,
        })
        total_weight += weight

    if not parsed_positions:
        return {
            "success": False,
            "msg": "포트폴리오 종목을 1개 이상 입력해 주세요.",
        }

    if total_weight > 1.0 + 1e-12:
        return {
            "success": False,
            "msg": "가중치 합이 100%를 넘습니다.",
        }

    if unweighted_count > 0:
        remaining = 1.0 - total_weight
        assign = remaining / unweighted_count if unweighted_count > 0 else 0
        for pos in parsed_positions:
            if pos["weight"] is None:
                pos["weight"] = assign
    else:
        if total_weight > 0:
            scale = 1.0 / total_weight
            for pos in parsed_positions:
                pos["weight"] *= scale
        else:
            share = 1.0 / len(parsed_positions)
            for pos in parsed_positions:
                pos["weight"] = share

    return {
        "success": True,
        "positions": parsed_positions,
    }


def run_single_ma_cross_backtest(
    symbol: str,
    payload: BacktestRequest,
    *,
    price_loader: Callable[[str, Optional[str], Optional[str]], List[dict]] = load_backtest_prices,
) -> dict:
    if not symbol:
        return {
            "success": False,
            "msg": "심볼을 입력해 주세요.",
        }

    short_window = payload.short_window
    long_window = payload.long_window
    if short_window < 2 or long_window < short_window + 1:
        return {
            "success": False,
            "msg": "short_window는 2 이상, long_window는 short_window보다 크게 설정해야 합니다.",
        }

    if payload.fee_rate < 0:
        return {
            "success": False,
            "msg": "수수료율은 0 이상이어야 합니다.",
        }

    if payload.initial_cash <= 0:
        return {
            "success": False,
            "msg": "초기 자금은 1 이상이어야 합니다.",
        }

    price_rows = price_loader(symbol, payload.start_date, payload.end_date)
    if len(price_rows) < long_window + 2:
        return {
            "success": False,
            "msg": "선택한 기간의 데이터가 부족합니다. 기간을 더 늘려 보세요.",
        }

    closes = [row["close"] for row in price_rows]
    cash = float(payload.initial_cash)
    shares = 0
    entry_total_cost = 0.0
    open_position = False
    trade_events = []
    wins = 0
    sell_count = 0

    equity_curve = []
    peak_equity = float(payload.initial_cash)
    max_drawdown = 0.0

    for i, item in enumerate(price_rows):
        price = item["close"]
        short_ma = sum(closes[max(0, i - short_window + 1):i + 1]) / min(short_window, i + 1)
        long_ma = sum(closes[max(0, i - long_window + 1):i + 1]) / min(long_window, i + 1)
        should_buy = short_ma > long_ma
        should_sell = short_ma < long_ma

        if should_buy and not open_position and i >= long_window - 1:
            max_affordable_shares = int(cash / (price * (1 + payload.fee_rate)))
            if max_affordable_shares > 0:
                buy_amount = max_affordable_shares * price
                fee = buy_amount * payload.fee_rate
                cash -= buy_amount + fee
                shares = max_affordable_shares
                entry_total_cost = buy_amount + fee
                open_position = True
                trade_events.append(
                    {
                        "side": "buy",
                        "date": item["date"],
                        "symbol": symbol,
                        "price": round(price, 4),
                        "shares": shares,
                        "fee": round(fee, 4),
                        "cash_after": round(cash, 4),
                    }
                )

        elif should_sell and open_position:
            proceeds = shares * price
            fee = proceeds * payload.fee_rate
            cash += proceeds - fee
            net_pnl = (proceeds - fee) - entry_total_cost
            net_return = 0
            if entry_total_cost > 0:
                net_return = (net_pnl / entry_total_cost) * 100

            if net_pnl > 0:
                wins += 1

            sell_count += 1
            trade_events.append(
                {
                    "side": "sell",
                    "date": item["date"],
                    "symbol": symbol,
                    "price": round(price, 4),
                    "shares": shares,
                    "fee": round(fee, 4),
                    "pnl": round(net_pnl, 4),
                    "pnl_percent": round(net_return, 2),
                    "cash_after": round(cash, 4),
                }
            )

            shares = 0
            open_position = False
            entry_total_cost = 0.0

        equity = cash + (shares * price)
        if equity > peak_equity:
            peak_equity = equity

        current_dd = ((peak_equity - equity) / peak_equity) * 100 if peak_equity > 0 else 0.0
        if current_dd > max_drawdown:
            max_drawdown = current_dd

        equity_curve.append(
            {
                "date": item["date"],
                "equity": round(equity, 4),
                "price": round(price, 4),
                "short_ma": round(short_ma, 4),
                "long_ma": round(long_ma, 4),
            }
        )

    final_equity = cash + (shares * closes[-1])
    total_return = final_equity - payload.initial_cash
    return_pct = (total_return / payload.initial_cash) * 100 if payload.initial_cash else 0
    win_rate = (wins / sell_count) * 100 if sell_count else 0.0

    return {
        "success": True,
        "result": {
            "symbol": symbol,
            "weight": 1.0,
            "period": {
                "from": price_rows[0]["date"],
                "to": price_rows[-1]["date"],
                "samples": len(price_rows),
            },
            "metrics": {
                "trade_count": sell_count,
                "wins": wins,
                "win_rate": round(win_rate, 2),
                "final_equity": round(final_equity, 4),
                "total_return": round(total_return, 4),
                "total_return_percent": round(return_pct, 2),
                "max_drawdown_percent": round(max_drawdown, 2),
                "remaining_shares": shares,
                "allocated_cash": round(payload.initial_cash, 4),
            },
            "trades": trade_events,
            "equity_curve": equity_curve,
        },
    }


def run_ma_cross_backtest(
    payload: BacktestRequest,
    *,
    normalize_positions_fn: Callable[[BacktestRequest], dict] = None,
    run_single_fn: Callable[[str, BacktestRequest], dict] = None,
    name_to_ticker: Optional[Dict[str, str]] = None,
) -> dict:
    if payload.initial_cash <= 0:
        return {
            "success": False,
            "msg": "초기 자금은 1 이상이어야 합니다.",
        }

    short_window = payload.short_window
    long_window = payload.long_window
    if short_window < 2 or long_window < short_window + 1:
        return {
            "success": False,
            "msg": "short_window는 2 이상, long_window는 short_window보다 크게 설정해야 합니다.",
        }

    if payload.fee_rate < 0:
        return {
            "success": False,
            "msg": "수수료율은 0 이상이어야 합니다.",
        }

    if normalize_positions_fn is None:
        normalize_positions_fn = lambda req: normalize_backtest_positions(req, name_to_ticker or {})
    if run_single_fn is None:
        run_single_fn = run_single_ma_cross_backtest

    normalized = normalize_positions_fn(payload)
    if not normalized["success"]:
        return normalized

    positions = normalized["positions"]

    all_results = []
    for pos in positions:
        allocation_cash = payload.initial_cash * pos["weight"]
        single_request = BacktestRequest(
            symbol=pos["symbol"],
            strategy=payload.strategy,
            start_date=payload.start_date,
            end_date=payload.end_date,
            initial_cash=allocation_cash,
            short_window=payload.short_window,
            long_window=payload.long_window,
            fee_rate=payload.fee_rate,
            positions=None,
        )

        response = run_single_fn(pos["symbol"], single_request)
        if not response["success"]:
            return response

        all_results.append(response["result"])

    if len(all_results) == 1:
        base = all_results[0]
        base["composition"] = [
            {
                "symbol": positions[0]["symbol"],
                "weight": positions[0]["weight"],
                "allocated_cash": payload.initial_cash * positions[0]["weight"],
            }
        ]
        return {
            "success": True,
            "symbol": positions[0]["symbol"],
            "strategy": payload.strategy,
            "period": base["period"],
            "params": base.get("params", {}),
            "composition": base["composition"],
            "metrics": base["metrics"],
            "trades": base["trades"],
            "equity_curve": base["equity_curve"],
        }

    total_curve = {}
    for result in all_results:
        for point in result["equity_curve"]:
            date = point["date"]
            total_curve[date] = total_curve.get(date, 0.0) + point["equity"]

    sorted_dates = sorted(total_curve.keys())
    if not sorted_dates:
        return {
            "success": False,
            "msg": "집계할 수 있는 포트폴리오 데이터가 없습니다.",
        }

    equity_curve = []
    peak_equity = payload.initial_cash
    max_drawdown = 0.0
    for date in sorted_dates:
        equity = round(total_curve[date], 4)
        if equity > peak_equity:
            peak_equity = equity
        drawdown = ((peak_equity - equity) / peak_equity) * 100 if peak_equity > 0 else 0.0
        if drawdown > max_drawdown:
            max_drawdown = drawdown
        equity_curve.append({
            "date": date,
            "equity": equity,
        })

    merged_trades = []
    for result in all_results:
        merged_trades.extend(result["trades"])
    merged_trades.sort(key=lambda item: item["date"])

    total_trade_count = sum(r["metrics"]["trade_count"] for r in all_results)
    total_wins = sum(r["metrics"]["wins"] for r in all_results)
    total_remaining_shares = sum(r["metrics"]["remaining_shares"] for r in all_results)

    composition = []
    for pos in positions:
        composition.append(
            {
                "symbol": pos["symbol"],
                "weight": round(pos["weight"], 6),
                "allocated_cash": payload.initial_cash * pos["weight"],
            }
        )

    position_metrics = []
    for pos, result in zip(positions, all_results):
        metric = result["metrics"]
        position_metrics.append(
            {
                "symbol": result["symbol"],
                "weight": round(pos["weight"], 6),
                "allocated_cash": metric["allocated_cash"],
                "final_equity": metric["final_equity"],
                "total_return": metric["total_return"],
                "trade_count": metric["trade_count"],
                "wins": metric["wins"],
                "win_rate": metric["win_rate"],
                "remaining_shares": metric["remaining_shares"],
            }
        )

    final_equity = equity_curve[-1]["equity"]
    total_return = final_equity - payload.initial_cash
    total_return_percent = (total_return / payload.initial_cash) * 100 if payload.initial_cash else 0

    return {
        "success": True,
        "strategy": payload.strategy,
        "symbol": " + ".join(p["symbol"] for p in positions),
        "period": {
            "from": sorted_dates[0],
            "to": sorted_dates[-1],
            "samples": len(sorted_dates),
        },
        "params": {
            "initial_cash": payload.initial_cash,
            "short_window": payload.short_window,
            "long_window": payload.long_window,
            "fee_rate": payload.fee_rate,
        },
        "composition": composition,
        "metrics": {
            "trade_count": total_trade_count,
            "wins": total_wins,
            "win_rate": round((total_wins / total_trade_count) * 100, 2) if total_trade_count else 0.0,
            "final_equity": round(final_equity, 4),
            "total_return": round(total_return, 4),
            "total_return_percent": round(total_return_percent, 2),
            "max_drawdown_percent": round(max_drawdown, 2),
            "remaining_shares": total_remaining_shares,
        },
        "position_results": position_metrics,
        "trades": merged_trades,
        "equity_curve": equity_curve,
    }
