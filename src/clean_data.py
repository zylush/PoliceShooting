"""Schema validation and normalization for raw police and city datasets."""

import re
from collections.abc import Iterable

import pandas as pd


MISSING_TOKENS = {"", "-", "(x)", "unknown", "undetermined", "nan", "none", "null"}
TRUTHY_TOKENS = {"true", "1", "t", "yes", "y"}

POLICE_COLUMNS = {
    "id", "name", "date", "manner_of_death", "armed", "age", "gender", "race",
    "city", "state", "signs_of_mental_illness", "threat_level", "flee", "body_camera",
}
CITY_COLUMNS = {
    "median_income": {"Geographic Area", "City", "Median Income"},
    "poverty_rate": {"Geographic Area", "City", "poverty_rate"},
    "high_school": {"Geographic Area", "City", "percent_completed_hs"},
    "race_by_city": {
        "City", "share_white", "share_black", "share_native_american", "share_asian", "share_hispanic",
    },
}
RACE_COLUMNS = [
    "share_white", "share_black", "share_native_american", "share_asian", "share_hispanic",
]


def _clean_city_name(series: pd.Series) -> pd.Series:
    """Create a stable city join key by removing Census-style suffixes."""
    values = series.fillna("Unknown").astype(str).str.strip()
    return (
        values.str.replace(
            r"\s+(?:city|town|cdp|village|municipality)$", "", flags=re.IGNORECASE, regex=True
        )
        .str.strip()
        .str.title()
        .replace("", "Unknown")
    )


def _require_columns(dataset_name: str, dataframe: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required).difference(dataframe.columns))
    if missing:
        raise ValueError(f"{dataset_name} is missing required columns: {', '.join(missing)}")


def _normalise_text(series: pd.Series, default: str = "Unknown") -> pd.Series:
    values = series.fillna("").astype(str).str.strip()
    missing = values.str.lower().isin(MISSING_TOKENS)
    return values.mask(missing, default)


def _clean_numeric(series: pd.Series) -> pd.Series:
    values = series.astype("string").str.strip()
    values = values.mask(values.str.lower().isin(MISSING_TOKENS))
    values = values.str.replace(r"[^\d.\-]", "", regex=True)
    return pd.to_numeric(values, errors="coerce")


def _prepare_city_keys(dataframe: pd.DataFrame, state_column: str = "Geographic Area") -> pd.DataFrame:
    result = dataframe.copy()
    result["state"] = _normalise_text(result[state_column]).str.upper()
    result["city_clean"] = _clean_city_name(result["City"])
    return result


def clean_all_datasets(datasets: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Return validated, type-safe copies of the five raw dataframes.

    Dates are intentionally parsed only as ``%d/%m/%y``.  Invalid source dates are
    retained as ``NaT`` so downstream metrics can exclude them without ambiguity.
    """
    required_datasets = {"police_killings", *CITY_COLUMNS}
    absent = sorted(required_datasets.difference(datasets))
    if absent:
        raise ValueError(f"Missing required datasets: {', '.join(absent)}")

    police = datasets["police_killings"].copy()
    _require_columns("police_killings", police, POLICE_COLUMNS)
    for column, default in {
        "name": "Unknown", "race": "Unknown", "gender": "Unknown", "armed": "undetermined",
        "flee": "Unknown", "threat_level": "undetermined", "manner_of_death": "Unknown",
        "city": "Unknown", "state": "Unknown",
    }.items():
        police[column] = _normalise_text(police[column], default)
    police["state"] = police["state"].str.upper()
    police["city_clean"] = _clean_city_name(police["city"])
    police["age"] = _clean_numeric(police["age"])
    police["date"] = pd.to_datetime(police["date"], format="%d/%m/%y", errors="coerce")
    for column in ("signs_of_mental_illness", "body_camera"):
        police[column] = (
            police[column].fillna("").astype(str).str.strip().str.lower().isin(TRUTHY_TOKENS)
        )

    income = datasets["median_income"].copy()
    _require_columns("median_income", income, CITY_COLUMNS["median_income"])
    income = _prepare_city_keys(income)
    income["median_income"] = _clean_numeric(income["Median Income"])

    poverty = datasets["poverty_rate"].copy()
    _require_columns("poverty_rate", poverty, CITY_COLUMNS["poverty_rate"])
    poverty = _prepare_city_keys(poverty)
    poverty["poverty_rate"] = _clean_numeric(poverty["poverty_rate"])

    high_school = datasets["high_school"].copy()
    _require_columns("high_school", high_school, CITY_COLUMNS["high_school"])
    high_school = _prepare_city_keys(high_school)
    high_school["percent_completed_hs"] = _clean_numeric(high_school["percent_completed_hs"])

    race_by_city = datasets["race_by_city"].copy()
    _require_columns("race_by_city", race_by_city, CITY_COLUMNS["race_by_city"])
    race_state_column = "Geographic Area" if "Geographic Area" in race_by_city else "Geographic area"
    if race_state_column not in race_by_city:
        raise ValueError("race_by_city is missing required column: Geographic Area")
    race_by_city = _prepare_city_keys(race_by_city, race_state_column)
    for column in RACE_COLUMNS:
        race_by_city[column] = _clean_numeric(race_by_city[column])

    return {
        "police_killings": police,
        "median_income": income[["state", "city_clean", "median_income"]],
        "poverty_rate": poverty[["state", "city_clean", "poverty_rate"]],
        "high_school": high_school[["state", "city_clean", "percent_completed_hs"]],
        "race_by_city": race_by_city[["state", "city_clean", *RACE_COLUMNS]],
    }
