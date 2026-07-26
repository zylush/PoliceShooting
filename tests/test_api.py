from fastapi.testclient import TestClient

from main import app


def test_dashboard_api_exposes_filtered_json_safe_data() -> None:
    with TestClient(app) as client:
        options = client.get("/api/options")
        assert options.status_code == 200
        payload = options.json()
        assert payload["states"]
        assert payload["races"]
        assert payload["flee"]

        stats = client.get("/api/stats", params={"state": "WA"})
        charts = client.get("/api/charts", params={"race": "Asian"})
        table = client.get(
            "/api/table",
            params={"flee": "Not fleeing", "search": "Tim Elliot", "page": 1, "limit": 8},
        )

        assert stats.status_code == charts.status_code == table.status_code == 200
        assert stats.json()["total_incidents"] > 0
        assert "timeline" in charts.json()
        assert table.json()["total"] > 0
        assert all("tim elliot" in row["name"].lower() for row in table.json()["data"])


def test_dashboard_page_and_pagination_validation() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        invalid_page = client.get("/api/table", params={"page": 0})

    assert page.status_code == 200
    assert "Executive Dashboard" in page.text
    assert "option.textContent = value" in page.text
    assert invalid_page.status_code == 422
