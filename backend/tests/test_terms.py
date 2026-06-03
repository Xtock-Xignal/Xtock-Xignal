class FakeTermsCollection:
    def __init__(self):
        self.docs = [
            {
                "en_term": "FOMC",
                "ko_term": "연방공개시장위원회",
                "definition": "미국 기준금리 방향을 논의하는 회의입니다.",
                "aliases": ["Federal Open Market Committee"],
            }
        ]
        self.update_calls = []

    def count_documents(self, query):
        return len(self.docs)

    def find(self, query, projection=None):
        return list(self.docs)

    def find_one(self, query, projection=None):
        needle = query["$or"][0]["en_term"]["$regex"].strip("^$")
        needle = needle.replace("\\ ", " ")
        for doc in self.docs:
            values = [doc.get("en_term", ""), doc.get("ko_term", ""), *(doc.get("aliases") or [])]
            if any(value.lower() == needle.lower() for value in values):
                return doc
        return None

    def update_one(self, *args, **kwargs):
        self.update_calls.append((args, kwargs))


def test_terms_search_returns_db_definition(client, monkeypatch):
    from app.api import terms

    fake_collection = FakeTermsCollection()
    monkeypatch.setattr(terms, "collection", fake_collection)

    response = client.get("/api/terms/search", params={"keyword": "FOMC"})

    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["en_term"] == "FOMC"
    assert data["definition"] == "미국 기준금리 방향을 논의하는 회의입니다."
    assert data["source"] == "DB"


def test_terms_scan_matches_known_terms(client, monkeypatch):
    from app.api import terms

    monkeypatch.setattr(terms, "collection", FakeTermsCollection())

    response = client.post(
        "/api/terms/scan",
        json={"text": "Investors are waiting for the FOMC decision."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["matched_terms"][0]["en_term"] == "FOMC"
