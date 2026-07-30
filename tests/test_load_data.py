from pathlib import Path

import pandas as pd
import pytest

from src.analyze_data import apply_filters, get_chart_aggregations, get_kpi_metrics
from src.clean_data import _clean_city_name, clean_all_datasets
from src.load_data import load_all_raw_datasets
from src.transform_data import transform_and_merge_datasets


RAW_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def test_loader_accepts_workspace_file_aliases_and_strips_headers() -> None:
    datasets = load_all_raw_datasets(RAW_DATA_DIR)

    assert set(datasets) == {
        "police_killings",
        "median_income",
        "poverty_rate",
        "high_school",
        "race_by_city",
    }
    assert all(not dataset.empty for dataset in datasets.values())
    assert datasets["median_income"].columns.tolist() == [
        "Geographic Area",
        "City",
        "Median Income",
    ]


def test_clean_transform_and_analyze_pipeline(tmp_path: Path) -> None:
    raw = {
        "police_killings": pd.DataFrame(
            {
                "id": [1, 2],
                "name": ["A Person", None],
                "date": ["02/01/15", "invalid"],
                "manner_of_death": ["shot", None],
                "armed": ["gun", "-"],
                "age": ["29", "-"],
                "gender": ["M", None],
                "race": ["B", None],
                "city": ["Austin city", "Austin city"],
                "state": ["tx", "TX"],
                "signs_of_mental_illness": ["True", "false"],
                "threat_level": ["attack", None],
                "flee": ["Not fleeing", None],
                "body_camera": ["0", "yes"],
            }
        ),
        "median_income": pd.DataFrame({"Geographic Area": ["TX"], "City": ["Austin city"], "Median Income": ["$50,000"]}),
        "poverty_rate": pd.DataFrame({"Geographic Area": ["TX"], "City": ["Austin city"], "poverty_rate": ["10.5%"]}),
        "high_school": pd.DataFrame({"Geographic Area": ["TX"], "City": ["Austin city"], "percent_completed_hs": ["88.2"]}),
        "race_by_city": pd.DataFrame(
            {"Geographic area": ["TX"], "City": ["Austin city"], "share_white": [50], "share_black": [10], "share_native_american": [1], "share_asian": [5], "share_hispanic": [30]}
        ),
    }

    cleaned = clean_all_datasets(raw)
    merged = transform_and_merge_datasets(cleaned, tmp_path / "cleaned.csv")

    assert _clean_city_name(pd.Series(["Austin city", "Pine town"])) .tolist() == ["Austin", "Pine"]
    assert merged.loc[0, "date"] == pd.Timestamp("2015-01-02")
    assert pd.isna(merged.loc[1, "date"])
    assert merged.loc[0, "age_group"] == "18-29"
    assert merged.loc[0, "median_income"] == 50000
    assert merged.loc[0, "race_full"] == "Black"
    assert (tmp_path / "cleaned.csv").exists()

    filtered = apply_filters(merged, state="TX", race="Black", flee="Not fleeing")
    metrics = get_kpi_metrics(filtered, merged)
    charts = get_chart_aggregations(filtered)

    assert len(filtered) == 1
    assert metrics["total_incidents"] == 1
    assert metrics["mental_illness_pct"] == 100.0
    assert charts["timeline"] == [{"year_month": "2015-01", "count": 1}]


def test_transform_imputes_missing_ages_by_state_then_overall_median(tmp_path: Path) -> None:
    cleaned_datasets = {
        "police_killings": pd.DataFrame(
            {
                "state": ["TX", "TX", "TX", "WA"],
                "age": [20.0, 40.0, pd.NA, pd.NA],
                "date": pd.to_datetime(["2015-01-01"] * 4),
                "race": ["W"] * 4,
                "city_clean": ["Austin"] * 4,
            }
        ),
        "median_income": pd.DataFrame(columns=["state", "city_clean", "median_income"]),
        "poverty_rate": pd.DataFrame(columns=["state", "city_clean", "poverty_rate"]),
        "high_school": pd.DataFrame(columns=["state", "city_clean", "percent_completed_hs"]),
        "race_by_city": pd.DataFrame(
            columns=["state", "city_clean", "share_white", "share_black", "share_native_american", "share_asian", "share_hispanic"]
        ),
    }

    merged = transform_and_merge_datasets(cleaned_datasets, tmp_path / "cleaned.csv")

    assert merged["age"].tolist() == [20.0, 40.0, 30.0, 30.0]
    assert merged.loc[2, "age_group"] == "30-44"
    assert merged.loc[3, "age_group"] == "30-44"


def test_cleaning_requires_expected_source_columns() -> None:
    with pytest.raises(ValueError, match="police_killings"):
        clean_all_datasets(
            {
                "police_killings": pd.DataFrame({"id": [1]}),
                "median_income": pd.DataFrame(),
                "poverty_rate": pd.DataFrame(),
                "high_school": pd.DataFrame(),
                "race_by_city": pd.DataFrame(),
            }
        )
