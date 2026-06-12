def test_industry_classify_endpoint_returns_gics_labels(client):
    response = client.post(
        "/api/industry/classify",
        json={
            "title": "Nvidia announces new GPU for AI workloads",
            "text": "The semiconductor company said demand for chips remains strong.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sector"] == "Information Technology"
    assert data["industry_group"] == "Semiconductors & Semiconductor Equipment"
    assert data["confidence"] > 0.5
    assert "gpu" in [term.lower() for term in data["matched_terms"]]


def test_industry_classify_endpoint_explains_unclassified_text(client):
    response = client.post(
        "/api/industry/classify",
        json={"title": "General market update", "text": "Investors watched broad market movement."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sector"] == "Unclassified"
    assert data["industry_group"] == "Unclassified"
    assert data["matched_terms"] == []
