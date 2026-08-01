"""FastAPI application for the police fatalities analytics dashboard."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import math
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from src.analyze_data import (
    apply_filters,
    get_chart_aggregations,
    get_kpi_metrics,
    get_state_map_aggregations,
)
from src.clean_data import clean_all_datasets
from src.load_data import load_all_raw_datasets
from src.transform_data import transform_and_merge_datasets
from src.visualize import export_static_charts


BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_FILE = PROCESSED_DIR / "cleaned_police_killings.csv"
DASHBOARD_HTML = (BASE_DIR / "templates" / "dashboard.html").read_text(encoding="utf-8")


def run_pipeline() -> pd.DataFrame:
    """Build the master dataset once during application startup."""
    raw_datasets = load_all_raw_datasets(RAW_DIR)
    cleaned_datasets = clean_all_datasets(raw_datasets)
    processed = transform_and_merge_datasets(cleaned_datasets, PROCESSED_FILE)
    export_static_charts(processed, PROCESSED_DIR)
    return processed


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.processed_df = run_pipeline()
    application.state.last_refreshed = datetime.now(timezone.utc).isoformat()
    yield


app = FastAPI(
    title="Police Fatalities & Community Context",
    description="Filtered incident and socio-economic analytics powered by FastAPI and Pandas",
    version="4.0.0",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Apply conservative browser security defaults to every response."""
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
        "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
    )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


def _dataframe() -> pd.DataFrame:
    return app.state.processed_df


def _filtered_dataframe(
    state: str | None,
    race: str | None,
    flee: str | None,
) -> pd.DataFrame:
    return apply_filters(_dataframe(), state, race, flee)


def _json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


@app.get("/api/options", response_class=JSONResponse)
def get_options() -> dict[str, Any]:
    """Return validated values for global dashboard filters."""
    processed_df = _dataframe()
    return {
        "states": sorted(
            state for state in processed_df["state"].dropna().unique() if state != "UNKNOWN"
        ),
        "races": sorted(processed_df["race_full"].dropna().unique().tolist()),
        "flee": sorted(processed_df["flee"].dropna().unique().tolist()),
        "last_refreshed": app.state.last_refreshed,
    }


@app.get("/api/stats", response_class=JSONResponse)
def get_stats(
    state: str | None = Query(None, max_length=64),
    race: str | None = Query(None, max_length=64),
    flee: str | None = Query(None, max_length=64),
) -> dict[str, Any]:
    """Return incident, selection, and socio-economic KPIs."""
    processed_df = _dataframe()
    filtered_df = apply_filters(processed_df, state, race, flee)
    return get_kpi_metrics(filtered_df, processed_df)


@app.get("/api/charts", response_class=JSONResponse)
def get_charts(
    state: str | None = Query(None, max_length=64),
    race: str | None = Query(None, max_length=64),
    flee: str | None = Query(None, max_length=64),
) -> dict[str, Any]:
    """Return aggregated datasets for all dashboard charts."""
    return get_chart_aggregations(_filtered_dataframe(state, race, flee))


@app.get("/api/map", response_class=JSONResponse)
def get_map(
    state: str | None = Query(None, max_length=64),
    race: str | None = Query(None, max_length=64),
    flee: str | None = Query(None, max_length=64),
) -> dict[str, list[dict[str, Any]]]:
    """Return hover-ready state metrics for the interactive map."""
    return get_state_map_aggregations(_filtered_dataframe(state, race, flee))


@app.get("/api/table", response_class=JSONResponse)
def get_table(
    search: str | None = Query(None, max_length=200),
    state: str | None = Query(None, max_length=64),
    race: str | None = Query(None, max_length=64),
    flee: str | None = Query(None, max_length=64),
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
) -> dict[str, Any]:
    """Return paginated incident records with city socio-economic context."""
    dataframe = _filtered_dataframe(state, race, flee)
    if search and search.strip():
        needle = search.strip()
        matches = (
            dataframe["name"].astype(str).str.contains(needle, case=False, regex=False, na=False)
            | dataframe["city"].astype(str).str.contains(
                needle, case=False, regex=False, na=False
            )
            | dataframe["armed"].astype(str).str.contains(
                needle, case=False, regex=False, na=False
            )
        )
        dataframe = dataframe.loc[matches]

    total_records = len(dataframe)
    start = (page - 1) * limit
    records = dataframe.iloc[start : start + limit].copy()
    records["date_str"] = (
        pd.to_datetime(records["date"], errors="coerce").dt.strftime("%b %d, %Y").fillna("N/A")
    )
    records["median_income_str"] = records["median_income"].apply(
        lambda value: f"${value:,.0f}" if pd.notnull(value) else "N/A"
    )
    records["poverty_rate_str"] = records["poverty_rate"].apply(
        lambda value: f"{value:.1f}%" if pd.notnull(value) else "N/A"
    )
    display_columns = [
        "id",
        "name",
        "date_str",
        "age",
        "race_full",
        "armed",
        "city",
        "state",
        "poverty_rate_str",
        "median_income_str",
    ]
    records_list = [
        {key: _json_value(value) for key, value in record.items()}
        for record in records[display_columns].to_dict(orient="records")
    ]
    total_pages = max(1, math.ceil(total_records / limit))
    return {
        "total": total_records,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
        "data": records_list,
    }


@app.get("/", response_class=HTMLResponse)
def dashboard_ui() -> HTMLResponse:
    """Serve the enterprise analytics dashboard."""
    return HTMLResponse(DASHBOARD_HTML)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
