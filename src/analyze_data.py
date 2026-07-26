"""Pure filtering and aggregation helpers for the analytics API."""

from typing import Any

import pandas as pd

from src.transform_data import AGE_LABELS


def _has_value(value: str | None) -> bool:
    return value is not None and bool(value.strip())


def apply_filters(
    dataframe: pd.DataFrame,
    state: str | None = None,
    race: str | None = None,
    flee: str | None = None,
) -> pd.DataFrame:
    """Apply case-insensitive dashboard filters without modifying the input frame."""
    result = dataframe
    if _has_value(state):
        result = result.loc[result["state"].astype(str).str.casefold() == state.strip().casefold()]
    if _has_value(race):
        needle = race.strip().casefold()
        raw_race = result["race"].astype(str).str.casefold() == needle
        display_race = result["race_full"].astype(str).str.casefold() == needle
        result = result.loc[raw_race | display_race]
    if _has_value(flee):
        result = result.loc[result["flee"].astype(str).str.casefold() == flee.strip().casefold()]
    return result.copy()


def _mean_or_zero(series: pd.Series, digits: int = 1) -> float:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return round(float(numeric.mean()), digits) if not numeric.empty else 0.0


def get_kpi_metrics(dataframe: pd.DataFrame, full_df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Calculate incident and city-context KPIs for the current selection."""
    valid_dates = pd.to_datetime(dataframe["date"], errors="coerce").dropna()
    reporting_period = "N/A – N/A"
    if not valid_dates.empty:
        reporting_period = f"{valid_dates.min():%b %d, %Y} – {valid_dates.max():%b %d, %Y}"

    total = len(dataframe)
    return {
        "total_incidents": total,
        "avg_age": _mean_or_zero(dataframe["age"]),
        "mental_illness_pct": round(float(dataframe["signs_of_mental_illness"].mean() * 100), 1) if total else 0.0,
        "body_cam_pct": round(float(dataframe["body_camera"].mean() * 100), 1) if total else 0.0,
        "avg_poverty_rate": _mean_or_zero(dataframe["poverty_rate"]),
        "avg_median_income": _mean_or_zero(dataframe["median_income"], 0),
        "avg_hs_completion": _mean_or_zero(dataframe["percent_completed_hs"]),
        "reporting_period": reporting_period,
    }


def _counts(dataframe: pd.DataFrame, column: str, limit: int | None = None) -> dict[str, int]:
    counts = dataframe[column].fillna("Unknown").astype(str).value_counts()
    if limit:
        counts = counts.head(limit)
    return {str(label): int(count) for label, count in counts.items()}


def get_chart_aggregations(dataframe: pd.DataFrame) -> dict[str, Any]:
    """Prepare JSON-ready chart data for the current dashboard selection."""
    timeline_frame = dataframe.loc[dataframe["year_month"] != "Unknown"]
    timeline_counts = timeline_frame.groupby("year_month").size().sort_index()
    age_counts = _counts(dataframe, "age_group")
    ordered_ages = {label: age_counts[label] for label in AGE_LABELS if label in age_counts}
    if "Unknown" in age_counts:
        ordered_ages["Unknown"] = age_counts["Unknown"]
    poverty = dataframe.groupby("state")["poverty_rate"].mean().dropna().sort_values(ascending=False).head(10)

    return {
        "timeline": [{"year_month": str(key), "count": int(value)} for key, value in timeline_counts.items()],
        "race": _counts(dataframe, "race_full"),
        "armed": _counts(dataframe, "armed", 8),
        "states": _counts(dataframe, "state", 10),
        "age_groups": ordered_ages,
        "state_poverty": {str(state): round(float(rate), 1) for state, rate in poverty.items()},
    }
