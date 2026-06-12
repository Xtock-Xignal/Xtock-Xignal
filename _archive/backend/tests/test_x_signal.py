import pandas as pd


def _price_frame():
    index = pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-06"])
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 104.0],
            "High": [102.0, 105.0, 108.0],
            "Low": [99.0, 100.0, 103.0],
            "Close": [101.0, 104.0, 107.0],
            "Volume": [1000, 1500, 2000],
        },
        index=index,
    )


def test_match_company_returns_frontend_ready_analysis(client, monkeypatch):
    import main

    def fake_download(*args, **kwargs):
        return _price_frame()

    monkeypatch.setattr(main.yf, "download", fake_download)

    response = client.post("/api/match-company", json={"text": "Apple"})

    assert response.status_code == 200
    data = response.json()
    first = data["matches"][0]
    assert first["symbol"] == "AAPL"
    assert first["tweet"]["author"] == "XTock Xignal"
    assert first["stockData"][0]["price"] == 101.0
    assert first["postIndex"] >= 0


def test_tweet_impact_calculates_next_return(client, monkeypatch):
    import main

    monkeypatch.setattr(main.yf, "download", lambda *args, **kwargs: _price_frame())

    response = client.post(
        "/api/tweet-impact",
        json={
            "symbol": "AAPL",
            "tweet_created_at": "2026-01-02T12:00:00.000Z",
            "tweet_id": "tweet-1",
            "tweet_text": "Apple growth looks good",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "AAPL"
    assert data["base_date"] == "2026-01-02"
    assert data["next_date"] == "2026-01-03"
    assert round(data["next_day_return"], 2) == 2.97
