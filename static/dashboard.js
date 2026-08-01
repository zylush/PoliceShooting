const dashboard = {
  charts: {},
  currentPage: 1,
  searchTimer: null,
  refreshToken: 0,
  lastRefreshed: null,
};
const palette = [
  "#17375e",
  "#2563eb",
  "#0d9488",
  "#f59e0b",
  "#7c3aed",
  "#db2777",
  "#64748b",
];
const stateLayout = [
  ["AK", 1, 1],
  ["ME", 1, 13],
  ["WA", 2, 2],
  ["ID", 2, 3],
  ["MT", 2, 4],
  ["ND", 2, 5],
  ["MN", 2, 6],
  ["WI", 2, 7],
  ["MI", 2, 8],
  ["NY", 2, 10],
  ["VT", 2, 11],
  ["NH", 2, 12],
  ["OR", 3, 2],
  ["NV", 3, 3],
  ["WY", 3, 4],
  ["SD", 3, 5],
  ["IA", 3, 6],
  ["IL", 3, 7],
  ["IN", 3, 8],
  ["OH", 3, 9],
  ["PA", 3, 10],
  ["NJ", 3, 11],
  ["CT", 3, 12],
  ["RI", 3, 13],
  ["CA", 4, 2],
  ["UT", 4, 3],
  ["CO", 4, 4],
  ["NE", 4, 5],
  ["MO", 4, 6],
  ["KY", 4, 7],
  ["WV", 4, 8],
  ["VA", 4, 9],
  ["MD", 4, 10],
  ["DE", 4, 11],
  ["AZ", 5, 3],
  ["NM", 5, 4],
  ["KS", 5, 5],
  ["AR", 5, 6],
  ["TN", 5, 7],
  ["NC", 5, 8],
  ["SC", 5, 9],
  ["DC", 5, 10],
  ["MA", 5, 12],
  ["OK", 6, 5],
  ["LA", 6, 6],
  ["MS", 6, 7],
  ["AL", 6, 8],
  ["GA", 6, 9],
  ["TX", 7, 5],
  ["FL", 7, 10],
  ["HI", 8, 1],
];
const byId = (id) => document.getElementById(id);
const getFilters = () => ({
  state: byId("stateFilter").value,
  race: byId("raceFilter").value,
  flee: byId("fleeFilter").value,
});
const filterParams = () => new URLSearchParams(getFilters());
const formatNumber = (value) => Number(value || 0).toLocaleString();
const formatPercent = (value) => `${Number(value || 0).toFixed(1)}%`;
const formatCurrency = (value) =>
  Number(value || 0).toLocaleString(undefined, {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
async function fetchJSON(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok)
    throw new Error(`Request failed with status ${response.status}`);
  return response.json();
}
function setBusy(isBusy, message = "") {
  document.body.classList.toggle("loading", isBusy);
  byId("applyFilters").disabled = isBusy;
  byId("dashboardStatus").textContent =
    message || (isBusy ? "Updating dashboard" : "Dashboard updated");
}
function showError(error) {
  const banner = byId("dashboardError");
  banner.textContent = `Dashboard data could not be loaded. ${error.message}. Please try again.`;
  banner.hidden = false;
}
function appendOptions(selectId, values) {
  const select = document.getElementById(selectId);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}
function renderActiveFilters() {
  const entries = Object.entries(getFilters()).filter(([, value]) => value);
  const container = byId("activeFilters");
  container.replaceChildren();
  if (!entries.length) {
    container.textContent = "No filters applied · showing the full dataset";
    return;
  }
  const label = document.createElement("span");
  label.textContent = "Active:";
  container.appendChild(label);
  entries.forEach(([key, value]) => {
    const chip = document.createElement("span");
    chip.className = "filter-chip";
    chip.textContent = `${key === "flee" ? "Flee status" : key[0].toUpperCase() + key.slice(1)}: ${value}`;
    container.appendChild(chip);
  });
}
function renderKpis(stats) {
  byId("kpiTotal").textContent = formatNumber(stats.total_incidents);
  byId("kpiTotalNote").textContent =
    `${formatPercent(stats.selection_share_pct)} of ${formatNumber(stats.national_total)} national records`;
  byId("kpiAge").textContent = Number(stats.avg_age || 0).toFixed(1);
  byId("kpiMental").textContent = formatPercent(stats.mental_illness_pct);
  byId("kpiCamera").textContent = formatPercent(stats.body_cam_pct);
  byId("kpiPoverty").textContent = formatPercent(stats.avg_poverty_rate);
  byId("kpiIncome").textContent = formatCurrency(stats.avg_median_income);
  byId("kpiHS").textContent = formatPercent(stats.avg_hs_completion);
  byId("dataContextCoverage").textContent = formatPercent(
    stats.city_context_coverage_pct,
  );
  byId("dataAgeImputed").textContent = formatPercent(stats.age_imputed_pct);
  byId("metaReportingPeriod").textContent = stats.reporting_period;
  byId("selectionScope").textContent =
    `${formatNumber(stats.states_covered)} states · ${formatNumber(stats.cities_covered)} cities`;
}
function drawChart(id, config, summaryId, summary) {
  byId(summaryId).textContent = summary;
  if (typeof Chart === "undefined") {
    byId(summaryId).textContent =
      "Interactive chart unavailable. Aggregated values remain available through the API.";
    return;
  }
  if (dashboard.charts[id]) dashboard.charts[id].destroy();
  dashboard.charts[id] = new Chart(byId(id), config);
}
function baseOptions(horizontal = false) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: horizontal ? "y" : "x",
    interaction: { intersect: false, mode: "index" },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#08172a",
        padding: 11,
        titleFont: { weight: "700" },
      },
    },
    scales: {
      x: { grid: { color: "#e2e8f0" }, ticks: { color: "#64748b" } },
      y: {
        beginAtZero: true,
        grid: { color: "#e2e8f0" },
        ticks: { color: "#64748b" },
      },
    },
  };
}
function describeSeries(id, labels, values, suffix = "") {
  byId(id).textContent = labels.length
    ? labels
        .map((label, index) => `${label}: ${values[index]}${suffix}`)
        .join("; ")
    : "No data for the current selection.";
}
function renderCharts(data) {
  const timelineLabels = data.timeline.map((item) => item.year_month),
    timelineValues = data.timeline.map((item) => item.count),
    peakIndex = timelineValues.indexOf(Math.max(...timelineValues));
  describeSeries("timelineData", timelineLabels, timelineValues);
  drawChart(
    "timelineChart",
    {
      type: "line",
      data: {
        labels: timelineLabels,
        datasets: [
          {
            label: "Incidents",
            data: timelineValues,
            borderColor: "#2563eb",
            backgroundColor: "#2563eb1f",
            fill: true,
            tension: 0.28,
            pointRadius: 1.5,
            borderWidth: 2,
          },
        ],
      },
      options: baseOptions(),
    },
    "timelineSummary",
    timelineValues.length
      ? `Peak month: ${timelineLabels[peakIndex]} with ${formatNumber(timelineValues[peakIndex])} incidents.`
      : "No dated incidents match the current filters.",
  );
  const raceLabels = Object.keys(data.race),
    raceValues = Object.values(data.race);
  describeSeries("raceData", raceLabels, raceValues);
  drawChart(
    "raceChart",
    {
      type: "doughnut",
      data: {
        labels: raceLabels,
        datasets: [
          {
            data: raceValues,
            backgroundColor: palette,
            borderColor: "#fff",
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "62%",
        plugins: {
          legend: {
            position: "bottom",
            labels: { boxWidth: 10, usePointStyle: true },
          },
        },
      },
    },
    "raceSummary",
    raceValues.length
      ? `${raceLabels[0]} is the largest recorded group in this selection.`
      : "No demographic data matches the current filters.",
  );
  const stateLabels = Object.keys(data.states),
    stateValues = Object.values(data.states);
  describeSeries("statesData", stateLabels, stateValues);
  drawChart(
    "statesChart",
    {
      type: "bar",
      data: {
        labels: stateLabels,
        datasets: [
          {
            label: "Incidents",
            data: stateValues,
            backgroundColor: "#17375e",
            borderRadius: 5,
          },
        ],
      },
      options: baseOptions(true),
    },
    "statesSummary",
    stateValues.length
      ? `${stateLabels[0]} has the highest selected count at ${formatNumber(stateValues[0])}.`
      : "No state counts match the current filters.",
  );
  const ageLabels = Object.keys(data.age_groups),
    ageValues = Object.values(data.age_groups);
  describeSeries("ageData", ageLabels, ageValues);
  drawChart(
    "ageChart",
    {
      type: "bar",
      data: {
        labels: ageLabels,
        datasets: [
          {
            label: "Incidents",
            data: ageValues,
            backgroundColor: "#2563eb",
            borderRadius: 5,
          },
        ],
      },
      options: baseOptions(),
    },
    "ageSummary",
    ageValues.length
      ? `${ageLabels[ageValues.indexOf(Math.max(...ageValues))]} is the largest age band.`
      : "No age data matches the current filters.",
  );
  const armedLabels = Object.keys(data.armed),
    armedValues = Object.values(data.armed);
  describeSeries("armedData", armedLabels, armedValues);
  drawChart(
    "armedChart",
    {
      type: "bar",
      data: {
        labels: armedLabels,
        datasets: [
          {
            label: "Incidents",
            data: armedValues,
            backgroundColor: "#0d9488",
            borderRadius: 5,
          },
        ],
      },
      options: baseOptions(true),
    },
    "armedSummary",
    armedValues.length
      ? `${armedLabels[0]} is the most frequent recorded armed status.`
      : "No armed-status data matches the current filters.",
  );
  const povertyLabels = Object.keys(data.state_poverty),
    povertyValues = Object.values(data.state_poverty),
    povertyOptions = baseOptions(true);
  describeSeries("povertyData", povertyLabels, povertyValues, "%");
  povertyOptions.scales.x.ticks.callback = (value) => `${value}%`;
  drawChart(
    "povertyChart",
    {
      type: "bar",
      data: {
        labels: povertyLabels,
        datasets: [
          {
            label: "Average poverty rate",
            data: povertyValues,
            backgroundColor: "#f59e0b",
            borderRadius: 5,
          },
        ],
      },
      options: povertyOptions,
    },
    "povertySummary",
    povertyValues.length
      ? `${povertyLabels[0]} has the highest average linked-city poverty rate shown.`
      : "No poverty context matches the current filters.",
  );
}
function renderMap(data) {
  const map = byId("stateMap"),
    records = new Map(data.states.map((item) => [item.state, item])),
    maxCount = Math.max(1, ...data.states.map((item) => item.total_incidents)),
    selectedState = byId("stateFilter").value;
  map.replaceChildren();
  stateLayout.forEach(([code, row, column]) => {
    const record = records.get(code) || {
        state: code,
        total_incidents: 0,
        avg_age: 0,
        avg_poverty_rate: 0,
      },
      intensity = Math.sqrt(record.total_incidents / maxCount),
      tile = document.createElement("button");
    tile.type = "button";
    const intensityBucket = Math.min(9, Math.round(intensity * 9));
    tile.className = `state-tile row-${row} col-${column} intensity-${intensityBucket}${intensity > 0.58 ? " tile-light" : ""}`;
    tile.setAttribute("aria-pressed", String(selectedState === code));
    tile.setAttribute(
      "aria-label",
      `${code}: ${record.total_incidents} incidents, average age ${record.avg_age || "not available"}`,
    );
    tile.append(document.createTextNode(code));
    const tip = document.createElement("span");
    tip.className = "state-tooltip";
    tip.textContent = `${formatNumber(record.total_incidents)} incidents · Avg age ${Number(record.avg_age || 0).toFixed(1)} · City poverty ${formatPercent(record.avg_poverty_rate)}`;
    tile.appendChild(tip);
    tile.addEventListener("click", () => {
      byId("stateFilter").value = code;
      refreshDashboard();
    });
    map.appendChild(tile);
  });
  const highest = [...data.states].sort(
    (a, b) => b.total_incidents - a.total_incidents,
  )[0];
  byId("mapSummary").textContent = highest
    ? `${highest.state} has the highest selected incident count (${formatNumber(highest.total_incidents)}). Hover or focus a tile for detail.`
    : "No state records match the current filters.";
}
function makeCell(value, className = "") {
  const cell = document.createElement("td");
  cell.textContent = value ?? "N/A";
  if (className) cell.className = className;
  return cell;
}
async function loadTable() {
  const params = filterParams();
  params.set("page", dashboard.currentPage);
  params.set("limit", "10");
  params.set("search", byId("tableSearch").value.trim());
  const result = await fetchJSON(`/api/table?${params}`),
    body = byId("tableBody");
  body.replaceChildren();
  result.data.forEach((row) => {
    const tr = document.createElement("tr");
    tr.append(
      makeCell(row.name, "record-name"),
      makeCell(row.date_str),
      makeCell(row.age),
      makeCell(row.race_full),
      makeCell(row.armed),
      makeCell(`${row.city}, ${row.state}`),
      makeCell(row.poverty_rate_str, "metric-cell"),
      makeCell(row.median_income_str, "metric-cell"),
    );
    body.appendChild(tr);
  });
  const first = result.total ? (result.page - 1) * result.limit + 1 : 0,
    last = Math.min(result.page * result.limit, result.total);
  byId("pageInfo").textContent =
    `${formatNumber(first)}–${formatNumber(last)} of ${formatNumber(result.total)} records · Page ${result.page} of ${result.total_pages}`;
  byId("btnPrev").disabled = result.page <= 1;
  byId("btnNext").disabled = result.page >= result.total_pages;
  byId("tableEmptyState").hidden = result.data.length !== 0;
  byId("tableBody").closest(".table-wrap").hidden = result.data.length === 0;
}
async function refreshDashboard(event) {
  if (event) event.preventDefault();
  const token = ++dashboard.refreshToken;
  setBusy(true, "Updating dashboard data");
  byId("dashboardError").hidden = true;
  renderActiveFilters();
  try {
    const params = filterParams(),
      [stats, chartData, mapData] = await Promise.all([
        fetchJSON(`/api/stats?${params}`),
        fetchJSON(`/api/charts?${params}`),
        fetchJSON(`/api/map?${params}`),
      ]);
    if (token !== dashboard.refreshToken) return;
    renderKpis(stats);
    renderCharts(chartData);
    renderMap(mapData);
    dashboard.currentPage = 1;
    await loadTable();
  } catch (error) {
    if (token === dashboard.refreshToken) showError(error);
  } finally {
    if (token === dashboard.refreshToken) setBusy(false, "Dashboard updated");
  }
}
async function init() {
  setBusy(true, "Loading dashboard");
  try {
    const opt = await fetchJSON("/api/options");
    appendOptions("stateFilter", opt.states);
    appendOptions("raceFilter", opt.races);
    appendOptions("fleeFilter", opt.flee);
    dashboard.lastRefreshed = opt.last_refreshed;
    byId("metaLastRefresh").textContent = new Date(
      opt.last_refreshed,
    ).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
    await refreshDashboard();
  } catch (error) {
    showError(error);
    setBusy(false, "Dashboard failed to load");
  }
}
byId("filterForm").addEventListener("submit", refreshDashboard);
byId("resetFilters").addEventListener("click", () => {
  ["stateFilter", "raceFilter", "fleeFilter", "tableSearch"].forEach((id) => {
    byId(id).value = "";
  });
  refreshDashboard();
});
byId("btnPrev").addEventListener("click", () => {
  dashboard.currentPage -= 1;
  loadTable().catch(showError);
});
byId("btnNext").addEventListener("click", () => {
  dashboard.currentPage += 1;
  loadTable().catch(showError);
});
byId("tableSearch").addEventListener("input", () => {
  clearTimeout(dashboard.searchTimer);
  dashboard.currentPage = 1;
  dashboard.searchTimer = setTimeout(() => loadTable().catch(showError), 300);
});
document.addEventListener("DOMContentLoaded", init);
