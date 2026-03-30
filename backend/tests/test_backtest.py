from typing import List, Dict, Any

import pytest

import main


def test_normalize_backtest_positions_single_symbol_alias():
    payload = main.BacktestRequest(symbol="tesla", short_window=5, long_window=20)
    result = main._normalize_backtest_positions(payload)

    assert result["success"] is True
    assert result["positions"] == [
        {
            "symbol": "TSLA",
            "weight": 1.0,
            "label": "TSLA",
        }
    ]


def test_normalize_backtest_positions_auto_weights_and_percent_scale():
    payload = main.BacktestRequest(
        short_window=5,
        long_window=20,
        positions=[
            main.BacktestPosition(symbol="AAPL", weight=None),
            main.BacktestPosition(symbol="MSFT", weight=0.25),
            main.BacktestPosition(symbol="TSLA", weight=25),
        ],
    )

    result = main._normalize_backtest_positions(payload)

    assert result["success"] is True
    positions = result["positions"]
    assert positions[0]["symbol"] == "AAPL"
    assert positions[0]["weight"] == pytest.approx(0.5)
    assert positions[1]["weight"] == pytest.approx(0.25)
    assert positions[2]["weight"] == pytest.approx(0.25)


def test_normalize_backtest_positions_rejects_excessive_weight_sum():
    payload = main.BacktestRequest(
        short_window=5,
        long_window=20,
        positions=[
            main.BacktestPosition(symbol="AAPL", weight=0.6),
            main.BacktestPosition(symbol="MSFT", weight=0.6),
        ],
    )

    result = main._normalize_backtest_positions(payload)

    assert result["success"] is False
    assert result["msg"] == "가중치 합이 100%를 넘습니다."


def test_symbols_catalog_endpoint_returns_symbols_with_names(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "_get_backtest_symbol_catalog",
        lambda: [
            {"symbol": "AAPL", "name": "Apple"},
            {"symbol": "MSFT", "name": "Microsoft"},
            {"symbol": "TSLA", "name": "Tesla"},
        ],
    )

    response = client.get("/api/backtest/symbols?query=AAPL&limit=10")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["items"], list)
    assert data["items"][0]["symbol"] == "AAPL"
    assert data["items"][0]["name"] == "Apple"


def _build_price_rows() -> List[Dict[str, Any]]:
    return [
        {"date": f"2025-01-0{i + 1}", "close": round(10 + i * 0.5, 2)}
        for i in range(8)
    ]


def test_backtest_run_uses_prepared_prices(monkeypatch, client):
    monkeypatch.setattr(main, "_load_backtest_prices", lambda *_args, **_kwargs: _build_price_rows())

    response = client.post(
        "/api/backtest/run",
        json={
            "symbol": "AAPL",
            "initial_cash": 10000,
            "short_window": 2,
            "long_window": 3,
            "fee_rate": 0.0,
            "strategy": "ma_cross",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["symbol"] == "AAPL"
    assert "metrics" in data
    assert "composition" in data
    assert data["composition"][0]["symbol"] == "AAPL"


def test_backtest_symbol_info_returns_detail(monkeypatch, client):
    monkeypatch.setattr(
        main,
        "_get_backtest_symbol_detail",
        lambda symbol: {
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NMS",
            "country": "USA",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "summary": "Demo summary for Apple",
            "website": "https://www.apple.com",
            "market_cap": 3_000_000_000_000,
            "employees": 161_000,
        },
    )

    response = client.get("/api/backtest/symbol-info?symbol=AAPL")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["item"]["symbol"] == "AAPL"
    assert data["item"]["name"] == "Apple Inc."


def test_backtest_symbol_info_returns_failure_when_unknown(monkeypatch, client):
    monkeypatch.setattr(main, "_get_backtest_symbol_detail", lambda symbol: None)

    response = client.get("/api/backtest/symbol-info?symbol=NOPE")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["msg"] == "티커를 확인할 수 없습니다."
