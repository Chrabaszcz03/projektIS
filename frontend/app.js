"use strict";

const CATEGORY_COLORS = {
  "Gospodarka":      "#2196F3",
  "Technologia":     "#4CAF50",
  "Geopolityka":     "#F44336",
  "Popkultura":      "#FF9800",
  "Regulacje/Prawo": "#9C27B0",
  "Inne":            "#9E9E9E",
};

// ── Auth ────────────────────────────────────────────────────────────────────

function getToken() { return localStorage.getItem("jwt"); }
function setToken(t) { localStorage.setItem("jwt", t); }
function clearToken() { localStorage.removeItem("jwt"); }

function authHeaders() {
  return { "Authorization": "Bearer " + getToken() };
}

async function apiPost(url, body, useForm) {
  const opts = { method: "POST" };
  if (useForm) {
    opts.body = body;
    opts.headers = authHeaders();
  } else {
    opts.headers = { "Content-Type": "application/x-www-form-urlencoded" };
    opts.body = body;
  }
  const r = await fetch(url, opts);
  if (!r.ok) {
    const err = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(err.detail || r.statusText);
  }
  return r.json();
}

// ── UI state ────────────────────────────────────────────────────────────────

function showMain() {
  document.getElementById("loginPanel").classList.add("d-none");
  document.getElementById("mainPanel").classList.remove("d-none");
  const stored = getToken();
  try {
    const payload = JSON.parse(atob(stored.split(".")[1]));
    document.getElementById("navUser").textContent = payload.sub || "";
  } catch { /* ignore */ }
}

function showLogin() {
  document.getElementById("mainPanel").classList.add("d-none");
  document.getElementById("loginPanel").classList.remove("d-none");
}

function setStatus(msg, type = "info") {
  const el = document.getElementById("statusMsg");
  el.className = `alert alert-${type}`;
  el.textContent = msg;
  el.classList.remove("d-none");
}

function clearStatus() {
  document.getElementById("statusMsg").classList.add("d-none");
}

function setImportExportMsg(msg, ok) {
  const el = document.getElementById("importExportMsg");
  el.className = `alert alert-${ok ? "success" : "danger"} py-2`;
  el.textContent = msg;
  el.classList.remove("d-none");
  setTimeout(() => el.classList.add("d-none"), 5000);
}

// ── Login / Register ────────────────────────────────────────────────────────

async function doLogin() {
  const u = document.getElementById("loginUser").value.trim();
  const p = document.getElementById("loginPass").value;
  const errEl = document.getElementById("loginError");
  errEl.classList.add("d-none");
  try {
    const data = await apiPost(
      "/api/auth/login",
      `username=${encodeURIComponent(u)}&password=${encodeURIComponent(p)}`
    );
    setToken(data.access_token);
    showMain();
    await loadCategories();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove("d-none");
  }
}

async function doRegister() {
  const u = document.getElementById("loginUser").value.trim();
  const p = document.getElementById("loginPass").value;
  const errEl = document.getElementById("loginError");
  errEl.classList.add("d-none");
  try {
    await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p }),
    }).then(async r => {
      if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    });
    await doLogin();
  } catch (e) {
    errEl.textContent = e.message;
    errEl.classList.remove("d-none");
  }
}

// ── Categories ──────────────────────────────────────────────────────────────

async function loadCategories() {
  try {
    const cats = await fetch("/api/categories").then(r => r.json());
    const sel = document.getElementById("selCategory");
    sel.innerHTML = '<option value="">Wszystkie</option>';
    cats.forEach(c => {
      const o = document.createElement("option");
      o.value = c;
      o.textContent = c;
      sel.appendChild(o);
    });
    await loadAnalysisCharts(document.getElementById("selCrypto").value || "BTC");
  } catch { /* ignore, categories not critical */ }
}

// ── Chart ───────────────────────────────────────────────────────────────────

let priceChart = null;
let analysisReturnChart = null;
let analysisPvalChart   = null;

function buildReturnChart(results) {
  const ctx    = document.getElementById("analysisReturnChart").getContext("2d");
  const labels = results.map(r => r.category);
  const event  = results.map(r => +(r.mean_return_event  ).toFixed(4));
  const ctrl   = results.map(r => +(r.mean_return_control).toFixed(4));
  const bgEvt  = results.map(r => CATEGORY_COLORS[r.category] || "#9E9E9E");
  const bgCtrl = bgEvt.map(c => c + "66");

  if (analysisReturnChart) analysisReturnChart.destroy();

  analysisReturnChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: "Dni z wydarzeniami", data: event, backgroundColor: bgEvt },
        { label: "Dni kontrolne",      data: ctrl,  backgroundColor: bgCtrl },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: true, position: "top" },
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.dataset.label}: ${ctx.parsed.y >= 0 ? "+" : ""}${ctx.parsed.y.toFixed(4)}%`,
          },
        },
        annotation: {},
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          ticks: { callback: v => (v >= 0 ? "+" : "") + v.toFixed(2) + "%" },
          grid: { color: "rgba(0,0,0,0.05)" },
        },
      },
    },
  });
}

function buildPvalChart(results) {
  const ctx    = document.getElementById("analysisPvalChart").getContext("2d");
  const labels = results.map(r => r.category);
  const pvals  = results.map(r => +r.p_value.toFixed(6));
  const colors = results.map(r => r.significant ? "#F44336" : "#2196F3");

  if (analysisPvalChart) analysisPvalChart.destroy();

  analysisPvalChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "p-wartość", data: pvals, backgroundColor: colors }],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: { label: ctx => `p = ${ctx.parsed.y.toFixed(6)}` },
        },
        annotation: {
          annotations: {
            significanceLine: {
              type: "line",
              yMin: 0.05,
              yMax: 0.05,
              borderColor: "#333",
              borderWidth: 1.5,
              borderDash: [5, 4],
              label: {
                display: true,
                content: "p = 0.05",
                position: "end",
                backgroundColor: "rgba(0,0,0,0.6)",
                font: { size: 11 },
              },
            },
          },
        },
      },
      scales: {
        x: { grid: { display: false } },
        y: {
          min: 0,
          suggestedMax: 1,
          ticks: { callback: v => v.toFixed(2) },
          grid: { color: "rgba(0,0,0,0.05)" },
        },
      },
    },
  });
}

async function loadAnalysisCharts(coin) {
  const returnCanvas      = document.getElementById("analysisReturnChart");
  const pvalCanvas        = document.getElementById("analysisPvalChart");
  const returnPlaceholder = document.getElementById("analysisReturnPlaceholder");
  const pvalPlaceholder   = document.getElementById("analysisPvalPlaceholder");

  function showPlaceholders() {
    returnCanvas.classList.add("d-none");
    pvalCanvas.classList.add("d-none");
    returnPlaceholder.classList.remove("d-none");
    pvalPlaceholder.classList.remove("d-none");
    if (analysisReturnChart) { analysisReturnChart.destroy(); analysisReturnChart = null; }
    if (analysisPvalChart)   { analysisPvalChart.destroy();   analysisPvalChart   = null; }
  }

  try {
    const resp    = await fetch(`/api/analysis/results?coin=${coin}`);
    const payload = await resp.json();
    const results = payload.items || [];

    if (results.length === 0) { showPlaceholders(); return; }

    returnPlaceholder.classList.add("d-none");
    pvalPlaceholder.classList.add("d-none");
    returnCanvas.classList.remove("d-none");
    pvalCanvas.classList.remove("d-none");

    buildReturnChart(results);
    buildPvalChart(results);
  } catch {
    showPlaceholders();
  }
}

function buildChart(prices, events) {
  const ctx = document.getElementById("priceChart").getContext("2d");

  const priceData = prices.map(p => ({ x: p.date, y: p.price }));

  const annotations = {};
  events.forEach((ev, i) => {
    const color = CATEGORY_COLORS[ev.category] || "#9E9E9E";
    annotations[`ev${i}`] = {
      type: "line",
      xMin: ev.date,
      xMax: ev.date,
      borderColor: color,
      borderWidth: 1,
      borderDash: [3, 3],
      label: {
        display: false,
        content: ev.category,
      },
    };
  });

  if (priceChart) priceChart.destroy();

  priceChart = new Chart(ctx, {
    type: "line",
    data: {
      datasets: [{
        label: document.getElementById("selCrypto").value + " USD",
        data: priceData,
        borderColor: "#1565C0",
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0.1,
        fill: false,
      }],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "category",
          ticks: {
            maxTicksLimit: 18,
            maxRotation: 0,
            autoSkip: true,
          },
          grid: { display: false },
        },
        y: {
          ticks: {
            callback: v => "$" + Number(v).toLocaleString("pl-PL"),
          },
          grid: { color: "rgba(0,0,0,0.05)" },
        },
      },
      plugins: {
        legend: { display: true, position: "top" },
        tooltip: {
          callbacks: {
            label: ctx => "$" + ctx.parsed.y.toLocaleString("pl-PL", { minimumFractionDigits: 2 }),
          },
        },
        annotation: { annotations },
      },
    },
  });
}

// ── Table ───────────────────────────────────────────────────────────────────

function buildTable(events) {
  const tbody = document.getElementById("eventsTableBody");
  tbody.innerHTML = "";
  document.getElementById("tableCount").textContent = `${events.length} wierszy`;

  events.forEach(ev => {
    const pct = ev.pct_change;
    let pctCell = "<td class='text-end text-muted'>—</td>";
    if (pct !== null && pct !== undefined) {
      const cls = pct >= 0 ? "pct-positive" : "pct-negative";
      pctCell = `<td class="text-end ${cls}">${pct >= 0 ? "+" : ""}${pct.toFixed(2)}%</td>`;
    }

    const catColor = CATEGORY_COLORS[ev.category] || "#9E9E9E";
    const catBadge = `<span class="badge" style="background:${catColor}">${ev.category}</span>`;

    const priceStr = ev.price != null
      ? "$" + Number(ev.price).toLocaleString("pl-PL", { minimumFractionDigits: 2 })
      : "—";

    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td class="text-nowrap">${ev.date}</td>
      <td>${catBadge}</td>
      <td class="text-truncate" style="max-width:360px" title="${escHtml(ev.title)}">${escHtml(ev.title)}</td>
      <td class="text-end text-nowrap">${priceStr}</td>
      ${pctCell}
    `;
    tbody.appendChild(tr);
  });
}

function escHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── Apply (fetch + render) ──────────────────────────────────────────────────

async function applyFilters() {
  const crypto   = document.getElementById("selCrypto").value;
  const from     = document.getElementById("fromDate").value;
  const to       = document.getElementById("toDate").value;
  const category = document.getElementById("selCategory").value;

  if (!from || !to) { setStatus("Ustaw zakres dat.", "warning"); return; }

  setStatus("Pobieranie danych...", "info");
  document.getElementById("btnApply").disabled = true;

  try {
    const priceUrl  = `/api/prices?crypto=${crypto}&from=${from}&to=${to}`;
    const evUrl     = `/api/events/price-changes?crypto=${crypto}&from=${from}&to=${to}&limit=5000`
                    + (category ? `&category=${encodeURIComponent(category)}` : "");

    const [priceResp, evResp] = await Promise.all([
      fetch(priceUrl).then(r => r.json()),
      fetch(evUrl).then(r => r.json()),
    ]);

    const prices = priceResp.items || [];
    const events = (evResp.items || []).sort((a, b) => a.date.localeCompare(b.date));

    buildChart(prices, events);
    buildTable([...events].reverse());
    await loadAnalysisCharts(crypto);

    clearStatus();
  } catch (e) {
    setStatus("Błąd pobierania danych: " + e.message, "danger");
  } finally {
    document.getElementById("btnApply").disabled = false;
  }
}

// ── Export ──────────────────────────────────────────────────────────────────

async function downloadFile(url, filename) {
  const r = await fetch(url, { headers: authHeaders() });
  if (!r.ok) {
    const e = await r.json().catch(() => ({ detail: r.statusText }));
    throw new Error(e.detail || r.statusText);
  }
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function exportJson() {
  try {
    await downloadFile("/api/export/events", "events_export.json");
    setImportExportMsg("Eksport JSON zakończony.", true);
  } catch (e) {
    setImportExportMsg("Błąd eksportu JSON: " + e.message, false);
  }
}

async function exportXml() {
  const crypto = document.getElementById("selCrypto").value;
  try {
    await downloadFile(`/api/export/prices?crypto=${crypto}`, "prices_export.xml");
    setImportExportMsg("Eksport XML zakończony.", true);
  } catch (e) {
    setImportExportMsg("Błąd eksportu XML: " + e.message, false);
  }
}

// ── Import ──────────────────────────────────────────────────────────────────

async function importFile(inputId, url) {
  const input = document.getElementById(inputId);
  if (!input.files.length) {
    setImportExportMsg("Wybierz plik przed wysyłaniem.", false);
    return;
  }
  const fd = new FormData();
  fd.append("file", input.files[0]);
  try {
    const r = await fetch(url, { method: "POST", headers: authHeaders(), body: fd });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || r.statusText);
    const msg = data.rows_upserted != null
      ? `Import XML: ${data.rows_upserted} wierszy (${data.tickers_imported.join(", ")})`
      : `Import JSON: ${data.imported} rekordów`;
    setImportExportMsg(msg, true);
    input.value = "";
  } catch (e) {
    setImportExportMsg("Błąd importu: " + e.message, false);
  }
}

// ── Init ────────────────────────────────────────────────────────────────────

document.addEventListener("DOMContentLoaded", async () => {
  if (getToken()) {
    showMain();
    await loadCategories();
  } else {
    showLogin();
  }

  document.getElementById("btnLogin").addEventListener("click", doLogin);
  document.getElementById("btnRegister").addEventListener("click", doRegister);
  document.getElementById("loginPass").addEventListener("keydown", e => {
    if (e.key === "Enter") doLogin();
  });

  document.getElementById("btnLogout").addEventListener("click", () => {
    clearToken();
    showLogin();
  });

  document.getElementById("btnApply").addEventListener("click", applyFilters);

  document.getElementById("btnExportJson").addEventListener("click", exportJson);
  document.getElementById("btnExportXml").addEventListener("click", exportXml);

  document.getElementById("btnImportXml").addEventListener("click", () =>
    importFile("importXmlFile", "/api/import/xml"));
  document.getElementById("btnImportJson").addEventListener("click", () =>
    importFile("importJsonFile", "/api/import/json"));
});
