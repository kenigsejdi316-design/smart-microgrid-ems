const state = {
  station: "ALL",
  points: 3200,
  refreshTimer: null,
};

const statusText = document.getElementById("statusText");
const stationSelect = document.getElementById("stationSelect");
const refreshBtn = document.getElementById("refreshBtn");
const updatedAt = document.getElementById("updatedAt");
const alertTable = document.getElementById("alertTable");
const stationList = document.getElementById("stationList");

const trendChart = echarts.init(document.getElementById("trendChart"), null, { renderer: "canvas" });
const mixChart = echarts.init(document.getElementById("mixChart"), null, { renderer: "canvas" });
const socChart = echarts.init(document.getElementById("socChart"), null, { renderer: "canvas" });

const charts = [trendChart, mixChart, socChart];

window.addEventListener("resize", () => {
  charts.forEach((chart) => chart.resize());
});

async function apiGet(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "API returned failure");
  }
  return payload.data;
}

async function apiPost(path) {
  const response = await fetch(path, { method: "POST" });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  const payload = await response.json();
  if (!payload.ok) {
    throw new Error(payload.message || "API returned failure");
  }
  return payload.data;
}

function formatNum(value, digits = 1) {
  if (Number.isNaN(Number(value))) {
    return "-";
  }
  return Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  });
}

function setMetric(id, value) {
  document.getElementById(id).textContent = value;
}

function updateStatus(text, isError = false) {
  statusText.textContent = text;
  statusText.style.color = isError ? "#b33a3a" : "#4e6369";
}

function updateOverview(overview) {
  setMetric("kpiPoints", formatNum(overview.data_points, 0));
  setMetric("kpiRenewable", `${formatNum(overview.renewable_ratio, 1)}%`);
  setMetric("kpiSoc", `${formatNum(overview.avg_soc, 1)}%`);
  setMetric("kpiOutlier", formatNum(overview.preprocess?.outliers_removed || 0, 0));
  updatedAt.textContent = overview.updated_at || "-";

  stationList.innerHTML = "";
  (overview.station_cards || []).forEach((card) => {
    const li = document.createElement("li");
    const gapClass = card.power_gap_kw >= 0 ? "gap-positive" : "gap-negative";

    li.innerHTML = `
      <span>${card.station_id}</span>
      <span>Load ${formatNum(card.load_kw, 1)} kW</span>
      <span class="${gapClass}">Gap ${formatNum(card.power_gap_kw, 1)} kW</span>
    `;
    stationList.appendChild(li);
  });
}

function renderTrend(data) {
  trendChart.setOption(
    {
      color: ["#0f9d7d", "#46b3a0", "#f18e3a"],
      animationDuration: 650,
      tooltip: {
        trigger: "axis",
      },
      legend: {
        top: 5,
      },
      grid: {
        left: 48,
        right: 24,
        top: 46,
        bottom: 66,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: data.timestamps,
        axisLabel: {
          color: "#4e6369",
          hideOverlap: true,
        },
      },
      yAxis: {
        type: "value",
        name: "kW",
        nameTextStyle: {
          color: "#4e6369",
        },
        axisLabel: {
          color: "#4e6369",
        },
        splitLine: {
          lineStyle: {
            color: "rgba(16, 37, 43, 0.11)",
          },
        },
      },
      dataZoom: [
        {
          type: "inside",
          throttle: 50,
        },
        {
          type: "slider",
          height: 22,
          bottom: 20,
        },
      ],
      series: [
        {
          name: "PV",
          type: "line",
          showSymbol: false,
          sampling: "lttb",
          progressive: 6000,
          data: data.pv_kw,
          smooth: 0.18,
          areaStyle: {
            color: "rgba(15, 157, 125, 0.12)",
          },
          lineStyle: {
            width: 2,
          },
        },
        {
          name: "Wind",
          type: "line",
          showSymbol: false,
          sampling: "lttb",
          progressive: 6000,
          data: data.wind_kw,
          smooth: 0.18,
          lineStyle: {
            width: 2,
          },
        },
        {
          name: "Load",
          type: "line",
          showSymbol: false,
          sampling: "lttb",
          progressive: 6000,
          data: data.load_kw,
          smooth: 0.18,
          lineStyle: {
            width: 2,
          },
        },
      ],
    },
    true,
  );
}

function renderMix(data) {
  mixChart.setOption(
    {
      color: ["#0f9d7d", "#46b3a0", "#f18e3a"],
      animationDuration: 500,
      tooltip: {
        trigger: "axis",
      },
      legend: {
        top: 5,
      },
      grid: {
        left: 45,
        right: 20,
        top: 44,
        bottom: 36,
      },
      xAxis: {
        type: "category",
        data: data.hours,
        axisLabel: {
          rotate: 35,
          color: "#4e6369",
        },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: "#4e6369",
        },
      },
      series: [
        {
          name: "PV",
          type: "bar",
          stack: "gen",
          data: data.pv_kw,
          barMaxWidth: 14,
        },
        {
          name: "Wind",
          type: "bar",
          stack: "gen",
          data: data.wind_kw,
          barMaxWidth: 14,
        },
        {
          name: "Load",
          type: "line",
          data: data.load_kw,
          smooth: 0.2,
          showSymbol: false,
        },
      ],
    },
    true,
  );
}

function renderSoc(overview) {
  socChart.setOption(
    {
      color: ["#0f9d7d", "#f18e3a"],
      tooltip: {
        trigger: "item",
      },
      series: [
        {
          type: "gauge",
          startAngle: 205,
          endAngle: -25,
          min: 0,
          max: 100,
          splitNumber: 5,
          axisLine: {
            lineStyle: {
              width: 16,
              color: [
                [0.35, "#ef5757"],
                [0.7, "#f1b35c"],
                [1, "#0f9d7d"],
              ],
            },
          },
          progress: {
            show: true,
            width: 16,
          },
          axisTick: { show: false },
          splitLine: {
            distance: -18,
            lineStyle: {
              color: "rgba(16, 37, 43, 0.18)",
              width: 2,
            },
          },
          axisLabel: {
            distance: -38,
            color: "#4e6369",
          },
          anchor: {
            show: true,
            size: 9,
          },
          title: {
            offsetCenter: [0, "60%"],
            fontSize: 14,
            color: "#4e6369",
          },
          detail: {
            valueAnimation: true,
            offsetCenter: [0, "18%"],
            formatter: "{value}%",
            fontSize: 28,
            color: "#10252b",
          },
          data: [
            {
              value: Number(overview.avg_soc || 0).toFixed(1),
              name: "Average SOC",
            },
          ],
        },
      ],
    },
    true,
  );
}

function renderAlerts(alerts) {
  alertTable.innerHTML = "";

  if (!alerts || alerts.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = '<td colspan="6">No active alerts</td>';
    alertTable.appendChild(tr);
    return;
  }

  alerts.forEach((item) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${item.timestamp}</td>
      <td>${item.station_id}</td>
      <td>${formatNum(item.load_kw, 1)} kW</td>
      <td>${formatNum(item.generation_kw, 1)} kW</td>
      <td>${formatNum(item.battery_soc, 1)}%</td>
      <td>${(item.reasons || []).join(", ")}</td>
    `;
    alertTable.appendChild(tr);
  });
}

async function loadDashboard() {
  const station = encodeURIComponent(state.station);

  const [overview, trend, mix, alerts] = await Promise.all([
    apiGet("/api/overview"),
    apiGet(`/api/trend?station=${station}&points=${state.points}`),
    apiGet(`/api/hourly-mix?station=${station}`),
    apiGet(`/api/alerts?station=${station}&limit=12`),
  ]);

  updateOverview(overview);
  renderTrend(trend);
  renderMix(mix);
  renderSoc(overview);
  renderAlerts(alerts);

  updateStatus(`Live stream loaded for station ${state.station}.`);
}

async function bootstrap() {
  try {
    const stations = await apiGet("/api/stations");
    stationSelect.innerHTML = "";

    stations.forEach((stationId) => {
      const option = document.createElement("option");
      option.value = stationId;
      option.textContent = stationId;
      stationSelect.appendChild(option);
    });

    stationSelect.value = state.station;

    stationSelect.addEventListener("change", async (event) => {
      state.station = event.target.value;
      await loadDashboard();
    });

    refreshBtn.addEventListener("click", async () => {
      try {
        refreshBtn.disabled = true;
        updateStatus("Regenerating and preprocessing dataset...");
        await apiPost("/api/refresh?regenerate=true");
        await loadDashboard();
      } catch (error) {
        updateStatus(error.message || "Refresh failed", true);
      } finally {
        refreshBtn.disabled = false;
      }
    });

    await loadDashboard();

    if (state.refreshTimer) {
      clearInterval(state.refreshTimer);
    }
    state.refreshTimer = setInterval(async () => {
      try {
        await loadDashboard();
      } catch (error) {
        updateStatus(error.message || "Auto refresh failed", true);
      }
    }, 15000);
  } catch (error) {
    updateStatus(error.message || "Dashboard initialization failed", true);
  }
}

bootstrap();
