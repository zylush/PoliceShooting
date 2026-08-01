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
        script = client.get("/static/dashboard.js")

    assert page.status_code == 200
    assert "Executive Dashboard" in page.text
    assert "option.textContent = value" in script.text
    assert invalid_page.status_code == 422


def test_state_map_api_returns_hover_stats_and_accepts_filters() -> None:
    """The map data contract exposes one aggregate record per US state."""
    with TestClient(app) as client:
        all_states_response = client.get("/api/map")
        filtered_response = client.get("/api/map", params={"race": "Asian"})

    assert all_states_response.status_code == 200
    assert filtered_response.status_code == 200

    all_states = all_states_response.json()["states"]
    filtered_states = filtered_response.json()["states"]
    assert len(all_states) >= 40
    assert all_states

    required_stats = {"state", "total_incidents", "avg_age"}
    assert required_stats.issubset(all_states[0])
    assert all(row["state"] for row in all_states)
    assert all(row["total_incidents"] >= 0 for row in all_states)
    assert sum(row["total_incidents"] for row in filtered_states) <= sum(
        row["total_incidents"] for row in all_states
    )


def test_dashboard_page_contains_interactive_state_map_hooks() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/dashboard.js")

    assert page.status_code == 200
    assert 'id="stateMap"' in page.text
    assert "/api/map" in script.text
    assert "renderMap" in script.text


def test_dashboard_page_exposes_enterprise_accessibility_and_status_hooks() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/dashboard.js")

    assert page.status_code == 200
    assert '<main id="mainContent"' in page.text
    assert 'aria-label="Global filters"' in page.text
    assert 'for="stateFilter"' in page.text
    assert 'for="raceFilter"' in page.text
    assert 'for="fleeFilter"' in page.text
    assert 'for="tableSearch"' in page.text
    assert 'id="dashboardStatus"' in page.text
    assert 'id="dashboardError"' in page.text
    assert 'id="activeFilters"' in page.text
    assert 'id="tableEmptyState"' in page.text
    assert 'id="dataContextCoverage"' in page.text
    assert 'id="dataAgeImputed"' in page.text
    assert "opt.last_refreshed" in script.text


def test_stats_api_exposes_selection_context() -> None:
    with TestClient(app) as client:
        stats = client.get("/api/stats", params={"state": "WA"})

    assert stats.status_code == 200
    payload = stats.json()
    assert 0 < payload["selection_share_pct"] <= 100
    assert payload["national_total"] >= payload["total_incidents"]
    assert payload["states_covered"] == 1
    assert payload["cities_covered"] > 0
    assert 0 <= payload["city_context_coverage_pct"] <= 100
    assert 0 <= payload["age_imputed_pct"] <= 100


def test_dashboard_serves_local_assets_with_security_headers() -> None:
    with TestClient(app) as client:
        page = client.get("/")
        script = client.get("/static/dashboard.js")
        stylesheet = client.get("/static/dashboard.css")

    assert page.status_code == script.status_code == stylesheet.status_code == 200
    assert "cdn.jsdelivr.net" not in page.text
    assert 'src="/static/vendor/chart.umd.min.js"' in page.text
    assert 'src="/static/dashboard.js"' in page.text
    assert 'href="/static/dashboard.css"' in page.text
    assert page.headers["x-content-type-options"] == "nosniff"
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert "style-src 'self';" in page.headers["content-security-policy"]
    assert "'unsafe-inline'" not in page.headers["content-security-policy"]
    assert page.headers["referrer-policy"] == "no-referrer"


def test_chart_canvases_reference_accessible_data_descriptions() -> None:
    with TestClient(app) as client:
        page = client.get("/")

    for chart_name in ("timeline", "race", "states", "age", "armed", "poverty"):
        assert f'aria-describedby="{chart_name}Data"' in page.text
        assert f'id="{chart_name}Data"' in page.text


def test_stats_api_zeroes_quality_metrics_for_empty_selection() -> None:
    with TestClient(app) as client:
        stats = client.get("/api/stats", params={"state": "ZZ"})

    assert stats.status_code == 200
    payload = stats.json()
    assert payload["total_incidents"] == 0
    assert payload["city_context_coverage_pct"] == 0.0
    assert payload["age_imputed_pct"] == 0.0
    assert payload["reporting_period"] == "N/A – N/A"
