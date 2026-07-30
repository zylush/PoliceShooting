"""Feature engineering and safe city-level joins."""

from pathlib import Path

import pandas as pd


RACE_NAMES = {
    "W": "White", "B": "Black", "H": "Hispanic", "A": "Asian",
    "N": "Native American", "O": "Other", "Unknown": "Unknown",
}
AGE_LABELS = ["<18", "18-29", "30-44", "45-59", "60+"]


def _aggregate_city_metrics(dataframe: pd.DataFrame) -> pd.DataFrame:
    return dataframe.groupby(["state", "city_clean"], as_index=False).mean(numeric_only=True)


def _impute_ages_by_state(incidents: pd.DataFrame) -> pd.DataFrame:
    """Fill missing ages from the state median, then the overall median."""
    result = incidents.copy()
    ages = pd.to_numeric(result["age"], errors="coerce")
    state_medians = ages.groupby(result["state"]).transform("median")
    result["age"] = ages.fillna(state_medians).fillna(ages.median())
    return result


def transform_and_merge_datasets(
    cleaned_datasets: dict[str, pd.DataFrame], output_path: Path
) -> pd.DataFrame:
    """Engineer incident features, left-join city metrics, and export the master CSV."""
    incidents = _impute_ages_by_state(cleaned_datasets["police_killings"])
    incidents["year"] = incidents["date"].dt.year.astype("Int64")
    incidents["month"] = incidents["date"].dt.month.astype("Int64")
    incidents["year_month"] = incidents["date"].dt.strftime("%Y-%m").fillna("Unknown")
    incidents["race_full"] = incidents["race"].map(RACE_NAMES).fillna("Unknown")
    age_groups = pd.cut(
        incidents["age"], bins=[float("-inf"), 18, 30, 45, 60, float("inf")],
        labels=AGE_LABELS, right=False,
    )
    incidents["age_group"] = age_groups.astype("string").fillna("Unknown")

    row_count = len(incidents)
    metrics = (
        _aggregate_city_metrics(cleaned_datasets["median_income"]),
        _aggregate_city_metrics(cleaned_datasets["poverty_rate"]),
        _aggregate_city_metrics(cleaned_datasets["high_school"]),
        _aggregate_city_metrics(cleaned_datasets["race_by_city"]),
    )
    merged = incidents
    for city_metrics in metrics:
        merged = merged.merge(
            city_metrics, on=["state", "city_clean"], how="left", validate="m:1"
        )
    if len(merged) != row_count:
        raise RuntimeError("City metric joins changed the number of police incident rows.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(destination, index=False)
    return merged
