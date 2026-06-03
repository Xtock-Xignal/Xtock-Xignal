from fastapi.testclient import TestClient

import main
import app.api.news as news_api


def test_translate_endpoint_uses_translation_module(monkeypatch):
    class FakeTranslator:
        def __init__(self, source, target):
            assert source == "en"
            assert target == "ko"

        def translate(self, text):
            return f"translated: {text}"

    monkeypatch.setattr(news_api, "GoogleTranslator", FakeTranslator)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/news/translate",
            json={
                "text": "The market moved higher today.",
                "url": None,
            },
        )

    assert response.status_code == 200
    assert response.json()["translated_text"] == "translated: The market moved higher today."


def test_live_news_endpoint_is_registered_and_returns_cached_news(monkeypatch):
    class FakeCursor:
        def __init__(self, docs):
            self.docs = docs

        def sort(self, *args, **kwargs):
            return self

        def limit(self, *args, **kwargs):
            return self

        def __iter__(self):
            return iter(self.docs)

    class FakeCollection:
        def __init__(self, docs):
            self.docs = docs

        def find(self, *args, **kwargs):
            return FakeCursor(self.docs)

    cached_article = {
        "source": "Test",
        "link": "https://example.com/news",
        "date": "2026-05-28T00:00:00",
        "timestamp": 1780000000,
        "title": "Cached market article",
        "original": "A cached article body.",
    }

    monkeypatch.setattr(news_api, "news_cache_col", None)
    monkeypatch.setattr(news_api, "news_sp500_col", FakeCollection([cached_article]))
    monkeypatch.setattr(news_api, "news_general_col", FakeCollection([]))

    with TestClient(main.app) as client:
        response = client.get("/api/news/live")

    assert response.status_code == 200
    data = response.json()
    assert data["has_new"] is False
    assert data["news"][0]["title"] == cached_article["title"]
    assert "industry_classification" in data["news"][0]


def test_news_symbol_parser_accepts_custom_tickers():
    assert news_api.parse_symbol_list("aapl, nvda, bad symbol, BRK.B") == [
        "AAPL",
        "NVDA",
        "BRK.B",
    ]


def test_context_question_returns_key_message_without_gemini_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/news/context-question",
            json={
                "selected_text": "earnings guidance",
                "article_title": "Market update",
                "article_text": "A company raised earnings guidance.",
            },
        )

    assert response.status_code == 200
    assert "AI API 키가 설정되어 있지 않아" in response.json()["answer"]
