"""Loading utilities for the five source datasets."""

from pathlib import Path
from typing import Final

import pandas as pd


DATASET_FILES: Final[dict[str, tuple[str, ...]]] = {
    "police_killings": ("PoliceKillingUS.csv",),
    # The first names mirror the brief; the second names support this workspace.
    "median_income": ("MedianHouseholdincome.csv", "MedianHouseholdIncome2015.csv"),
    "poverty_rate": (
        "PercentagePeopleBelowPropertyLevel.csv",
        "PercentagePeopleBelowPovertyLevel.csv",
    ),
    "high_school": ("PercentOver25CompletedHighSchool.csv",),
    "race_by_city": ("ShareRaceByCity.csv",),
}


def _read_csv_safe(file_path: Path) -> pd.DataFrame:
    """Read a CSV using the source's common encoding and clean its headers."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Required dataset was not found: {file_path}")

    try:
        dataframe = pd.read_csv(file_path, encoding="windows-1252")
    except UnicodeDecodeError:
        dataframe = pd.read_csv(file_path, encoding="utf-8", encoding_errors="replace")

    dataframe.columns = dataframe.columns.map(lambda value: str(value).strip())
    return dataframe


def _find_source_file(raw_dir: Path, dataset_name: str) -> Path:
    candidates = DATASET_FILES[dataset_name]
    for filename in candidates:
        candidate = raw_dir / filename
        if candidate.is_file():
            return candidate
    expected = ", ".join(candidates)
    raise FileNotFoundError(
        f"Missing '{dataset_name}' source in {raw_dir}. Expected one of: {expected}."
    )


def load_all_raw_datasets(raw_dir: Path) -> dict[str, pd.DataFrame]:
    """Load all required raw CSVs, accepting documented filename aliases."""
    source_dir = Path(raw_dir)
    return {
        dataset_name: _read_csv_safe(_find_source_file(source_dir, dataset_name))
        for dataset_name in DATASET_FILES
    }
