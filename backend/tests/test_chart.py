import pandas as pd

import chart.router as chart_router
import chart.service as chart_service
from chart.websocket_manager import SymbolHub


def test_chart_history_endpoint_returns_rows_and_points(client, monkeypatch):
    index = pd.to_datetime(["2026-01-02", "2026-01-03"])
    frame = pd.DataFrame(
        {
            "Open": [99.0, 101.0],
            "High": [101.0, 103.0],
            "Low": [98.5, 100.5],
            "Close": [100.5, 102.25],
            "Volume": [1000, 1500],
        },
        index=index,
    )

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, period, interval):
            assert self.symbol == "AAPL"
            assert period == "1mo"
            assert interval == "1d"
            return frame

    monkeypatch.setattr(chart_service.yf, "Ticker", FakeTicker)

    response = client.get("/api/chart/history/aapl?period=1mo&interval=1d")

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["period"] == "1mo"
    assert data["interval"] == "1d"
    assert data["points"][0]["price"] == 100.5
    assert data["rows"][1] == {
        "date": "2026-01-03",
        "open": 101.0,
        "high": 103.0,
        "low": 100.5,
        "close": 102.25,
        "volume": 1500,
    }


def test_chart_history_endpoint_accepts_date_range(client, monkeypatch):
    frame = pd.DataFrame(
        {
            "Open": [99.0],
            "High": [101.0],
            "Low": [98.5],
            "Close": [100.5],
            "Volume": [1000],
        },
        index=pd.to_datetime(["2026-01-02"]),
    )

    class FakeTicker:
        def __init__(self, symbol):
            self.symbol = symbol

        def history(self, start, end, interval):
            assert self.symbol == "TSLA"
            assert start == "2026-01-01"
            assert end == "2026-01-31"
            assert interval == "1d"
            return frame

    monkeypatch.setattr(chart_service.yf, "Ticker", FakeTicker)

    response = client.get(
        "/api/chart/history/tsla?start_date=2026-01-01&end_date=2026-01-31&interval=1d"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "TSLA"
    assert data["rows"][0]["open"] == 99.0


def test_chart_websocket_endpoint_streams_hub_payload(client, monkeypatch):
    class FakeHub:
        def __init__(self):
            self.disconnected = False

        async def connect(self, websocket):
            await websocket.accept()
            await websocket.send_json({
                "type": "tick",
                "symbol": "TSLA",
                "price": 110.0,
                "time": "2026-05-25T15:30:00Z",
            })

        def disconnect(self, websocket):
            self.disconnected = True

    fake_hub = FakeHub()
    monkeypatch.setattr(chart_router, "get_hub", lambda symbol: fake_hub)

    with client.websocket_connect("/api/chart/ws/TSLA") as websocket:
        assert websocket.receive_json() == {
            "type": "tick",
            "symbol": "TSLA",
            "price": 110.0,
            "time": "2026-05-25T15:30:00Z",
        }


def test_chart_websocket_hub_builds_history_compatible_tick_row():
    hub = SymbolHub("tsla")

    row = hub.to_chart_row(110.0, "2026-05-25T15:30:00Z")

    assert row == {
        "date": "2026-05-25",
        "time": "2026-05-25T15:30:00Z",
        "open": 110.0,
        "high": 110.0,
        "low": 110.0,
        "close": 110.0,
        "volume": 0,
    }


def test_chart_websocket_hub_normalizes_numeric_string_timestamps():
    hub = SymbolHub("tsla")

    parsed = hub.parse_message({"price": 110.0, "time": "1780402337"})
    row = hub.to_chart_row(parsed["price"], parsed["time"])

    assert parsed["time"].startswith("2026-06-02T12:12:17")
    assert row["date"] == "2026-06-02"
    assert row["time"].startswith("2026-06-02T12:12:17")
