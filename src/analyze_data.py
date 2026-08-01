"""Pure filtering and aggregation helpers for the analytics API."""

from typing import Any

import pandas as pd

from src.transform_data import AGE_LABELS

CITY_CONTEXT_COLUMNS = [
    "poverty_rate",
    "median_income",
    "percent_completed_hs",
    "share_white",
    "share_black",
    "share_native_american",
    "share_asian",
    "share_hispanic",
]
TRUTHY_VALUES = {"true", "1", "1.0", "yes", "y"}


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


def _true_percentage(series: pd.Series) -> float:
    """Return the percentage of explicit truthy values in a mixed-type series."""
    if series.empty:
        return 0.0
    normalized = series.astype("string").str.strip().str.casefold()
    return float(normalized.isin(TRUTHY_VALUES).mean() * 100)


def _distinct_locations(dataframe: pd.DataFrame) -> int:
    if dataframe.empty:
        return 0
    return int(dataframe[["state", "city_clean"]].dropna().drop_duplicates().shape[0])


def get_kpi_metrics(dataframe: pd.DataFrame, full_df: pd.DataFrame | None = None) -> dict[str, Any]:
    """Calculate incident, selection, and city-context KPIs."""
    valid_dates = pd.to_datetime(dataframe["date"], errors="coerce").dropna()
    reporting_period = "N/A – N/A"
    if not valid_dates.empty:
        reporting_period = f"{valid_dates.min():%b %d, %Y} – {valid_dates.max():%b %d, %Y}"

    total = len(dataframe)
    national_total = len(full_df) if full_df is not None else total
    selection_share = (total / national_total * 100) if national_total else 0.0
    if total:
        complete_context = dataframe[CITY_CONTEXT_COLUMNS].notna().all(axis=1)
        city_context_coverage = float(complete_context.mean() * 100)
        age_imputed = (
            dataframe["age_imputed"]
            if "age_imputed" in dataframe
            else pd.Series(False, index=dataframe.index)
        )
        age_imputed_pct = _true_percentage(age_imputed)
    else:
        city_context_coverage = 0.0
        age_imputed_pct = 0.0
    return {
        "total_incidents": total,
        "national_total": national_total,
        "selection_share_pct": round(selection_share, 1),
        "states_covered": int(dataframe["state"].dropna().nunique()),
        "cities_covered": _distinct_locations(dataframe),
        "city_context_coverage_pct": round(city_context_coverage, 1),
        "age_imputed_pct": round(age_imputed_pct, 1),
        "avg_age": _mean_or_zero(dataframe["age"]),
        "mental_illness_pct": (
            round(float(dataframe["signs_of_mental_illness"].mean() * 100), 1) if total else 0.0
        ),
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
    poverty = (
        dataframe.groupby("state")["poverty_rate"]
        .mean()
        .dropna()
        .sort_values(ascending=False)
        .head(10)
    )

    return {
        "timeline": [
            {"year_month": str(key), "count": int(value)}
            for key, value in timeline_counts.items()
        ],
        "race": _counts(dataframe, "race_full"),
        "armed": _counts(dataframe, "armed", 8),
        "states": _counts(dataframe, "state", 10),
        "age_groups": ordered_ages,
        "state_poverty": {str(state): round(float(rate), 1) for state, rate in poverty.items()},
    }


def get_state_map_aggregations(dataframe: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    """Return compact hover-ready metrics for each state in the selection."""
    states: list[dict[str, Any]] = []
    for state, group in dataframe.groupby("state", sort=True):
        state_code = str(state)
        if state_code.casefold() == "unknown":
            continue
        total = len(group)
        states.append(
            {
                "state": state_code,
                "total_incidents": total,
                "avg_age": _mean_or_zero(group["age"]),
                "body_cam_pct": (
                    round(float(group["body_camera"].mean() * 100), 1) if total else 0.0
                ),
                "mental_illness_pct": (
                    round(float(group["signs_of_mental_illness"].mean() * 100), 1)
                    if total
                    else 0.0
                ),
                "avg_poverty_rate": _mean_or_zero(group["poverty_rate"]),
                "avg_median_income": _mean_or_zero(group["median_income"], 0),
            }
        )
    return {"states": states}
