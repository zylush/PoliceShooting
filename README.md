# Police Shootings & Socio-Economic Analytics Dashboard

A multi-dataset analytics dashboard that merges **US police killings data (2015–2017)** with city-level socio-economic indicators (median income, poverty rate, high school completion, and racial demographics). Built with **FastAPI** and **Pandas**.

## Features

- **End-to-end data pipeline** — Load, clean, transform, merge, and analyze five source datasets automatically
- **Interactive dashboard UI** — Filter by state, race, and flee type; view KPIs, charts, and a paginated incident table
- **REST API** — JSON endpoints for stats, chart data, filter options, and paginated records
- **Static chart exports** — PNG exports of timeline trends, race distribution, and state poverty rates via Matplotlib
- **Socio-economic context** — Each incident is enriched with its city's poverty rate, median household income, high school completion rate, and racial composition

## Getting Started

### Prerequisites

- Python **≥3.14**
- [uv](https://docs.astral.sh/uv/) (recommended) or `pip`

### Installation

```bash
git clone https://github.com/zylush/Police-Shooting-Visualization.git
cd Police-Shooting-Visualization
```

Create a virtual environment and install dependencies:

```bash
# Using uv (recommended)
uv sync

# Or using pip
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### Run Locally

```bash
# Using the FastAPI CLI
fastapi dev main.py

# Or directly with Python
python main.py
```

Open **http://127.0.0.1:8000** in your browser to view the dashboard.

## Dashboard Experience

- **Executive overview** with selection share, geographic coverage, incident KPIs, and city context
- **Interactive state intensity map** with keyboard-accessible details and click-to-filter behavior
- **Linked visual analysis** for monthly trends, race and ethnicity, age groups, armed status, state volume, and poverty context
- **Enterprise interaction states** including active filters, loading feedback, recoverable errors, empty results, and precise pagination
- **Accessible controls** with semantic labels, focus states, live status announcements, and chart summaries
- **Data-quality transparency** showing complete city-context coverage and median-imputed age rates for every selection

The dashboard reads the server-provided refresh timestamp and updates all KPIs, maps, charts, and records from the same global filter selection.

## Usage

1. The dashboard loads automatically with full dataset KPIs and charts.
2. Use the **filter dropdowns** (State, Race, Flee Type) to narrow down the data.
3. Use the **search box** to find incidents by name, city, or weapon type.
4. Navigate the **incident table** using pagination controls.
5. The **REST API** is available at `/api/stats`, `/api/charts`, `/api/map`, `/api/table`, and `/api/options`.

### Example API Call

```bash
curl "http://127.0.0.1:8000/api/stats?state=WA&race=White"
```

## Project Structure

```text
.
+-- data/
|   +-- raw/                        # Source CSVs (PoliceKillingsUS.csv, etc.)
|   +-- processed/                  # Cleaned output (CSV + PNG exports)
+-- src/
|   +-- load_data.py                # CSV loading with filename aliases
|   +-- clean_data.py               # Schema validation & type normalization
|   +-- transform_data.py           # Feature engineering & city-level joins
|   +-- analyze_data.py             # Filtering, KPI & chart aggregation logic
|   +-- visualize.py                # Static chart export (PNG)
+-- tests/
|   +-- test_load_data.py           # Pipeline acceptance tests
|   +-- test_api.py                 # FastAPI integration tests
+-- templates/dashboard.html       # Responsive enterprise dashboard UI
+-- main.py                         # FastAPI application and analytics API
+-- pyproject.toml                  # Project metadata & dependencies
+-- requirements.txt                # pip-compatible dependency list
+-- README.md
```

## Configuration

No additional configuration is required. The project loads source CSVs from `data/raw/` automatically. If you need to change the data directory, modify `BASE_DIR` / `RAW_DIR` in `main.py`.

## Contributing

Contributions are welcome.

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-change`.
3. Make and test your changes.
4. Open a pull request describing what changed and why.

## License

This project is licensed under the [MIT License](LICENSE), unless noted otherwise.
