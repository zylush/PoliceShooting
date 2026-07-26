"""Static export charts for sharing outside the interactive dashboard."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _save_plot(series: pd.Series, kind: str, title: str, color: str, destination: Path) -> None:
    figure, axis = plt.subplots(figsize=(10, 4.5))
    if series.empty:
        axis.text(0.5, 0.5, "No data available", ha="center", va="center")
        axis.set_axis_off()
    else:
        series.plot(kind=kind, ax=axis, color=color, linewidth=2 if kind == "line" else None)
        axis.set_ylabel("Incidents" if title != "State Poverty Rates" else "Poverty rate (%)")
        axis.tick_params(axis="x", rotation=45)
    axis.set_title(title, loc="left", fontweight="bold")
    figure.tight_layout()
    figure.savefig(destination, dpi=200, bbox_inches="tight")
    plt.close(figure)


def export_static_charts(dataframe: pd.DataFrame, output_dir: Path) -> None:
    """Write the requested timeline, race, and state-poverty PNG summaries."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    timeline = dataframe.loc[dataframe["year_month"] != "Unknown"].groupby("year_month").size().sort_index()
    race = dataframe["race_full"].fillna("Unknown").value_counts()
    poverty = dataframe.groupby("state")["poverty_rate"].mean().dropna().sort_values(ascending=False).head(10)
    _save_plot(timeline, "line", "Monthly Incidents Trend", "#1E293B", destination / "timeline_trend.png")
    _save_plot(race, "bar", "Race Distribution", "#4F46E5", destination / "race_distribution.png")
    _save_plot(poverty, "bar", "State Poverty Rates", "#0D9488", destination / "state_poverty_rates.png")
