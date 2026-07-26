from datetime import datetime, timezone
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional
import math
import pandas as pd
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

from src.load_data import load_all_raw_datasets
from src.clean_data import clean_all_datasets
from src.transform_data import transform_and_merge_datasets
from src.analyze_data import apply_filters, get_kpi_metrics, get_chart_aggregations
from src.visualize import export_static_charts

# File Path Management
BASE_DIR = Path(__file__).resolve().parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_FILE = PROCESSED_DIR / "cleaned_police_killings.csv"

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
    title="Police Shootings & Socio-Economic Analytics",
    description="Multi-dataset analytics dashboard powered by FastAPI & Pandas",
    version="3.0.0",
    lifespan=lifespan,
)


def _dataframe() -> pd.DataFrame:
    return app.state.processed_df


@app.get("/api/options", response_class=JSONResponse)
def get_options():
    """Returns unique filter dropdown options."""
    processed_df = _dataframe()
    return {
        "states": sorted(s for s in processed_df["state"].dropna().unique() if s != "UNKNOWN"),
        "races": sorted(processed_df["race_full"].dropna().unique().tolist()),
        "flee": sorted(processed_df["flee"].dropna().unique().tolist()),
        "last_refreshed": app.state.last_refreshed,
    }


@app.get("/api/stats", response_class=JSONResponse)
def get_stats(state: Optional[str] = None, race: Optional[str] = None, flee: Optional[str] = None):
    """Returns KPIs including socio-economic context."""
    processed_df = _dataframe()
    df = apply_filters(processed_df, state, race, flee)
    return get_kpi_metrics(df, processed_df)


@app.get("/api/charts", response_class=JSONResponse)
def get_charts(state: Optional[str] = None, race: Optional[str] = None, flee: Optional[str] = None):
    """Returns aggregated chart datasets."""
    processed_df = _dataframe()
    df = apply_filters(processed_df, state, race, flee)
    return get_chart_aggregations(df)


@app.get("/api/table", response_class=JSONResponse)
def get_table(
    search: Optional[str] = Query(None, max_length=200),
    state: Optional[str] = None,
    race: Optional[str] = None,
    flee: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(8, ge=1, le=100)
):
    """Returns paginated incident records with city socio-economic context."""
    df = apply_filters(_dataframe(), state, race, flee)

    if search:
        s = search.strip()
        df = df[
            df["name"].astype(str).str.contains(s, case=False, regex=False, na=False) |
            df["city"].astype(str).str.contains(s, case=False, regex=False, na=False) |
            df["armed"].astype(str).str.contains(s, case=False, regex=False, na=False)
        ]

    total_records = len(df)
    start = (page - 1) * limit
    end = start + limit

    records = df.iloc[start:end].copy()
    records["date_str"] = pd.to_datetime(records["date"]).dt.strftime("%b %d, %Y").fillna("N/A")
    records["median_income_str"] = records["median_income"].apply(lambda x: f"${x:,.0f}" if pd.notnull(x) else "N/A")
    records["poverty_rate_str"] = records["poverty_rate"].apply(lambda x: f"{x:.1f}%" if pd.notnull(x) else "N/A")
    display_columns = [
        "id", "name", "date_str", "age", "race_full", "armed", "city", "state",
        "poverty_rate_str", "median_income_str",
    ]
    records_list: list[dict[str, Any]] = []
    for record in records[display_columns].to_dict(orient="records"):
        records_list.append({
            key: None if isinstance(value, float) and math.isnan(value) else value
            for key, value in record.items()
        })

    return {
        "total": total_records,
        "page": page,
        "limit": limit,
        "total_pages": (total_records + limit - 1) // limit if limit > 0 else 1,
        "data": records_list
    }


@app.get("/", response_class=HTMLResponse)
def dashboard_ui():
    """Serves Executive Light-Theme UI."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>US Police Fatalities & Socio-Economic Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style> body { font-family: 'Inter', sans-serif; } </style>
    </head>
    <body class="bg-slate-50 text-slate-800 antialiased min-h-screen border-t-4 border-slate-900">

        <!-- Header -->
        <header class="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-xs">
            <div class="max-w-7xl mx-auto px-6 py-5">
                <div class="flex flex-col lg:flex-row lg:items-center justify-between pb-4 border-b border-slate-100 gap-4">
                    <div>
                        <div class="flex items-center space-x-2">
                            <span class="w-2.5 h-2.5 rounded-full bg-slate-900"></span>
                            <h1 class="text-xl font-bold text-slate-900 tracking-tight">Police Shootings & Socio-Economic Analytics</h1>
                        </div>
                        <p class="text-xs text-slate-500 mt-1">Multi-Dataset Executive Dashboard</p>
                    </div>
                    <div class="flex items-center gap-6 text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-4 py-2">
                        <div>Period: <span id="metaReportingPeriod" class="font-semibold text-slate-800">--</span></div>
                        <div class="w-px h-4 bg-slate-300"></div>
                        <div>Refreshed: <span id="metaLastRefresh" class="font-semibold text-slate-800">--</span></div>
                    </div>
                </div>

                <!-- Filters -->
                <div class="flex flex-wrap items-center justify-between gap-3 mt-4">
                    <div class="flex flex-wrap items-center gap-3">
                        <select id="stateFilter" onchange="refreshDashboard()" class="bg-white text-xs border border-slate-300 rounded-md px-3 py-1.5 text-slate-700">
                            <option value="">All States</option>
                        </select>
                        <select id="raceFilter" onchange="refreshDashboard()" class="bg-white text-xs border border-slate-300 rounded-md px-3 py-1.5 text-slate-700">
                            <option value="">All Races</option>
                        </select>
                        <select id="fleeFilter" onchange="refreshDashboard()" class="bg-white text-xs border border-slate-300 rounded-md px-3 py-1.5 text-slate-700">
                            <option value="">All Flee Types</option>
                        </select>
                    </div>
                    <button onclick="resetFilters()" class="bg-slate-900 text-white text-xs px-4 py-1.5 rounded-md">Reset Filters</button>
                </div>
            </div>
        </header>

        <!-- Main Content -->
        <main class="max-w-7xl mx-auto px-6 py-8 space-y-8">

            <!-- Incident KPIs -->
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
                <div class="bg-white border border-slate-200 rounded-xl p-5"><span class="text-xs text-slate-400 font-semibold uppercase">Total Incidents</span><h3 id="kpiTotal" class="text-3xl font-bold text-slate-900 mt-2">--</h3></div>
                <div class="bg-white border border-slate-200 rounded-xl p-5"><span class="text-xs text-slate-400 font-semibold uppercase">Avg Victim Age</span><h3 id="kpiAge" class="text-3xl font-bold text-slate-900 mt-2">--</h3></div>
                <div class="bg-white border border-slate-200 rounded-xl p-5"><span class="text-xs text-slate-400 font-semibold uppercase">Mental Illness %</span><h3 id="kpiMental" class="text-3xl font-bold text-slate-900 mt-2">--%</h3></div>
                <div class="bg-white border border-slate-200 rounded-xl p-5"><span class="text-xs text-slate-400 font-semibold uppercase">Body Camera %</span><h3 id="kpiCamera" class="text-3xl font-bold text-slate-900 mt-2">--%</h3></div>
            </div>

            <!-- City Socio-Economic Context KPIs -->
            <div class="grid grid-cols-1 sm:grid-cols-3 gap-5">
                <div class="bg-white border border-slate-200 rounded-xl p-5"><span class="text-xs text-teal-600 font-semibold uppercase">Avg City Poverty Rate</span><h3 id="kpiPoverty" class="text-2xl font-bold text-slate-900 mt-1">--%</h3><p class="text-xs text-slate-400 mt-1">Affected locations</p></div>
                <div class="bg-white border border-slate-200 rounded-xl p-5"><span class="text-xs text-indigo-600 font-semibold uppercase">Avg City Household Income</span><h3 id="kpiIncome" class="text-2xl font-bold text-slate-900 mt-1">$--</h3><p class="text-xs text-slate-400 mt-1">Median household income</p></div>
                <div class="bg-white border border-slate-200 rounded-xl p-5"><span class="text-xs text-amber-600 font-semibold uppercase">High School Grad %</span><h3 id="kpiHS" class="text-2xl font-bold text-slate-900 mt-1">--%</h3><p class="text-xs text-slate-400 mt-1">Completed high school</p></div>
            </div>

            <!-- Charts -->
            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div class="lg:col-span-2 bg-white border border-slate-200 rounded-xl p-6"><h2 class="text-sm font-bold text-slate-900 mb-4">Monthly Trend</h2><div class="h-64"><canvas id="timelineChart"></canvas></div></div>
                <div class="bg-white border border-slate-200 rounded-xl p-6"><h2 class="text-sm font-bold text-slate-900 mb-4">Race Breakdown</h2><div class="h-64"><canvas id="raceChart"></canvas></div></div>
            </div>

            <!-- Table -->
            <div class="bg-white border border-slate-200 rounded-xl p-6 space-y-4">
                <div class="flex justify-between items-center">
                    <h2 class="text-sm font-bold text-slate-900">Incident Records & City Context</h2>
                    <input type="text" id="tableSearch" onkeyup="debounceSearch()" placeholder="Search..." class="bg-slate-50 border border-slate-200 text-xs rounded-md px-3 py-1.5 w-64">
                </div>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-xs text-slate-700">
                        <thead class="bg-slate-50 uppercase text-slate-500">
                            <tr>
                                <th class="p-3">Name</th>
                                <th class="p-3">Date</th>
                                <th class="p-3">Age</th>
                                <th class="p-3">Race</th>
                                <th class="p-3">Location</th>
                                <th class="p-3">City Poverty</th>
                                <th class="p-3">City Income</th>
                            </tr>
                        </thead>
                        <tbody id="tableBody" class="divide-y divide-slate-100"></tbody>
                    </table>
                </div>
                <div class="flex justify-between items-center text-xs text-slate-500">
                    <span id="pageInfo">Showing 0 of 0</span>
                    <div class="space-x-2">
                        <button id="btnPrev" onclick="changePage(-1)" class="border px-3 py-1 rounded">Prev</button>
                        <button id="btnNext" onclick="changePage(1)" class="border px-3 py-1 rounded">Next</button>
                    </div>
                </div>
            </div>
        </main>

        <script>
            let charts = {}, currentPage = 1, searchTimeout = null;

            async function init() {
                const opt = await (await fetch('/api/options')).json();
                appendOptions('stateFilter', opt.states);
                appendOptions('raceFilter', opt.races);
                appendOptions('fleeFilter', opt.flee);
                refreshDashboard();
            }

            function appendOptions(selectId, values) {
                const select = document.getElementById(selectId);
                values.forEach(value => {
                    const option = document.createElement('option');
                    option.value = value;
                    option.textContent = value;
                    select.appendChild(option);
                });
            }

            async function refreshDashboard() {
                const s = document.getElementById('stateFilter').value;
                const r = document.getElementById('raceFilter').value;
                const f = document.getElementById('fleeFilter').value;
                const p = new URLSearchParams({ state: s, race: r, flee: f });

                const stats = await (await fetch(`/api/stats?${p}`)).json();
                document.getElementById('kpiTotal').innerText = stats.total_incidents.toLocaleString();
                document.getElementById('kpiAge').innerText = stats.avg_age;
                document.getElementById('kpiMental').innerText = stats.mental_illness_pct + '%';
                document.getElementById('kpiCamera').innerText = stats.body_cam_pct + '%';
                document.getElementById('kpiPoverty').innerText = stats.avg_poverty_rate + '%';
                document.getElementById('kpiIncome').innerText = '$' + stats.avg_median_income.toLocaleString();
                document.getElementById('kpiHS').innerText = stats.avg_hs_completion + '%';
                document.getElementById('metaReportingPeriod').innerText = stats.reporting_period;
                document.getElementById('metaLastRefresh').innerText = new Date().toLocaleTimeString();

                const chartData = await (await fetch(`/api/charts?${p}`)).json();
                renderCharts(chartData);
                currentPage = 1;
                loadTable();
            }

            function renderCharts(data) {
                const draw = (id, type, labels, dataset, color) => {
                    if (charts[id]) charts[id].destroy();
                    charts[id] = new Chart(document.getElementById(id), {
                        type, data: { labels, datasets: [{ data: dataset, backgroundColor: color, borderColor: type==='line'?'#1e293b':'transparent' }] },
                        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: type==='doughnut' } } }
                    });
                };
                draw('timelineChart', 'line', data.timeline.map(x=>x.year_month), data.timeline.map(x=>x.count), '#1e293b');
                draw('raceChart', 'doughnut', Object.keys(data.race), Object.values(data.race), ['#1e293b', '#475569', '#4f46e5', '#0d9488', '#d97706']);
            }

            async function loadTable() {
                const s = document.getElementById('stateFilter').value;
                const r = document.getElementById('raceFilter').value;
                const search = document.getElementById('tableSearch').value;
                const p = new URLSearchParams({ page: currentPage, limit: 8, state: s, race: r, search });

                p.set('flee', document.getElementById('fleeFilter').value);
                const res = await (await fetch(`/api/table?${p}`)).json();
                const tbody = document.getElementById('tableBody');
                tbody.innerHTML = '';
                res.data.forEach(row => {
                    tbody.innerHTML += `<tr>
                        <td class="p-3 font-semibold">${escapeHtml(row.name)}</td>
                        <td class="p-3">${escapeHtml(row.date_str)}</td>
                        <td class="p-3">${escapeHtml(row.age ?? 'N/A')}</td>
                        <td class="p-3">${escapeHtml(row.race_full)}</td>
                        <td class="p-3">${escapeHtml(row.city)}, ${escapeHtml(row.state)}</td>
                        <td class="p-3 text-teal-700 font-medium">${escapeHtml(row.poverty_rate_str)}</td>
                        <td class="p-3 text-indigo-700 font-medium">${escapeHtml(row.median_income_str)}</td>
                    </tr>`;
                });
                document.getElementById('pageInfo').innerText = `Page ${res.page} of ${res.total_pages || 1}`;
                document.getElementById('btnPrev').disabled = currentPage <= 1;
                document.getElementById('btnNext').disabled = currentPage >= res.total_pages;
            }

            function changePage(d) { currentPage += d; loadTable(); }
            function debounceSearch() { clearTimeout(searchTimeout); searchTimeout = setTimeout(loadTable, 300); }
            function resetFilters() { document.getElementById('stateFilter').value = ''; document.getElementById('raceFilter').value = ''; document.getElementById('fleeFilter').value = ''; refreshDashboard(); }
            function escapeHtml(value) {
                const node = document.createElement('span');
                node.textContent = String(value ?? 'N/A');
                return node.innerHTML;
            }
            window.onload = init;
        </script>
    </body>
    </html>
    """


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
