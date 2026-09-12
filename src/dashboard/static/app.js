/**
 * Strategy Lab Dashboard - Frontend Application Logic
 */

let chartInstance = null;
let allStrategies = [];

document.addEventListener("DOMContentLoaded", async () => {
  await loadStrategies();
  await loadComparativeMatrix();
});

function switchTab(tabId) {
  document.querySelectorAll(".tab-content").forEach(el => el.classList.remove("active"));
  document.querySelectorAll(".tab-btn").forEach(el => el.classList.remove("active"));

  const target = document.getElementById(tabId);
  if (target) target.classList.add("active");

  if (tabId === "tab-matrix") document.getElementById("btn-tab-matrix").classList.add("active");
  if (tabId === "tab-backtest") document.getElementById("btn-tab-backtest").classList.add("active");
  if (tabId === "tab-testnet") document.getElementById("btn-tab-testnet").classList.add("active");
}

async function loadStrategies() {
  try {
    const res = await fetch("/api/strategies");
    const data = await res.json();
    allStrategies = data.strategies || [];

    const btSelect = document.getElementById("bt-strategy");
    const tnSelect = document.getElementById("tn-select-strategy");

    btSelect.innerHTML = "";
    tnSelect.innerHTML = "";

    allStrategies.forEach(s => {
      const opt1 = document.createElement("option");
      opt1.value = s.id;
      opt1.textContent = `${s.name} (${s.id})`;
      btSelect.appendChild(opt1);

      const opt2 = document.createElement("option");
      opt2.value = s.id;
      opt2.textContent = `${s.name} (${s.id})`;
      tnSelect.appendChild(opt2);
    });

    document.getElementById("kpi-total-strat").textContent = allStrategies.length;
  } catch (err) {
    console.error("Error loading strategies:", err);
  }
}

async function loadComparativeMatrix() {
  const tbody = document.getElementById("matrix-tbody");
  tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding: 2rem; color: var(--text-muted);">Calculando simulación de las 11 estrategias...</td></tr>`;

  const symbol = document.getElementById("matrix-symbol-select").value;

  try {
    const res = await fetch(`/api/comparative?symbol=${encodeURIComponent(symbol)}&timeframe=1h&days=30`);
    const data = await res.json();
    const list = data.strategies || [];

    tbody.innerHTML = "";

    if (list.length > 0) {
      // Top KPIs
      const bestPf = list.reduce((prev, curr) => (curr.profit_factor > prev.profit_factor ? curr : prev), list[0]);
      const bestSharpe = list.reduce((prev, curr) => (curr.sharpe_ratio > prev.sharpe_ratio ? curr : prev), list[0]);
      const lowestDd = list.reduce((prev, curr) => (curr.max_drawdown_pct < prev.max_drawdown_pct ? curr : prev), list[0]);

      document.getElementById("kpi-best-pf").textContent = bestPf.profit_factor.toFixed(2);
      document.getElementById("kpi-best-pf-strat").textContent = bestPf.name;

      document.getElementById("kpi-best-sharpe").textContent = bestSharpe.sharpe_ratio.toFixed(2);
      document.getElementById("kpi-best-sharpe-strat").textContent = bestSharpe.name;

      document.getElementById("kpi-lowest-dd").textContent = `${lowestDd.max_drawdown_pct.toFixed(1)}%`;
    }

    list.forEach((s, idx) => {
      const tr = document.createElement("tr");
      const isPass = s.verdict === "PASA";
      const badgeClass = isPass ? "badge-pass" : "badge-fail";
      const badgeIcon = isPass ? "🟢" : "🔴";

      tr.innerHTML = `
        <td style="color: var(--text-dim); font-weight: 600;">${idx + 1}</td>
        <td style="font-weight: 600;">${s.name}</td>
        <td><span class="badge ${badgeClass}">${badgeIcon} ${s.verdict}</span></td>
        <td style="font-weight: 700; color: ${s.profit_factor >= 1.3 ? 'var(--color-green)' : (s.profit_factor >= 1 ? 'var(--color-amber)' : 'var(--color-red)')};">${s.profit_factor.toFixed(2)}</td>
        <td>${s.sharpe_ratio.toFixed(2)}</td>
        <td style="color: ${s.max_drawdown_pct > 20 ? 'var(--color-red)' : 'var(--text-main)'};">${s.max_drawdown_pct.toFixed(1)}%</td>
        <td style="color: ${s.total_return_pct >= 0 ? 'var(--color-green)' : 'var(--color-red)'}; font-weight: 600;">${s.total_return_pct >= 0 ? '+' : ''}${s.total_return_pct.toFixed(2)}%</td>
        <td>${s.win_rate_pct.toFixed(1)}%</td>
        <td>${s.total_trades}</td>
        <td style="color: var(--text-muted);">$${s.commissions.toFixed(2)}</td>
        <td>
          <button class="btn-primary" style="padding: 0.35rem 0.75rem; font-size: 0.75rem;" onclick="prefillAndRunBacktest('${s.id}')">Probar</button>
        </td>
      `;
      tbody.appendChild(tr);
    });

  } catch (err) {
    console.error("Error loading comparative matrix:", err);
    tbody.innerHTML = `<tr><td colspan="11" style="color: var(--color-red); text-align: center; padding: 2rem;">Error al cargar datos de la matriz.</td></tr>`;
  }
}

function prefillAndRunBacktest(strategyId) {
  document.getElementById("bt-strategy").value = strategyId;
  switchTab("tab-backtest");
  document.getElementById("backtest-form").dispatchEvent(new Event("submit"));
}

async function executeBacktest(e) {
  e.preventDefault();

  const spinner = document.getElementById("bt-spinner");
  const btn = document.getElementById("btn-run-backtest");
  spinner.style.display = "inline-block";
  btn.disabled = true;

  const payload = {
    strategy: document.getElementById("bt-strategy").value,
    symbol: document.getElementById("bt-symbol").value,
    timeframe: document.getElementById("bt-timeframe").value,
    profile: document.getElementById("bt-profile").value,
    start_date: document.getElementById("bt-start").value,
    end_date: document.getElementById("bt-end").value,
    initial_capital: parseFloat(document.getElementById("bt-capital").value)
  };

  try {
    const res = await fetch("/api/backtest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      let msg = "Error en el servidor";
      try {
        const err = await res.json();
        msg = err.detail || JSON.stringify(err);
      } catch (e) {
        msg = await res.text();
      }
      alert(`Error en Backtest: ${msg}`);
      return;
    }

    const data = await res.json();
    renderBacktestResults(data);

  } catch (err) {
    console.error("Backtest execution failed:", err);
    alert(`Error de conexión al ejecutar backtest: ${err.message || err}`);
  } finally {
    spinner.style.display = "none";
    btn.disabled = false;
  }
}

function renderBacktestResults(data) {
  document.getElementById("bt-results-panel").style.display = "block";

  const m = data.metrics;
  const isPass = data.verdict === "PASA";

  const verdictEl = document.getElementById("res-verdict");
  verdictEl.textContent = data.verdict;
  verdictEl.style.color = isPass ? "var(--color-green)" : "var(--color-red)";

  document.getElementById("res-candles-analyzed").textContent = `${data.total_candles} velas analizadas`;
  document.getElementById("res-pf").textContent = m.profit_factor.toFixed(2);
  document.getElementById("res-sharpe").textContent = m.sharpe_ratio.toFixed(2);
  document.getElementById("res-max-dd").textContent = `${(m.max_drawdown_pct * 100).toFixed(2)}%`;

  const returnPct = m.total_return_pct * 100;
  const returnEl = document.getElementById("res-return");
  returnEl.textContent = `${returnPct >= 0 ? '+' : ''}${returnPct.toFixed(2)}%`;
  returnEl.style.color = returnPct >= 0 ? "var(--color-green)" : "var(--color-red)";

  document.getElementById("res-final-equity").textContent = `Capital Final: $${m.final_equity.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
  document.getElementById("res-winrate").textContent = `${(m.win_rate_pct * 100).toFixed(1)}%`;
  document.getElementById("res-trades-count").textContent = `${m.total_trades} operaciones ejecutadas`;

  // Render Chart
  renderChart(data.equity_curve);

  // Render Trades Table
  const tbody = document.getElementById("trades-tbody");
  tbody.innerHTML = "";

  if (data.trades.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">No se abrieron posiciones en este rango temporal con los filtros aplicados.</td></tr>`;
  } else {
    data.trades.forEach(t => {
      const tr = document.createElement("tr");
      const isWin = t.net_pnl > 0;
      tr.innerHTML = `
        <td style="font-size: 0.75rem; color: var(--text-muted);">${t.entry_time.slice(0, 16)}</td>
        <td style="font-size: 0.75rem; color: var(--text-muted);">${t.exit_time.slice(0, 16)}</td>
        <td><span class="badge ${t.direction === 'long' ? 'badge-buy' : 'badge-sell'}">${t.direction.toUpperCase()}</span></td>
        <td>$${t.entry_price.toLocaleString()}</td>
        <td>$${t.exit_price.toLocaleString()}</td>
        <td style="font-weight: 700; color: ${isWin ? 'var(--color-green)' : 'var(--color-red)'};">${isWin ? '+' : ''}$${t.net_pnl.toFixed(2)}</td>
        <td style="color: ${isWin ? 'var(--color-green)' : 'var(--color-red)'};">${isWin ? '+' : ''}${t.return_pct.toFixed(2)}%</td>
        <td><span class="badge badge-hold">${t.exit_reason}</span></td>
        <td>${t.duration_hours}h</td>
      `;
      tbody.appendChild(tr);
    });
  }

  // Smooth scroll down to results
  document.getElementById("bt-results-panel").scrollIntoView({ behavior: "smooth" });
}

function renderChart(curveData) {
  const ctx = document.getElementById("equityChartCanvas").getContext("2d");

  if (chartInstance) {
    chartInstance.destroy();
  }

  const labels = curveData.map(d => d.timestamp.slice(5, 16));
  const equityPoints = curveData.map(d => d.equity);
  const ddPoints = curveData.map(d => -d.drawdown_pct);

  chartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Equity ($)",
          data: equityPoints,
          borderColor: "#00f2fe",
          backgroundColor: "rgba(0, 242, 254, 0.08)",
          borderWidth: 2,
          fill: true,
          tension: 0.15,
          pointRadius: 0,
          yAxisID: "y"
        },
        {
          label: "Drawdown (%)",
          data: ddPoints,
          borderColor: "#ef4444",
          backgroundColor: "rgba(239, 68, 68, 0.2)",
          borderWidth: 1,
          fill: true,
          pointRadius: 0,
          yAxisID: "y1"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          labels: { color: "#94a3b8", font: { family: "Inter" } }
        },
        tooltip: {
          backgroundColor: "rgba(18, 24, 38, 0.95)",
          titleColor: "#00f2fe",
          bodyColor: "#f3f4f6",
          borderColor: "rgba(255, 255, 255, 0.1)",
          borderWidth: 1
        }
      },
      scales: {
        x: {
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#64748b", maxTicksLimit: 10 }
        },
        y: {
          position: "left",
          grid: { color: "rgba(255, 255, 255, 0.05)" },
          ticks: { color: "#94a3b8" }
        },
        y1: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#ef4444", callback: val => `${val}%` }
        }
      }
    }
  });
}

async function evaluateTestnetLive() {
  const spinner = document.getElementById("tn-spinner");
  spinner.style.display = "inline-block";

  const strat = document.getElementById("tn-select-strategy").value;
  const sym = document.getElementById("tn-select-symbol").value;
  const tf = document.getElementById("tn-select-timeframe").value;
  const prof = document.getElementById("tn-select-profile").value;

  try {
    const res = await fetch("/api/testnet/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ strategy: strat, symbol: sym, timeframe: tf, profile: prof })
    });

    const data = await res.json();

    const actionText = document.getElementById("tn-action-text");
    actionText.textContent = data.action;
    if (data.action.includes("BUY")) {
      actionText.style.color = "var(--color-green)";
    } else if (data.action.includes("SELL")) {
      actionText.style.color = "var(--color-red)";
    } else {
      actionText.style.color = "var(--text-muted)";
    }

    document.getElementById("tn-market-price").textContent = `$${data.close_price.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    document.getElementById("tn-strategy-name").textContent = data.strategy;
    document.getElementById("tn-timestamp").textContent = data.last_timestamp.slice(0, 19);
    document.getElementById("tn-sl-price").textContent = `$${data.stop_loss.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    document.getElementById("tn-tp-price").textContent = `$${data.take_profit.toLocaleString('en-US', {minimumFractionDigits: 2})}`;

    document.getElementById("tn-raw-output").textContent = JSON.stringify(data, null, 2);

  } catch (err) {
    console.error("Testnet evaluation failed:", err);
    alert("Error al conectar con Binance Testnet.");
  } finally {
    spinner.style.display = "none";
  }
}
